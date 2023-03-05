import math

import numpy as np

from parsing.settings import explosion_danger
from rule.execute_action import plan_move, execute_move
from search.astar import AStar
from utils.game_utils import is_invincible_next_tick, Point, blast_r, manhattan_distance
from utils.policy import can_hit_enemy, debug_print


def suicide_bomb(state):
    for unit in state.parser.my_units:
        if state.is_busy(unit.id):
            continue
        if not is_invincible_next_tick(unit, state.tick_number):
            continue
        enemy_i_can_hit_now = can_hit_enemy(unit, state.parser)
        if enemy_i_can_hit_now and not is_invincible_next_tick(enemy_i_can_hit_now, state.tick_number):
            continue  # I didn't hit him for reason
        max_distance = unit.invincibility_last_tick - state.tick_number - 2
        explosions_near_enemy = set()
        for enemy in state.parser.enemy_units:
            if is_invincible_next_tick(enemy, state.tick_number):
                continue

            def check_explosion(x, y):
                if x < 0 or x >= state.parser.w or y < 0 or y >= state.parser.h:
                    return True
                if state.parser.wall_map[x, y]:
                    return True
                if state.parser.danger_map[x, y] >= explosion_danger:
                    if manhattan_distance(Point(x, y), unit.pos) <= max_distance:
                        explosions_near_enemy.add(Point(x, y))
                    return False
                return False

            rad = blast_r(unit.blast_diameter)
            x, y = enemy.pos
            for i in range(1, rad):
                if check_explosion(x + i, y):
                    break
            for i in range(1, rad):
                if check_explosion(x - i, y):
                    break
            for i in range(1, rad):
                if check_explosion(x, y + i):
                    break
            for i in range(1, rad):
                if check_explosion(x, y - i):
                    break
        debug_print(state, "Possible suicide pos", explosions_near_enemy)
        if not explosions_near_enemy:
            continue
        walk_map = state.parser.walkable_map + np.ones_like(state.parser.walkable_map)
        best_path = None
        best_cost = math.inf
        for point in explosions_near_enemy:
            path, cost = AStar(walk_map, unit.pos, point).run()
            if cost < best_cost:
                best_cost = cost
                best_path = path
        debug_print(state, "Best path is", best_cost, best_path)
        if best_cost == math.inf:
            continue
        if best_cost > max_distance:  # can't hit and run off
            debug_print(state, "Best cost is too great", best_cost, max_distance)
            continue
        if len(best_path) <= 1:
            continue
        move = plan_move(unit.id, best_path)
        move_cell = best_path[1] if move else unit.pos
        return execute_move(state, unit.id, move, move_cell)