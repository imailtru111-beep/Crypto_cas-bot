import asyncio
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.models import get_user, update_balance, log_bet, get_setting
from games.roulette import spin_roulette, calculate_roulette_win, format_roulette_result, get_number_color
from utils.keyboards import roulette_bet_type_kb, roulette_bet_amount_kb, back_kb, main_menu_kb

router = Router()

ROULETTE_HISTORY = {}  # tg_id -> list


class RouletteStates(StatesGroup):
    waiting_number = State()
    waiting_custom_bet = State()


@router.callback_query(F.data == "game_roulette")
async def cb_roulette(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        f"🎰 ═══════════════════\n"
        f"    РУЛЕТКА LEPS\n"
        f"════════════════════\n\n"
        f"🎯 Европейская рулетка (0-36)\n\n"
        f"Выбери тип ставки:\n\n"
        f"🔴⚫ Цвет — ×2\n"
        f"➕➖ Чёт/Нечет — ×2\n"
        f"📉📈 Половины — ×2\n"
        f"1️⃣2️⃣3️⃣ Дюжины — ×3\n"
        f"   Колонки — ×3\n"
        f"🎯 Число — ×36\n"
        f"════════════════════"
    )
    await call.message.edit_text(text, reply_markup=roulette_bet_type_kb())
    await call.answer()


@router.callback_query(F.data == "rl_number")
async def cb_rl_number(call: CallbackQuery, state: FSMContext):
    await state.set_state(RouletteStates.waiting_number)
    await call.message.edit_text(
        "🎯 Введи число от 0 до 36:",
        reply_markup=back_kb("game_roulette")
    )
    await call.answer()


@router.message(RouletteStates.waiting_number)
async def process_roulette_number(message: Message, state: FSMContext):
    try:
        num = int(message.text.strip())
        if not (0 <= num <= 36):
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи число от 0 до 36:")
        return

    await state.clear()
    await message.answer(
        f"🎯 Ставка на число {num}\nВыбери сумму ставки:",
        reply_markup=roulette_bet_amount_kb("number", str(num))
    )


@router.callback_query(F.data.startswith("rl_color_") | F.data.startswith("rl_parity_") |
                       F.data.startswith("rl_dozen_") | F.data.startswith("rl_column_") |
                       F.data.startswith("rl_half_"))
async def cb_rl_bet_type(call: CallbackQuery):
    parts = call.data.split("_")
    bet_type = parts[1]
    bet_value = parts[2]

    type_names = {
        "color": {"red": "🔴 Красное", "black": "⚫ Чёрное"},
        "parity": {"even": "➕ Чётное", "odd": "➖ Нечётное"},
        "half": {"low": "📉 1-18", "high": "📈 19-36"},
        "dozen": {"1": "1️⃣ Дюжина 1", "2": "2️⃣ Дюжина 2", "3": "3️⃣ Дюжина 3"},
        "column": {"1": "Колонка 1", "2": "Колонка 2", "3": "Колонка 3"},
    }

    name = type_names.get(bet_type, {}).get(bet_value, f"{bet_type} {bet_value}")
    await call.message.edit_text(
        f"🎯 Ставка: {name}\nВыбери сумму:",
        reply_markup=roulette_bet_amount_kb(bet_type, bet_value)
    )
    await call.answer()


@router.callback_query(F.data.startswith("rl_custom_"))
async def cb_rl_custom(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    bet_type = parts[2]
    bet_value = parts[3]
    await state.update_data(bet_type=bet_type, bet_value=bet_value)
    await state.set_state(RouletteStates.waiting_custom_bet)
    await call.message.edit_text(
        "✏️ Введи сумму ставки в TON:",
        reply_markup=back_kb("game_roulette")
    )
    await call.answer()


@router.message(RouletteStates.waiting_custom_bet)
async def process_roulette_custom_bet(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное число:")
        return

    data = await state.get_data()
    await state.clear()
    await _place_roulette_bet(message, data["bet_type"], data["bet_value"], amount)


@router.callback_query(F.data.startswith("rl_bet_"))
async def cb_rl_place_bet(call: CallbackQuery):
    # rl_bet_{type}_{value}_{amount}
    parts = call.data[7:].rsplit("_", 1)
    type_value = parts[0]
    amount = float(parts[1])

    tv_parts = type_value.split("_", 1)
    bet_type = tv_parts[0]
    bet_value = tv_parts[1] if len(tv_parts) > 1 else ""

    await _place_roulette_bet(call.message, bet_type, bet_value, amount, call)


async def _place_roulette_bet(message_or_msg, bet_type: str, bet_value: str, amount: float, call=None):
    tg_id = message_or_msg.chat.id if hasattr(message_or_msg, 'chat') else call.from_user.id
    if call:
        tg_id = call.from_user.id

    user = await get_user(tg_id)
    if not user:
        if call:
            await call.answer("❌ Пользователь не найден", show_alert=True)
        return

    if user.is_banned:
        if call:
            await call.answer("🚫 Аккаунт заблокирован", show_alert=True)
        return

    min_bet = float(await get_setting("min_bet", "0.1"))
    max_bet = float(await get_setting("max_bet", "100.0"))

    if amount < min_bet:
        msg = f"❌ Минимальная ставка: {min_bet} TON"
        if call:
            await call.answer(msg, show_alert=True)
        else:
            await message_or_msg.answer(msg)
        return

    if amount > max_bet:
        msg = f"❌ Максимальная ставка: {max_bet} TON"
        if call:
            await call.answer(msg, show_alert=True)
        else:
            await message_or_msg.answer(msg)
        return

    if user.balance < amount:
        msg = f"❌ Недостаточно средств! Баланс: {user.balance:.4f} TON"
        if call:
            await call.answer(msg, show_alert=True)
        else:
            await message_or_msg.answer(msg)
        return

    # Deduct bet
    await update_balance(tg_id, -amount)

    # Spin
    result = spin_roulette()
    win_amount, win_desc = calculate_roulette_win(bet_type, bet_value, amount, result)

    if win_amount > 0:
        await update_balance(tg_id, win_amount)

    # Update history
    if tg_id not in ROULETTE_HISTORY:
        ROULETTE_HISTORY[tg_id] = []
    ROULETTE_HISTORY[tg_id].append(result)
    ROULETTE_HISTORY[tg_id] = ROULETTE_HISTORY[tg_id][-15:]

    # Log bet
    await log_bet(tg_id, "roulette", amount, win_amount,
                  f"{bet_type}:{bet_value}->result:{result}")

    user_after = await get_user(tg_id)
    result_text = format_roulette_result(result, win_amount, amount, win_desc, ROULETTE_HISTORY[tg_id])
    result_text += f"\n\n💰 Баланс: {user_after.balance:.4f} TON"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Снова", callback_data="game_roulette"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu"),
    )
    kb = builder.as_markup()

    if call:
        await call.message.edit_text(result_text, reply_markup=kb)
        await call.answer()
    else:
        await message_or_msg.answer(result_text, reply_markup=kb)
