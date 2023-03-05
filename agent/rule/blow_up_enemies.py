from typing import List

from actions import DetonateBombAction
from parsing.bombs import BombExplosionMapEntry
from rule.execute_action import execute_action
from rule.rule_policy_state import RulePolicyState
from rule.utils import mark_detonate_bomb_danger
from utils.game_utils import Point, blast_r
from utils.policy import debug_print


def blow_up_enemies(state: RulePolicyState):
    for enemy in state.parser.enemy_units:
        blow_up_if_worth_it(state, enemy.pos, False)


def blow_up_if_worth_it(state: RulePolicyState, pos: Point, blow_if_equal: bool) -> bool:
    bombs_list = state.parser.all_bomb_explosion_map_my[pos]
    if not bombs_list:
        return False
    for bomb_entry in bombs_list:
        if bomb_entry.cluster.my_bomb_that_can_trigger:
            bomb_to_trigger = bomb_entry.cluster.my_bomb_that_can_trigger
            enemies_in_cluster = 0
            for e in state.parser.enemy_units:
                enemy_weight = 2 if e == state.closest_to_center_unit else 1
                if e.invincibility_last_tick and e.invincibility_last_tick > state.tick_number:
                    enemy_weight *= 0.1
                e_bomb_entries: List[BombExplosionMapEntry] = state.parser.all_bomb_explosion_map_my[e.pos]
                if not e_bomb_entries:
                    continue
                for e_bomb_entry in e_bomb_entries:
                    if e_bomb_entry.cluster == bomb_entry.cluster:
                        enemies_in_cluster += enemy_weight
                        break
            my_in_cluster = 0
            for u in state.parser.my_units:
                my_weight = 2 if u == state.closest_to_center_unit else 1
                if u.invincibility_last_tick and u.invincibility_last_tick > state.tick_number:
                    my_weight *= 0.1
                u_bomb_entries: List[BombExplosionMapEntry] = state.parser.all_bomb_explosion_map_my[u.pos]
                if not u_bomb_entries:
                    continue
                for u_bomb_entry in u_bomb_entries:
                    if u_bomb_entry.cluster == bomb_entry.cluster:
                        my_in_cluster += my_weight
                        break
            debug_print(state, "Thinking to blow up ", pos, "my", my_in_cluster, "enemy",
                        enemies_in_cluster)
            if my_in_cluster < enemies_in_cluster or my_in_cluster == enemies_in_cluster and blow_if_equal:
                debug_print(state, "Worth it, blowing up", pos)
                unit_id = bomb_to_trigger.owner_unit_id
                if state.is_busy(unit_id):
                    debug_print(state, "Damn, busy", unit_id)
                    continue
                execute_action(state, DetonateBombAction(unit_id, bomb_to_trigger))
                unit = state.parser.unit_id_to_unit[unit_id]
                mark_detonate_bomb_danger(state, unit.pos, blast_r(unit.blast_diameter))
                return True
    return False
