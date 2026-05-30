from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎰 Рулетка", callback_data="game_roulette"),
        InlineKeyboardButton(text="💣 Мины", callback_data="game_mines"),
    )
    builder.row(
        InlineKeyboardButton(text="🗼 Башня", callback_data="game_tower"),
    )
    builder.row(
        InlineKeyboardButton(text="💰 Баланс", callback_data="balance"),
        InlineKeyboardButton(text="💳 Пополнить", callback_data="deposit"),
    )
    builder.row(
        InlineKeyboardButton(text="📤 Вывод", callback_data="withdraw"),
        InlineKeyboardButton(text="👥 Рефералы", callback_data="referral"),
    )
    builder.row(
        InlineKeyboardButton(text="📊 История ставок", callback_data="bet_history"),
    )
    return builder.as_markup()


def deposit_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🤖 Через @send", callback_data="dep_send"),
        InlineKeyboardButton(text="🚀 xRocket", callback_data="dep_xrocket"),
    )
    builder.row(
        InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="dep_stars"),
        InlineKeyboardButton(text="💎 TON кошелёк", callback_data="dep_ton"),
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))
    return builder.as_markup()


def back_kb(callback: str = "main_menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data=callback)]
    ])


def roulette_bet_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔴 Красное", callback_data="rl_color_red"),
        InlineKeyboardButton(text="⚫ Чёрное", callback_data="rl_color_black"),
    )
    builder.row(
        InlineKeyboardButton(text="➕ Чётное", callback_data="rl_parity_even"),
        InlineKeyboardButton(text="➖ Нечётное", callback_data="rl_parity_odd"),
    )
    builder.row(
        InlineKeyboardButton(text="📉 1-18", callback_data="rl_half_low"),
        InlineKeyboardButton(text="📈 19-36", callback_data="rl_half_high"),
    )
    builder.row(
        InlineKeyboardButton(text="1️⃣ Дюжина 1", callback_data="rl_dozen_1"),
        InlineKeyboardButton(text="2️⃣ Дюжина 2", callback_data="rl_dozen_2"),
        InlineKeyboardButton(text="3️⃣ Дюжина 3", callback_data="rl_dozen_3"),
    )
    builder.row(
        InlineKeyboardButton(text="Колонка 1", callback_data="rl_column_1"),
        InlineKeyboardButton(text="Колонка 2", callback_data="rl_column_2"),
        InlineKeyboardButton(text="Колонка 3", callback_data="rl_column_3"),
    )
    builder.row(
        InlineKeyboardButton(text="🎯 Число (0-36)", callback_data="rl_number"),
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))
    return builder.as_markup()


def roulette_bet_amount_kb(bet_type: str, bet_value: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    amounts = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0]
    for i in range(0, len(amounts), 3):
        row_amounts = amounts[i:i+3]
        builder.row(*[
            InlineKeyboardButton(text=f"{a} TON", callback_data=f"rl_bet_{bet_type}_{bet_value}_{a}")
            for a in row_amounts
        ])
    builder.row(InlineKeyboardButton(text="✏️ Своя сумма", callback_data=f"rl_custom_{bet_type}_{bet_value}"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="game_roulette"))
    return builder.as_markup()


def mines_setup_kb(mines_count: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➖", callback_data=f"mines_mines_minus"),
        InlineKeyboardButton(text=f"💣 Мин: {mines_count}", callback_data="mines_mines_info"),
        InlineKeyboardButton(text="➕", callback_data=f"mines_mines_plus"),
    )
    amounts = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0]
    for i in range(0, len(amounts), 3):
        row_amounts = amounts[i:i+3]
        builder.row(*[
            InlineKeyboardButton(text=f"{a} TON", callback_data=f"mines_start_{mines_count}_{a}")
            for a in row_amounts
        ])
    builder.row(InlineKeyboardButton(text="✏️ Своя ставка", callback_data=f"mines_custom_{mines_count}"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))
    return builder.as_markup()


