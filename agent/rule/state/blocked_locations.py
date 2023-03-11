import math

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rule.state.rule_policy_state import RulePolicyState
from utils.game_utils import manhattan_distance
from utils.policy import debug_print


def compute_blocked_locations(state: 'RulePolicyState'):
    for unit in state.parser.my_units:
        if unit.stunned_last_tick >= state.tick_number - 1:
            continue
        if unit.id in state.unit_id_to_target_pos and unit.pos != state.unit_id_to_target_pos[unit.id]:
            state.blocked_locations.add(state.unit_id_to_target_pos[unit.id])
    state.unit_id_to_target_pos.clear()
    debug_print(state, "blocked locations before filter: ", state.blocked_locations)
    if not state.blocked_locations:
        return

    filtered_blocked_locations = set()
    blocked_danger_map = state.parser.danger_map + state.endgame_fire_simulator.get_endgame_fire_danger(
        state.parser.endgame_fires)

    for location in state.blocked_locations:
        my_min_danger = math.inf
        for unit in state.parser.my_units:
            if manhattan_distance(unit.pos, location) == 1:
                debug_print(state, "Blocked location:", location, "my unit:", unit,
                            "danger:",
                            state.state_map[unit.pos])
                my_min_danger = min(blocked_danger_map[unit.pos], my_min_danger)
        enemy_min_danger = math.inf
        for unit in state.parser.enemy_units:
            if manhattan_distance(unit.pos, location) == 1:
                debug_print(state, "Blocked location:", location, "enemy unit:", unit,
                            "danger:",
                            state.state_map[unit.pos])
                enemy_min_danger = min(blocked_danger_map[unit.pos], enemy_min_danger)
        if my_min_danger >= enemy_min_danger:
            filtered_blocked_locations.add(location)
    state.blocked_locations = filtered_blocked_locations
    debug_print(state, "blocked locations after filter: ", state.blocked_locations)
