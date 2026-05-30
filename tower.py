import random

TOWER_FLOORS = 10
POSITIONS_PER_FLOOR = 3


def get_tower_multiplier(floor: int, mines_per_floor: int) -> float:
    """Multiplier after completing `floor` floors (1-based)"""
    safe = POSITIONS_PER_FLOOR - mines_per_floor
    house_edge = 0.97
    mult = 1.0
    for _ in range(floor):
        mult *= POSITIONS_PER_FLOOR / safe
    return round(mult * house_edge, 4)


def generate_floor(mines_per_floor: int) -> list:
    """Returns list of 3: True=mine, False=safe"""
    floor = [False] * POSITIONS_PER_FLOOR
    mine_positions = random.sample(range(POSITIONS_PER_FLOOR), mines_per_floor)
    for pos in mine_positions:
        floor[pos] = True
    return floor


def format_tower_game(state: dict, game_over: bool = False, cashed_out: bool = False) -> str:
    current_floor = state["current_floor"]  # 0-based, starts at 0
    mines_per_floor = state["mines_per_floor"]
    bet = state["bet"]
    history = state.get("history", [])  # list of chosen positions per floor

    mult = get_tower_multiplier(current_floor, mines_per_floor) if current_floor > 0 else 1.0
    potential = round(bet * mult, 4)

    lines = []

    if game_over:
        header = f"💣 БУМ! МИНА НА ЭТАЖЕ {current_floor + 1}!\n😢 Потеряно: -{bet:.4f} TON\n\n"
    elif cashed_out:
        win = state.get("cashed_win", potential)
        header = f"💰 ЗАБРАЛ ВЫИГРЫШ!\n🎉 Выигрыш: +{win:.4f} TON\n\n"
    else:
        header = f"🎯 Ставка: {bet:.4f} TON\n💰 Потенциал: {potential:.4f} TON (×{mult})\n\n"

    # Draw tower from top to bottom
    for floor_idx in range(TOWER_FLOORS - 1, -1, -1):
        floor_num = floor_idx + 1
        if floor_idx < current_floor:
            # Passed floor
            chosen = history[floor_idx] if floor_idx < len(history) else -1
            floor_state = state.get("floor_results", {}).get(str(floor_idx), [False]*3)
            cells = []
            for i in range(3):
                if floor_state[i]:  # mine
                    cells.append("💣" if i == chosen else "💥")
                else:
                    cells.append("✅" if i == chosen else "⬜")
            line = f"{'✅' if floor_idx < current_floor else '▶️'} {floor_num:2d} | {' '.join(cells)}"
        elif floor_idx == current_floor and not game_over and not cashed_out:
            # Current floor - active
            line = f"▶️ {floor_num:2d} | 🟦 🟦 🟦  ← ВЫБЕРИ"
        else:
            line = f"   {floor_num:2d} | ⬜ ⬜ ⬜"
        lines.append(line)

    tower_str = "\n".join(lines)

    return (
        f"🗼 ═══════════════════\n"
        f"    БАШНЯ LEPS\n"
        f"════════════════════\n\n"
        f"{header}"
        f"💣 Мин/этаж: {mines_per_floor}\n\n"
        f"{tower_str}\n"
        f"════════════════════"
    )
