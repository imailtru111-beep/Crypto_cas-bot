import random
import json
import math

FIELD_SIZE = 25  # 5x5


def create_mines_field(mines_count: int) -> list:
    """Returns list of 25 booleans, True = mine"""
    field = [False] * FIELD_SIZE
    mine_positions = random.sample(range(FIELD_SIZE), mines_count)
    for pos in mine_positions:
        field[pos] = True
    return field


def get_mines_multiplier(mines_count: int, opened: int) -> float:
    """Dynamic multiplier based on mines count and opened cells"""
    safe = FIELD_SIZE - mines_count
    if opened >= safe:
        return 0
    # House edge ~3%
    house_edge = 0.97
    mult = 1.0
    for i in range(opened):
        remaining = FIELD_SIZE - i
        safe_remaining = safe - i
        mult *= remaining / safe_remaining
    return round(mult * house_edge, 4)


def format_mines_field(field: list, revealed: list, game_over: bool = False) -> str:
    """field=mine positions, revealed=list of opened indices"""
    rows = []
    for row in range(5):
        cells = []
        for col in range(5):
            idx = row * 5 + col
            if idx in revealed:
                if field[idx]:
                    cells.append("💣")
                else:
                    cells.append("💎")
            elif game_over and field[idx]:
                cells.append("💥")
            else:
                cells.append("⬛")
        rows.append(" ".join(cells))
    return "\n".join(rows)


def format_mines_game(state: dict, game_over: bool = False, cashed_out: bool = False) -> str:
    field_str = format_mines_field(state["field"], state["revealed"], game_over)
    mines = state["mines_count"]
    opened = len(state["revealed"])
    bet = state["bet"]
    mult = get_mines_multiplier(mines, opened)
    potential = round(bet * mult, 4)

    if game_over:
        header = "💣 БУМ! МИНА!\n"
        profit_line = f"😢 Потеряно: -{bet:.4f} TON"
    elif cashed_out:
        win = state.get("cashed_win", potential)
        header = "💰 ЗАБРАЛ ВЫИГРЫШ!\n"
        profit_line = f"🎉 Выигрыш: +{win:.4f} TON"
    else:
        header = ""
        profit_line = f"💰 Потенциал: {potential:.4f} TON (×{mult})"

    return (
        f"💣 ═══════════════════\n"
        f"    МИНЫ LEPS\n"
        f"════════════════════\n\n"
        f"{header}"
        f"💣 Мин: {mines} | 💎 Открыто: {opened}\n"
        f"🎯 Ставка: {bet:.4f} TON\n"
        f"{profit_line}\n\n"
        f"{field_str}\n"
        f"════════════════════"
    )