def mines_field_kb(state: dict) -> InlineKeyboardMarkup:
    """5x5 grid with revealed cells disabled"""
    builder = InlineKeyboardBuilder()
    revealed = state.get("revealed", [])
    opened = len(revealed)
    from games.mines import get_mines_multiplier
    mult = get_mines_multiplier(state["mines_count"], opened)
    potential = round(state["bet"] * mult, 4)

    for row in range(5):
        row_buttons = []
        for col in range(5):
            idx = row * 5 + col
            if idx in revealed:
                if state["field"][idx]:
                    row_buttons.append(InlineKeyboardButton(text="💣", callback_data="mines_noop"))
                else:
                    row_buttons.append(InlineKeyboardButton(text="💎", callback_data="mines_noop"))
            else:
                row_buttons.append(InlineKeyboardButton(text="⬛", callback_data=f"mines_open_{idx}"))
        builder.row(*row_buttons)

    if opened > 0:
        builder.row(
            InlineKeyboardButton(text=f"💰 Забрать {potential:.4f} TON", callback_data="mines_cashout")
        )
    builder.row(InlineKeyboardButton(text="❌ Сдаться", callback_data="mines_forfeit"))
    return builder.as_markup()


def tower_setup_kb(mines_per_floor: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➖", callback_data="tower_mines_minus"),
        InlineKeyboardButton(text=f"💣 Мин/этаж: {mines_per_floor}", callback_data="tower_mines_info"),
        InlineKeyboardButton(text="➕", callback_data="tower_mines_plus"),
    )
    amounts = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0]
    for i in range(0, len(amounts), 3):
        row_amounts = amounts[i:i+3]
        builder.row(*[
            InlineKeyboardButton(text=f"{a} TON", callback_data=f"tower_start_{mines_per_floor}_{a}")
            for a in row_amounts
        ])
    builder.row(InlineKeyboardButton(text="✏️ Своя ставка", callback_data=f"tower_custom_{mines_per_floor}"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))
    return builder.as_markup()


def tower_floor_kb(state: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    current_floor = state["current_floor"]
    mines_per_floor = state["mines_per_floor"]
    bet = state["bet"]

    from games.tower import get_tower_multiplier
    mult = get_tower_multiplier(current_floor, mines_per_floor)
    potential = round(bet * mult, 4)

    # 3 position buttons
    builder.row(
        InlineKeyboardButton(text="1️⃣", callback_data="tower_pick_0"),
        InlineKeyboardButton(text="2️⃣", callback_data="tower_pick_1"),
        InlineKeyboardButton(text="3️⃣", callback_data="tower_pick_2"),
    )

    if current_floor > 0:
        builder.row(
            InlineKeyboardButton(text=f"💰 Забрать {potential:.4f} TON", callback_data="tower_cashout")
        )
    builder.row(InlineKeyboardButton(text="❌ Сдаться", callback_data="tower_forfeit"))
    return builder.as_markup()


def admin_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👥 Пользователи", callback_data="adm_users"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats"),
    )
    builder.row(
        InlineKeyboardButton(text="💸 Заявки на вывод", callback_data="adm_withdrawals"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="adm_settings"),
    )
    builder.row(
        InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_broadcast"),
        InlineKeyboardButton(text="💰 Платежи лог", callback_data="adm_payments"),
    )
    return builder.as_markup()


def admin_withdraw_kb(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"adm_wd_approve_{request_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_wd_reject_{request_id}"),
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="adm_withdrawals")]
    ])


def stars_amounts_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # Stars: 50, 100, 250, 500, 1000 stars
    stars = [50, 100, 250, 500, 1000]
    for i in range(0, len(stars), 2):
        row = stars[i:i+2]
        builder.row(*[
            InlineKeyboardButton(text=f"⭐ {s} Stars", callback_data=f"stars_buy_{s}")
            for s in row
        ])
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="deposit"))
    return builder.as_markup()
