from parsing.settings import explosion_danger
from rule.rule_policy_state import RulePolicyState
from utils.game_utils import manhattan_distance, Point
from utils.policy import debug_print


def is_my_unit_near(state: RulePolicyState, pos: Point, equals_is_true: bool = True) -> bool:
    enemies = 0
    for enemy in state.parser.enemy_units:
        if manhattan_distance(pos, enemy.pos) == 1:
            enemy_weight = 2 if enemy == state.closest_to_center_unit else 1
            if enemy.invincibility_last_tick and enemy.invincibility_last_tick > state.tick_number:
                enemy_weight *= 0.1
            debug_print(state, "near enemy", enemy, enemy_weight)
            enemies += enemy_weight
    my = 0
    for other in state.parser.my_units:
        if manhattan_distance(pos, other.pos) == 1:
            my_weight = 2 if other == state.closest_to_center_unit else 1
            if other.invincibility_last_tick and other.invincibility_last_tick > state.tick_number:
                my_weight *= 0.1
            debug_print(state, "near my", other, my_weight)
            my += my_weight
    return my > enemies or my == enemies and equals_is_true


def mark_detonate_bomb_danger(state: RulePolicyState, pos: Point, blast_rad: int):
    maps_to_mark = [
        state.state_map,
        state.parser.danger_map
    ]
    for map in maps_to_mark:
        state.parser.raise_danger_for_potential_explosion(map, pos, explosion_danger, blast_rad)