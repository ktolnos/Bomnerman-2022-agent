import math

import numpy as np

from actions import BombAction
from parsing.settings import *
from rule.blow_up_enemies import blow_up_if_worth_it
from rule.execute_action import execute_action, plan_move_to_point, execute_move
from rule.move_to_safer_spot import move_to_safer_spot_if_in_danger, move_to_safer_spot
from rule.state.rule_policy_state import RulePolicyState
from rule.utils import is_my_unit_near
from search.astar import AStar
from utils.game_utils import manhattan_distance, Point, blast_r
from utils.grid import check_free
from utils.policy import debug_print


def move_units_to_different_map_parts(state: RulePolicyState):
    if len(state.parser.my_units) < 2:
        return
    units_to_remove = []
    for unit_id in state.unit_id_to_diff_map_side_target_pos.keys():
        if unit_id not in state.parser.unit_id_to_unit:
            units_to_remove.append(unit_id)
    for unit_id in units_to_remove:
        state.unit_id_to_diff_map_side_target_pos.pop(unit_id)
    if not state.unit_id_to_diff_map_side_target_pos:
        has_unit_in_upper_part = False
        has_unit_in_lower_part = False
        for unit in state.parser.my_units:
            if unit.pos.y >= state.parser.center.y:
                has_unit_in_upper_part = True
            if unit.pos.y <= state.parser.center.y:
                has_unit_in_lower_part = True
        if has_unit_in_lower_part and has_unit_in_upper_part:
            return

        def units_order(unit):
            return -manhattan_distance(unit.pos, state.parser.center)

        for unit in sorted(state.parser.my_units, key=units_order):
            if state.is_busy(unit.id):
                continue
            if unit == state.closest_to_center_my:
                continue
            target_y_modifier = 1 if has_unit_in_lower_part else -1
            target_y = state.parser.center.y + target_y_modifier
            search_map = np.copy(state.parser.cell_occupation_danger_map) + close_cell_danger
            search_map += state.parser.wall_map * 1000
            search_map += state.parser.endgame_fires_map * 10000
            # search_map += self.parser.danger_map

            for spot in state.already_occupied_spots:
                search_map[spot] = 100000

            for spot in state.blocked_locations:
                search_map[spot] = 10000

            for other in state.parser.my_units:
                if other.id != unit.id:
                    search_map[other.pos] = 100000
            while search_map[state.parser.center.x, target_y] > 3000 and 0 < target_y < state.parser.h - 1:
                target_y += target_y_modifier
            target = Point(state.parser.center.x, target_y)
            state.unit_id_to_diff_map_side_target_pos[unit.id] = target
            break

    units_reached = set()
    for unit_id, target in state.unit_id_to_diff_map_side_target_pos.items():
        unit = state.parser.unit_id_to_unit[unit_id]
        if unit.pos == target:
            units_reached.add(unit_id)
            continue
        search_map = np.ones_like(state.parser.wall_map)
        search_map += state.parser.wall_map * 1000
        search_map += state.parser.endgame_fires_map * 10000

        for spot in state.already_occupied_spots:
            search_map[spot] = 100000

        for spot in state.blocked_locations:
            search_map[spot] = 10000

        for other in state.parser.my_units:
            if other.id != unit.id:
                search_map[other.pos] = 100000
        for enemy in state.parser.enemy_units:
            search_map[enemy.pos] = 10000
        target_y_modifier = 1 if target.y > state.parser.center.y else -1

        target_y = target.y
        while search_map[state.parser.center.x, target_y] > 3000 and 0 < target_y < state.parser.h - 1:
            target_y += target_y_modifier
        target = Point(state.parser.center.x, target_y)

        if unit.pos == target:
            units_reached.add(unit_id)
            continue

        path, cost = AStar(search_map, unit.pos, target).run()

        debug_print(state, "Differrent side", search_map, unit, cost, path)

        if move_to_safer_spot_if_in_danger(state, unit):
            debug_print(state, "In danger", unit, "\n", state.parser.danger_map)
            continue
        next_pos = path[1]
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
                continue
            execute_action(state, BombAction(unit.id))
            state.bombs_count += 1
            continue
        if next_pos in state.already_occupied_spots or state.parser.units_map[next_pos]:
            continue
        move = plan_move_to_point(unit.id, unit.pos, next_pos)
        execute_move(state, unit.id, move, next_pos)
    for unit_id in units_reached:
        state.unit_id_to_diff_map_side_target_pos.pop(unit_id)
        