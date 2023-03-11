import math

import numpy as np

from parsing.settings import *
from rule.closest_to_center_discount import add_closest_to_center_enemy_discount
from rule.execute_action import execute_move, plan_move
from rule.state.rule_policy_state import RulePolicyState
from search.least_cost_search import LeastCostSearch
from utils.game_utils import get_neighbours, Unit
from utils.grid import draw_cross
from utils.policy import debug_print


def move_to_safer_spot(state: RulePolicyState, unit, allow_occupied_position=False) -> bool:
    """
    :return: True if unit moved
    """
    if state.is_busy(unit.id):
        return False
    unit_map = np.copy(state.state_map)
    debug_print(state, unit, "state_map", unit_map)
    unit_close_cell_danger = np.copy(state.parser.cell_occupation_danger_map)
    if unit_map[unit.pos] == math.inf:
        unit_map[unit.pos] = stand_on_bomb_danger
    for other_unit in state.parser.my_units:
        if other_unit == unit:
            continue
        unit_place_danger = math.inf
        if allow_occupied_position:
            my_neighbours = set(get_neighbours(state.parser.danger_map, unit.pos))
            if other_unit.pos in my_neighbours:
                for neighbour in get_neighbours(state.parser.danger_map, other_unit.pos):
                    if state.parser.danger_map[neighbour] <= my_bomb_starting_danger and not \
                            state.parser.walkable_map[neighbour]:
                        unit_place_danger = move_on_occupied_spot_penalty
        unit_map[other_unit.pos] += unit_place_danger
        draw_cross(unit_close_cell_danger, other_unit.pos.x, other_unit.pos.y, rad=2, value=close_cell_danger)
    debug_print(state, unit, "added units", unit_map)
    unit_map += np.square(unit_close_cell_danger)
    debug_print(state, unit, "added _cell_danger", unit_map)
    add_closest_to_center_enemy_discount(state, unit, unit_map)
    if unit != state.closest_to_center_unit:
        for power_up in state.parser.power_ups:
            unit_map[power_up.get("x"), power_up.get("y")] += power_up_discount
    discount = close_enemy_discount
    if unit == state.closest_to_center_unit and state.parser.free_from_endgame_fire <= 81:
        discount = 0
    if state.parser.danger_map[unit.pos] and not state.parser.has_bomb_map[unit.pos]:
        discount = 0
    for enemy in state.parser.enemy_units:
        draw_cross(unit_map, enemy.pos.x, enemy.pos.y, rad=2, value=discount)

    if state.tick_number > 270:
        unit_map[state.parser.center] += endgame_fire_center_discount * unit.hp

        unit_map[state.parser.center.x - 1::state.parser.center.x + 2,
                 state.parser.center.y - 1::state.parser.center.y + 2] += endgame_fire_center_discount_mass

        debug_print(state, unit, "added center discounts", unit_map)

    for spot in state.already_occupied_spots:
        unit_map[spot] += stand_on_bomb_danger
    debug_print(state, unit, "removed already_occupied_spots", unit_map)

    for spot in state.blocked_locations:
        if spot != unit.pos:
            unit_map[spot] += stand_on_bomb_danger
    debug_print(state, unit, "removed blocked_locations", unit_map)

    search_budget = search_budget_big

    least_cost_search = LeastCostSearch(unit_map, unit.pos,
                                        exclude_points=state.already_occupied_destinations,
                                        search_budget=search_budget)
    safest_path, cost = least_cost_search.run(horizon=search_horizon)
    # good breakpoint spot
    state.already_occupied_destinations.add(safest_path[-1])
    debug_print(state, unit_map, unit, safest_path, cost)
    move = plan_move(unit.id, safest_path)
    move_cell = safest_path[1] if move else unit.pos
    return execute_move(state, unit.id, move, move_cell)


def move_all_to_safer_spot(state: RulePolicyState):
    def unit_move_importance(unit: Unit):
        return state.endgame_fire_simulator.endgame_fire_spiral[unit.pos] - state.parser.danger_map[unit.pos]

    move_order = sorted(state.parser.my_units, key=unit_move_importance)
    for unit in move_order:
        move_to_safer_spot(state, unit, True)


def move_to_safer_spot_if_in_danger(state: RulePolicyState, unit: Unit) -> bool:
    """
    :return: True if unit submitted action
    """
    if state.parser.danger_map[unit.pos] != 0:
        move_to_safer_spot(state, unit, True)
        return True
    return False
