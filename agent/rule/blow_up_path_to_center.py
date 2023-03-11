import math

import numpy as np

from actions import BombAction
from parsing.settings import close_cell_danger
from rule.blow_up_enemies import blow_up_if_worth_it
from rule.execute_action import execute_move, execute_action, plan_move_to_point
from rule.move_to_safer_spot import move_to_safer_spot, move_to_safer_spot_if_in_danger
from rule.state.rule_policy_state import RulePolicyState
from rule.utils import is_my_unit_near
from search.astar import AStar
from utils.game_utils import manhattan_distance, blast_r, get_neighbours, Point
from utils.grid import check_free
from utils.policy import debug_print


def blow_up_path_to_center(state: RulePolicyState):
    search_map = np.copy(state.parser.cell_occupation_danger_map) + close_cell_danger
    search_map += state.parser.wall_map * 1000
    search_map += state.parser.endgame_fires_map * 10000
    # search_map += self.parser.danger_map

    for spot in state.already_occupied_spots:
        search_map[spot] = 100000

    for spot in state.blocked_locations:
        search_map[spot] = 10000

    for unit_id in state.parser.my_unit_ids:
        if unit_id not in state.parser.unit_id_to_unit:
            # unit is dead
            continue
        if unit_id in state.unit_id_to_diff_map_side_target_pos:
            continue  # he is moving to center the other way
        unit = state.parser.unit_id_to_unit[unit_id]
        if state.is_busy(unit.id):
            debug_print(state, "path_to_center", unit, "is busy")
            continue
        u_search_map = np.copy(search_map)
        for other in state.parser.my_units:
            if other.id != unit.id and manhattan_distance(other.pos, state.parser.center) > 2:
                u_search_map[other.pos] = 10000

        path_to_center, cost = AStar(u_search_map, unit.pos, state.parser.center).run()

        if cost == math.inf and len(path_to_center) > 1:
            new_center = path_to_center[-2]
            debug_print(state, "path_to_center", unit, "new center is", new_center)
            path_to_center, cost = AStar(u_search_map, unit.pos, new_center).run()

        debug_print(state, u_search_map, "\nblow up path\n", unit, cost, path_to_center)
        if cost < 1000 or cost == math.inf:
            debug_print(state, "path_to_center", unit, "is free", cost)
            continue
        if move_to_safer_spot_if_in_danger(state, unit):
            debug_print(state, "In danger", unit, "\n", state.parser.danger_map)
            continue
        next_pos = path_to_center[1]
        detonated_bomb = False
        for bomb in state.parser.my_armed_bombs:
            if bomb.owner_unit_id == unit.id and blow_up_if_worth_it(state, bomb.pos, True):
                detonated_bomb = True
                break
        if detonated_bomb:
            continue
        already_placed_bomb = False
        for bomb in state.parser.my_bombs:
            if bomb.owner_unit_id == unit.id:
                move_to_safer_spot(state, unit)
                already_placed_bomb = True
                break
        if already_placed_bomb:
            debug_print(state, "already_placed_bomb", unit)
            continue

        least_powerup_cost = math.inf
        powerup_path = None
        for powerup in state.parser.power_ups:
            powerup_pos = Point(powerup.get("x"), powerup.get("y"))
            path_to_powerup, powerup_cost = AStar(search_map, unit.pos, powerup_pos).run()
            should_persue_powerup = True
            for u in state.parser.my_units:
                if u == unit:
                    continue
                other_path, u_powerup_cost = AStar(search_map, u.pos, powerup_pos).run()
                if u_powerup_cost < powerup_cost:
                    should_persue_powerup = False
                    break
                if should_persue_powerup and least_powerup_cost > cost:
                    least_powerup_cost = cost
                    powerup_path = path_to_powerup
        if least_powerup_cost != math.inf and powerup_path and len(powerup_path) > 1:
            next_pos = powerup_path[1]

        if state.parser.danger_map[next_pos.x, next_pos.y]:
            debug_print(state, "Next in danger", unit, "\n", state.parser.danger_map)
            move_to_safer_spot(state, unit)
            continue
        if state.parser.wall_map[next_pos.x, next_pos.y] and state.bombs_count < 3:
            if is_my_unit_near(state, unit.pos, equals_is_true=False):
                continue
            if not check_free(state.parser, unit.pos, blast_r(unit.blast_diameter) + 1,
                              blast_r(unit.blast_diameter)):
                for neighbour in get_neighbours(search_map, unit.pos):
                    if check_free(state.parser, neighbour,
                                  blast_r(unit.blast_diameter) + 1, blast_r(unit.blast_diameter), unit.id):
                        move = plan_move_to_point(unit.id, unit.pos, neighbour)
                        execute_move(state, unit.id, move, neighbour)
                        state.force_bomb_unit_ids.add(unit.id)
                        break
                continue
            execute_action(state, BombAction(unit.id))
            state.bombs_count += 1
            continue
        if next_pos in state.already_occupied_spots or state.parser.units_map[next_pos]:
            continue
        move = plan_move_to_point(unit.id, unit.pos, next_pos)
        execute_move(state, unit.id, move, next_pos)
