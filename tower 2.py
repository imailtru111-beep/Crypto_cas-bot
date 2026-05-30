import json
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.models import get_user, update_balance, log_bet, get_setting, async_session
from database.models import GameSession
from games.tower import (
    TOWER_FLOORS, POSITIONS_PER_FLOOR,
    get_tower_multiplier, generate_floor, format_tower_game
)
from utils.keyboards import tower_setup_kb, tower_floor_kb, back_kb, main_menu_kb
from sqlalchemy import select

router = Router()

TOWER_SETUP = {}  # tg_id -> mines_per_floor


class TowerStates(StatesGroup):
    waiting_custom_bet = State()


@router.callback_query(F.data == "game_tower")
async def cb_tower(call: CallbackQuery, state: FSMContext):
    await state.clear()
    tg_id = call.from_user.id
    mines = TOWER_SETUP.get(tg_id, 1)

    text = (
        f"🗼 ═══════════════════\n"
        f"      БАШНЯ LEPS\n"
        f"════════════════════\n\n"
        f"🎮 10 этажей, 3 позиции\n"
        f"💣 Выбери мины на этаж (1-2)\n"
        f"🏆 Взбирайся выше!\n\n"
        f"💡 Забери выигрыш после любого этажа\n"
        f"════════════════════"
    )
    await call.message.edit_text(text, reply_markup=tower_setup_kb(mines))
    await call.answer()


@router.callback_query(F.data == "tower_mines_minus")
async def cb_tower_minus(call: CallbackQuery):
    tg_id = call.from_user.id
    current = TOWER_SETUP.get(tg_id, 1)
    TOWER_SETUP[tg_id] = max(1, current - 1)
    await call.message.edit_reply_markup(reply_markup=tower_setup_kb(TOWER_SETUP[tg_id]))
    await call.answer(f"💣 Мин/этаж: {TOWER_SETUP[tg_id]}")


@router.callback_query(F.data == "tower_mines_plus")
async def cb_tower_plus(call: CallbackQuery):
    tg_id = call.from_user.id
    current = TOWER_SETUP.get(tg_id, 1)
    TOWER_SETUP[tg_id] = min(2, current + 1)
    await call.message.edit_reply_markup(reply_markup=tower_setup_kb(TOWER_SETUP[tg_id]))
    await call.answer(f"💣 Мин/этаж: {TOWER_SETUP[tg_id]}")


@router.callback_query(F.data == "tower_mines_info")
async def cb_tower_info(call: CallbackQuery):
    await call.answer()


@router.callback_query(F.data.startswith("tower_custom_"))
async def cb_tower_custom(call: CallbackQuery, state: FSMContext):
    mines = int(call.data.split("_")[2])
    await state.update_data(mines_per_floor=mines)
    await state.set_state(TowerStates.waiting_custom_bet)
    await call.message.edit_text(
        f"✏️ Мин/этаж: {mines}\nВведи ставку в TON:",
        reply_markup=back_kb("game_tower")
    )
    await call.answer()


