import random
import json

ROULETTE_NUMBERS = list(range(0, 37))

RED_NUMBERS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
BLACK_NUMBERS = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}

DOZENS = {
    "1": list(range(1, 13)),
    "2": list(range(13, 25)),
    "3": list(range(25, 37)),
}

COLUMNS = {
    "1": [1,4,7,10,13,16,19,22,25,28,31,34],
    "2": [2,5,8,11,14,17,20,23,26,29,32,35],
    "3": [3,6,9,12,15,18,21,24,27,30,33,36],
}

ROULETTE_HISTORY = {}  # tg_id -> list of last results


def spin_roulette():
    return random.randint(0, 36)


def get_number_color(n: int) -> str:
    if n == 0:
        return "🟢"
    elif n in RED_NUMBERS:
        return "🔴"
    else:
        return "⚫"


def calculate_roulette_win(bet_type: str, bet_value: str, bet_amount: float, result: int) -> tuple[float, str]:
    """Returns (win_amount, description). win_amount=0 means loss."""
    win = 0.0
    desc = ""

    if bet_type == "number":
        num = int(bet_value)
        if result == num:
            win = bet_amount * 36
            desc = f"Число {num} выпало! ×36"
    elif bet_type == "color":
        if bet_value == "red" and result in RED_NUMBERS:
            win = bet_amount * 2
            desc = "Красное! ×2"
        elif bet_value == "black" and result in BLACK_NUMBERS:
            win = bet_amount * 2
            desc = "Чёрное! ×2"
    elif bet_type == "parity":
        if result != 0:
            if bet_value == "even" and result % 2 == 0:
                win = bet_amount * 2
                desc = "Чётное! ×2"
            elif bet_value == "odd" and result % 2 != 0:
                win = bet_amount * 2
                desc = "Нечётное! ×2"
    elif bet_type == "dozen":
        if result in DOZENS.get(bet_value, []):
            win = bet_amount * 3
            desc = f"Дюжина {bet_value}! ×3"
    elif bet_type == "column":
        if result in COLUMNS.get(bet_value, []):
            win = bet_amount * 3
            desc = f"Колонка {bet_value}! ×3"
    elif bet_type == "half":
        if result != 0:
            if bet_value == "low" and 1 <= result <= 18:
                win = bet_amount * 2
                desc = "Малые (1-18)! ×2"
            elif bet_value == "high" and 19 <= result <= 36:
                win = bet_amount * 2
                desc = "Большие (19-36)! ×2"

    return round(win, 6), desc


def format_roulette_result(result: int, win: float, bet_amount: float, desc: str, history: list) -> str:
    color = get_number_color(result)
    profit = win - bet_amount

    history_str = " ".join([f"{get_number_color(h)}{h}" for h in history[-8:]])

    if win > 0:
        status = f"🎉 ВЫИГРЫШ! +{win:.4f} TON\n{desc}"
    else:
        status = f"😢 Проигрыш... -{bet_amount:.4f} TON"

    return (
        f"🎰 ═══════════════════\n"
        f"    РУЛЕТКА LEPS\n"
        f"════════════════════\n\n"
        f"🎯 Выпало: {color} {result}\n\n"
        f"{status}\n\n"
        f"📊 История:\n{history_str}\n"
        f"════════════════════"
    )
