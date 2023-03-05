import math

from actions import BombAction
from parsing.settings import explosion_danger
from rule.execute_action import execute_action
from rule.rule_policy_state import RulePolicyState
from rule.utils import is_my_unit_near, mark_detonate_bomb_danger
from search.astar import AStar
from utils.game_utils import is_invincible_next_tick, blast_r, manhattan_distance
from utils.grid import check_free
from utils.policy import debug_print, can_hit_enemy


def place_bombs(state: RulePolicyState):
    debug_print(state, "place_bombs")
    for unit in state.parser.my_units:
        debug_print(state, "place_bombs", unit)
        if state.bombs_count >= 3:
            debug_print(state, "place_bombs too many bombs", unit)
            return
        if state.is_busy(unit.id):
            debug_print(state, "place_bombs is busy", unit)
            continue
        if not unit.bombs:
            debug_print(state, "place_bombs has no boms", unit)
            continue
        stands_on_bomb = state.parser.has_bomb_map[unit.pos]
        if stands_on_bomb:
            debug_print(state, "place_bombs stands_on_bomb", unit)
            continue
        enemy_to_hit = can_hit_enemy(unit, state.parser)
        is_enemy_invincible = enemy_to_hit and is_invincible_next_tick(enemy_to_hit, state.tick_number)

        if state.closest_to_center_unit == state.closest_to_center_enemy and \
                state.parser.endgame_fires >= state.parser.w * state.parser.h - 25 and \
                enemy_to_hit and not is_enemy_invincible:
            state.bombs_count += 1
            debug_print(state, "hitting because endgame", unit)
            execute_action(state, BombAction(unit.id))
            continue

        if is_my_unit_near(state, unit.pos, False):
            debug_print(state, "don't blow up allies", unit)
            continue  # don't blow up allies

        if unit.invincibility_last_tick and unit.invincibility_last_tick > state.tick_number and \
                state.parser.danger_map[unit.pos] >= explosion_danger - 4:
            debug_print(state, "invincible", unit)
            if enemy_to_hit and not is_enemy_invincible:
                state.bombs_count += 1
                debug_print(state, "hitting while invincible", unit)
                execute_action(state, BombAction(unit.id))
                mark_detonate_bomb_danger(state, unit.pos, blast_r(unit.blast_diameter))
                continue
        else:
            debug_print(state, "not invincible", unit)
        force_bomb = unit.id in state.force_bomb_unit_ids
        if unit == state.closest_to_center_unit and not force_bomb:
            debug_print(state, "Placing bomb", unit, "is closest to center")
            continue

        if not check_free(state.parser, unit.pos, blast_r(unit.blast_diameter) + 1, blast_r(unit.blast_diameter)):
            debug_print(state, "Placing bomb", unit, "not free")
            continue

        bomb_clusters = state.parser.all_bomb_explosion_map_enemy[unit.pos]
        is_in_enemy_bomb_cluster = False
        if bomb_clusters:
            for entry in bomb_clusters:
                if entry.cluster.is_enemy:
                    is_in_enemy_bomb_cluster = True
                    break
        if is_in_enemy_bomb_cluster:
            debug_print(state, "Placing bomb", unit, "in enemy bomb cluster")
            continue
        equals_is_true = not force_bomb
        if not is_my_unit_near(state, unit.pos, equals_is_true):
            if force_bomb:
                debug_print(state, "Forcing bomb", unit)
                state.bombs_count += 1
                execute_action(state, BombAction(unit.id))
            for enemy in state.parser.enemy_units:
                if manhattan_distance(unit.pos, enemy.pos) == 1:
                    debug_print(state, "Placing bomb", unit, "hitting", enemy)
                    state.bombs_count += 1
                    execute_action(state, BombAction(unit.id))
                    break
        if enemy_to_hit and not is_enemy_invincible:
            path, cost = AStar(state.parser.danger_map, unit.pos, enemy_to_hit.pos).run()
            debug_print(state, "Placing bomb", unit, "wanna hit", enemy_to_hit,
                        "danger distance is ",
                        cost, "danger map\n", state.parser.danger_map)
            if cost > 0 and cost != math.inf:  # can't come to enemy and not due to my unit
                state.bombs_count += 1
                debug_print(state, "Placed bomb", unit, "hitting remote", enemy_to_hit)
                execute_action(state, BombAction(unit.id))
    state.force_bomb_unit_ids.clear()
