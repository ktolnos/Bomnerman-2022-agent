from parsing.settings import *
from rule.rule_policy_state import RulePolicyState
from rule.utils import is_my_unit_near
from utils.game_utils import Unit, Point, get_neighbours
from utils.policy import debug_print


def add_closest_to_center_enemy_discount(state: RulePolicyState, unit: Unit, unit_map):
    if not unit.bombs and state.closest_to_center_unit == state.closest_to_center_enemy:
        for power_up in state.parser.power_ups:
            unit_map[power_up.get("x"), power_up.get("y")] += center_occupied_ammo_discount
        return

    my_distance = state.endgame_fire_simulator.endgame_fire_spiral[unit.pos]
    enemy_distance = state.endgame_fire_simulator.endgame_fire_spiral[state.closest_to_center_enemy.pos]

    if enemy_distance > my_distance:
        debug_print(state, f"{state.tick_number} Enemy {state.closest_to_center_enemy} is closer "
                           f"({enemy_distance} < {my_distance}) then me {unit}")

        def should_discount(pos: Point) -> bool:
            return not is_my_unit_near(state, pos, equals_is_true=False)

        positions = filter(should_discount, get_neighbours(unit_map, unit.pos))
        for pos in positions:
            unit_map[pos] += close_to_center_enemy_discount
