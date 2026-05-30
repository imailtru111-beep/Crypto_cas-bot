import json
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.models import get_user, update_balance, log_bet, get_setting, async_session
from database.models import GameSession
from games.mines import create_mines_field, get_mines_multiplier, format_mines_game
from utils.keyboards import mines_setup_kb, mines_field_kb, back_kb, main_menu_kb
from sqlalchemy import select

router = Router()

MINES_SETUP = {}  # tg_id -> mines_count


class MinesStates(StatesGroup):
    waiting_custom_bet = State()


@router.callback_query(F.data == "game_mines")
async def cb_mines(call: CallbackQuery, state: FSMContext):
    await state.clear()
    tg_id = call.from_user.id
    mines_count = MINES_SETUP.get(tg_id, 3)

    text = (
        f"💣 ═══════════════════\n"
        f"      МИНЫ LEPS\n"
        f"════════════════════\n\n"
        f"🎮 Поле 5×5 (25 клеток)\n"
        f"💣 Выбери кол-во мин (2-15)\n"
        f"💎 Открывай клетки без мин!\n\n"
        f"💡 Забери выигрыш в любой момент\n"
        f"════════════════════"
    )
    await call.message.edit_text(text, reply_markup=mines_setup_kb(mines_count))
    await call.answer()


@router.callback_query(F.data == "mines_mines_minus")
async def cb_mines_minus(call: CallbackQuery):
    tg_id = call.from_user.id
    current = MINES_SETUP.get(tg_id, 3)
    MINES_SETUP[tg_id] = max(2, current - 1)
    await call.message.edit_reply_markup(reply_markup=mines_setup_kb(MINES_SETUP[tg_id]))
    await call.answer(f"💣 Мин: {MINES_SETUP[tg_id]}")


@router.callback_query(F.data == "mines_mines_plus")
async def cb_mines_plus(call: CallbackQuery):
    tg_id = call.from_user.id
    current = MINES_SETUP.get(tg_id, 3)
    MINES_SETUP[tg_id] = min(15, current + 1)
    await call.message.edit_reply_markup(reply_markup=mines_setup_kb(MINES_SETUP[tg_id]))
    await call.answer(f"💣 Мин: {MINES_SETUP[tg_id]}")


@router.callback_query(F.data == "mines_mines_info")
async def cb_mines_info(call: CallbackQuery):
    await call.answer()


@router.callback_query(F.data.startswith("mines_custom_"))
async def cb_mines_custom(call: CallbackQuery, state: FSMContext):
    mines_count = int(call.data.split("_")[2])
    await state.update_data(mines_count=mines_count)
    await state.set_state(MinesStates.waiting_custom_bet)
    await call.message.edit_text(
        f"✏️ Мин: {mines_count}\nВведи сумму ставки в TON:",
        reply_markup=back_kb("game_mines")
    )
    await call.answer()