@router.message(TowerStates.waiting_custom_bet)
async def process_tower_custom(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное число:")
        return

    data = await state.get_data()
    await state.clear()
    await _start_tower_game(message, data["mines_per_floor"], amount)


@router.callback_query(F.data.startswith("tower_start_"))
async def cb_tower_start(call: CallbackQuery):
    parts = call.data.split("_")
    mines = int(parts[2])
    amount = float(parts[3])
    await _start_tower_game(call.message, mines, amount, call)


async def _start_tower_game(message_or_msg, mines_per_floor: int, amount: float, call=None):
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
        msg = f"❌ Недостаточно средств!"
        if call:
            await call.answer(msg, show_alert=True)
        else:
            await message_or_msg.answer(msg)
        return

    # Close existing
    async with async_session() as session:
        result = await session.execute(
            select(GameSession).where(
                GameSession.tg_id == tg_id,
                GameSession.game == "tower",
                GameSession.is_active == True
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.is_active = False
            await session.commit()

    await update_balance(tg_id, -amount)

    # Pre-generate all floors
    all_floors = [generate_floor(mines_per_floor) for _ in range(TOWER_FLOORS)]

    state_data = {
        "current_floor": 0,
        "mines_per_floor": mines_per_floor,
        "bet": amount,
        "history": [],
        "all_floors": all_floors,
        "floor_results": {},
    }

    async with async_session() as session:
        gs = GameSession(tg_id=tg_id, game="tower", state=json.dumps(state_data))
        session.add(gs)
        await session.commit()

    game_text = format_tower_game(state_data)
    game_text += f"\n\n💰 Баланс: {user.balance - amount:.4f} TON"

    if call:
        await call.message.edit_text(game_text, reply_markup=tower_floor_kb(state_data))
        await call.answer()
    else:
        await message_or_msg.answer(game_text, reply_markup=tower_floor_kb(state_data))


@router.callback_query(F.data.startswith("tower_pick_"))
async def cb_tower_pick(call: CallbackQuery):
    position = int(call.data.split("_")[2])
    tg_id = call.from_user.id

    async with async_session() as session:
        result = await session.execute(
            select(GameSession).where(
                GameSession.tg_id == tg_id,
                GameSession.game == "tower",
                GameSession.is_active == True
            )
        )
        gs = result.scalar_one_or_none()
        if not gs:
            await call.answer("❌ Игра не найдена", show_alert=True)
            return

        state_data = json.loads(gs.state)
        current_floor = state_data["current_floor"]
        floor_layout = state_data["all_floors"][current_floor]

        # Save result for display
        state_data["floor_results"][str(current_floor)] = floor_layout
        state_data["history"].append(position)

        if floor_layout[position]:  # Mine!
            gs.is_active = False
            gs.state = json.dumps(state_data)
            await session.commit()

            await log_bet(tg_id, "tower", state_data["bet"], 0,
                         f"mines_per_floor:{state_data['mines_per_floor']},floor:{current_floor}")

            user = await get_user(tg_id)
            game_text = format_tower_game(state_data, game_over=True)
            game_text += f"\n\n💰 Баланс: {user.balance:.4f} TON"

            from aiogram.utils.keyboard import InlineKeyboardBuilder
            from aiogram.types import InlineKeyboardButton
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="🔄 Снова", callback_data="game_tower"),
                InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu"),
            )
            await call.message.edit_text(game_text, reply_markup=builder.as_markup())
            await call.answer("💣 Мина!")
        else:
            # Safe! Move up
            state_data["current_floor"] += 1
            gs.state = json.dumps(state_data)
            await session.commit()

            new_floor = state_data["current_floor"]
            mult = get_tower_multiplier(new_floor, state_data["mines_per_floor"])
            potential = round(state_data["bet"] * mult, 4)

            if new_floor >= TOWER_FLOORS:
                # Completed all floors!
                win = potential
                await update_balance(tg_id, win)
                gs.is_active = False
                await session.commit()

                await log_bet(tg_id, "tower", state_data["bet"], win,
                             f"completed_all_floors")

                state_data["cashed_win"] = win
                user = await get_user(tg_id)
                game_text = format_tower_game(state_data, cashed_out=True)
                game_text += f"\n\n💰 Баланс: {user.balance:.4f} TON"

                from aiogram.utils.keyboard import InlineKeyboardBuilder
                from aiogram.types import InlineKeyboardButton
                builder = InlineKeyboardBuilder()
                builder.row(
                    InlineKeyboardButton(text="🔄 Снова", callback_data="game_tower"),
                    InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu"),
                )
                await call.message.edit_text(game_text, reply_markup=builder.as_markup())
                await call.answer(f"🏆 Башня покорена! +{win:.4f} TON")
            else:
                game_text = format_tower_game(state_data)
                game_text += f"\n\n💰 Потенциал: {potential:.4f} TON"
                await call.message.edit_text(game_text, reply_markup=tower_floor_kb(state_data))
                await call.answer(f"✅ Этаж {new_floor} пройден! ×{mult}")


@router.callback_query(F.data == "tower_cashout")
async def cb_tower_cashout(call: CallbackQuery):
    tg_id = call.from_user.id

    async with async_session() as session:
        result = await session.execute(
            select(GameSession).where(
                GameSession.tg_id == tg_id,
                GameSession.game == "tower",
                GameSession.is_active == True
            )
        )
        gs = result.scalar_one_or_none()
        if not gs:
            await call.answer("❌ Игра не найдена", show_alert=True)
            return

        state_data = json.loads(gs.state)
        current_floor = state_data["current_floor"]
        if current_floor == 0:
            await call.answer("Нужно пройти хотя бы 1 этаж!", show_alert=True)
            return

        mult = get_tower_multiplier(current_floor, state_data["mines_per_floor"])
        win = round(state_data["bet"] * mult, 6)
        state_data["cashed_win"] = win

        gs.is_active = False
        gs.state = json.dumps(state_data)
        await session.commit()

    await update_balance(tg_id, win)
    await log_bet(tg_id, "tower", state_data["bet"], win,
                 f"cashout_floor:{current_floor}")

    user = await get_user(tg_id)
    game_text = format_tower_game(state_data, cashed_out=True)
    game_text += f"\n\n💰 Баланс: {user.balance:.4f} TON"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Снова", callback_data="game_tower"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu"),
    )
    await call.message.edit_text(game_text, reply_markup=builder.as_markup())
    await call.answer(f"💰 Забрал {win:.4f} TON!")


@router.callback_query(F.data == "tower_forfeit")
async def cb_tower_forfeit(call: CallbackQuery):
    tg_id = call.from_user.id
    async with async_session() as session:
        result = await session.execute(
            select(GameSession).where(
                GameSession.tg_id == tg_id,
                GameSession.game == "tower",
                GameSession.is_active == True
            )
        )
        gs = result.scalar_one_or_none()
        if gs:
            state_data = json.loads(gs.state)
            gs.is_active = False
            await session.commit()
            await log_bet(tg_id, "tower", state_data["bet"], 0, "forfeit")

    await call.message.edit_text("❌ Игра прекращена.", reply_markup=main_menu_kb())
    await call.answer()
