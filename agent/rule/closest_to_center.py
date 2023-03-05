import math


def calculate_closest_to_center(state):
    enemy_max_closeness = -math.inf
    for enemy in state.parser.enemy_units:
        unit_closeness = state.endgame_fire_simulator.endgame_fire_spiral[enemy.pos]
        if unit_closeness > enemy_max_closeness:
            enemy_max_closeness = unit_closeness
            state.closest_to_center_enemy = enemy
    state.parser.my_units.sort(key=lambda my_unit: state.endgame_fire_simulator.endgame_fire_spiral[my_unit.pos],
                               reverse=True)
    state.closest_to_center_my = state.parser.my_units[0]
    my_max_closeness = state.endgame_fire_simulator.endgame_fire_spiral[state.closest_to_center_my.pos]
    state.closest_to_center_unit = state.closest_to_center_my if \
        my_max_closeness > enemy_max_closeness else state.closest_to_center_enemy