@router.message(MinesStates.waiting_custom_bet)
async def process_mines_custom(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное число:")
        return

    data = await state.get_data()
    await state.clear()
    await _start_mines_game(message, data["mines_count"], amount)


@router.callback_query(F.data.startswith("mines_start_"))
async def cb_mines_start(call: CallbackQuery):
    # mines_start_{mines}_{amount}
    parts = call.data.split("_")
    mines_count = int(parts[2])
    amount = float(parts[3])
    await _start_mines_game(call.message, mines_count, amount, call)


async def _start_mines_game(message_or_msg, mines_count: int, amount: float, call=None):
    tg_id = call.from_user.id if call else message_or_msg.chat.id

    user = await get_user(tg_id)
    if not user or user.is_banned:
        if call:
            await call.answer("❌ Ошибка", show_alert=True)
        return

    min_bet = float(await get_setting("min_bet", "0.1"))
    max_bet = float(await get_setting("max_bet", "100.0"))

    if amount < min_bet or amount > max_bet:
        msg = f"❌ Ставка: {min_bet}-{max_bet} TON"
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

    # Close any existing session
    async with async_session() as session:
        result = await session.execute(
            select(GameSession).where(
                GameSession.tg_id == tg_id,
                GameSession.game == "mines",
                GameSession.is_active == True
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.is_active = False
            await session.commit()

    # Deduct bet
    await update_balance(tg_id, -amount)

    # Create game
    field = create_mines_field(mines_count)
    state_data = {
        "field": field,
        "revealed": [],
        "mines_count": mines_count,
        "bet": amount,
    }

    async with async_session() as session:
        gs = GameSession(tg_id=tg_id, game="mines", state=json.dumps(state_data))
        session.add(gs)
        await session.commit()

    game_text = format_mines_game(state_data)
    game_text += f"\n💰 Баланс: {user.balance - amount:.4f} TON"

    if call:
        await call.message.edit_text(game_text, reply_markup=mines_field_kb(state_data))
        await call.answer()
    else:
        await message_or_msg.answer(game_text, reply_markup=mines_field_kb(state_data))


@router.callback_query(F.data.startswith("mines_open_"))
async def cb_mines_open(call: CallbackQuery):
    idx = int(call.data.split("_")[2])
    tg_id = call.from_user.id

    async with async_session() as session:
        result = await session.execute(
            select(GameSession).where(
                GameSession.tg_id == tg_id,
                GameSession.game == "mines",
                GameSession.is_active == True
            )
        )
        gs = result.scalar_one_or_none()
        if not gs:
            await call.answer("❌ Игра не найдена", show_alert=True)
            return

        state_data = json.loads(gs.state)
        if idx in state_data["revealed"]:
            await call.answer("Уже открыто!")
            return

        state_data["revealed"].append(idx)

        if state_data["field"][idx]:  # Mine!
            gs.is_active = False
            gs.state = json.dumps(state_data)
            await session.commit()

            await log_bet(tg_id, "mines", state_data["bet"], 0,
                         f"mines:{state_data['mines_count']},opened:{len(state_data['revealed'])-1},hit_mine")

            user = await get_user(tg_id)
            game_text = format_mines_game(state_data, game_over=True)
            game_text += f"\n\n💰 Баланс: {user.balance:.4f} TON"

            from aiogram.utils.keyboard import InlineKeyboardBuilder
            from aiogram.types import InlineKeyboardButton
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="🔄 Снова", callback_data="game_mines"),
                InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu"),
            )
            await call.message.edit_text(game_text, reply_markup=builder.as_markup())
            await call.answer("💣 Мина!")
        else:
            # Safe!
            mines_count = state_data["mines_count"]
            opened = len(state_data["revealed"])
            safe_total = 25 - mines_count

            if opened >= safe_total:
                # Win all!
                mult = get_mines_multiplier(mines_count, opened)
                win = round(state_data["bet"] * mult, 6)
                await update_balance(tg_id, win)
                gs.is_active = False
                gs.state = json.dumps(state_data)
                await session.commit()

                await log_bet(tg_id, "mines", state_data["bet"], win,
                             f"mines:{mines_count},cleared_all")

                state_data["cashed_win"] = win
                user = await get_user(tg_id)
                game_text = format_mines_game(state_data, cashed_out=True)
                game_text += f"\n\n💰 Баланс: {user.balance:.4f} TON"

                from aiogram.utils.keyboard import InlineKeyboardBuilder
                from aiogram.types import InlineKeyboardButton
                builder = InlineKeyboardBuilder()
                builder.row(
                    InlineKeyboardButton(text="🔄 Снова", callback_data="game_mines"),
                    InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu"),
                )
                await call.message.edit_text(game_text, reply_markup=builder.as_markup())
                await call.answer(f"🎉 Очистил поле! +{win:.4f} TON")
            else:
                gs.state = json.dumps(state_data)
                await session.commit()

                game_text = format_mines_game(state_data)
                mult = get_mines_multiplier(mines_count, opened)
                potential = round(state_data["bet"] * mult, 4)
                game_text += f"\n\n💎 Потенциал: {potential:.4f} TON"
                await call.message.edit_text(game_text, reply_markup=mines_field_kb(state_data))
                await call.answer(f"💎 Безопасно! ×{mult}")


@router.callback_query(F.data == "mines_cashout")
async def cb_mines_cashout(call: CallbackQuery):
    tg_id = call.from_user.id

    async with async_session() as session:
        result = await session.execute(
            select(GameSession).where(
                GameSession.tg_id == tg_id,
                GameSession.game == "mines",
                GameSession.is_active == True
            )
        )
        gs = result.scalar_one_or_none()
        if not gs:
            await call.answer("❌ Игра не найдена", show_alert=True)
            return

        state_data = json.loads(gs.state)
        opened = len(state_data["revealed"])
        if opened == 0:
            await call.answer("Нужно открыть хотя бы 1 клетку!", show_alert=True)
            return

        mult = get_mines_multiplier(state_data["mines_count"], opened)
        win = round(state_data["bet"] * mult, 6)
        state_data["cashed_win"] = win

        gs.is_active = False
        gs.state = json.dumps(state_data)
        await session.commit()

    await update_balance(tg_id, win)
    await log_bet(tg_id, "mines", state_data["bet"], win,
                 f"mines:{state_data['mines_count']},opened:{opened},cashout")

    user = await get_user(tg_id)
    game_text = format_mines_game(state_data, cashed_out=True)
    game_text += f"\n\n💰 Баланс: {user.balance:.4f} TON"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Снова", callback_data="game_mines"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu"),
    )
    await call.message.edit_text(game_text, reply_markup=builder.as_markup())
    await call.answer(f"💰 Забрал {win:.4f} TON!")


@router.callback_query(F.data == "mines_forfeit")
async def cb_mines_forfeit(call: CallbackQuery):
    tg_id = call.from_user.id
    async with async_session() as session:
        result = await session.execute(
            select(GameSession).where(
                GameSession.tg_id == tg_id,
                GameSession.game == "mines",
                GameSession.is_active == True
            )
        )
        gs = result.scalar_one_or_none()
        if gs:
            state_data = json.loads(gs.state)
            gs.is_active = False
            await session.commit()
            await log_bet(tg_id, "mines", state_data["bet"], 0, "forfeit")

    await call.message.edit_text("❌ Игра прекращена.", reply_markup=main_menu_kb())
    await call.answer()


@router.callback_query(F.data == "mines_noop")
async def cb_mines_noop(call: CallbackQuery):
    await call.answer()
