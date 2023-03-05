from parsing.gamestate import ParsedGameState


def evaluate_gamestate_for_unit(gs: ParsedGameState, unit_id: str) -> float:
    for su in gs.units:
        if su.unit_id == unit_id:
            unit = su
            break
    unit_score = 0
    unit_score += unit.hp * 100
    unit_score += unit.blast_r * 10
    dist_to_center = abs(unit.pos.x - gs.w // 2) + abs(unit.pos.y - gs.h // 2)  # TODO replace with endfire-related calc
    unit_score += (15 - dist_to_center) * 0.5
    return unit_score
