import asyncio
from cmath import cos
from distutils.log import debug
import time
import numpy as np
from collections import deque
from turtle import forward
from dataclasses import dataclass

from actions import MoveAction, BombAction, DetonateBombAction, Action
from astar import AStar, get_neighbours
from engame_fire_simulator2 import EndgameFireSimulator2
from least_cost_search import LeastCostSearch
from parser import *
from parser import Parser

from forward import ForwardModel
from game_utils import Point, manhattan_distance, blast_r


@dataclass
class PathProposal:
    path: list
    unit: dict
    destination: dict

    def __lt__(self, other):
        return len(self.path) < len(other.path)


class Ticker:
    def __init__(self):
        self.tick = 0


class RulePolicy:

    def __init__(self):
        self.busy = set()  # units that already made the move
        self.tasks = list()
        self.endgame_fire_simulator = EndgameFireSimulator2(15, 15)
        self.has_no_path_to_center = None
        self.all_have_path_to_center = False
        self.already_occupied_spots = list()
        self.already_occupied_destinations = set()
        self.loop = None
        self.print_queue = deque()
        self.parser = None
        self.client = None
        self.closest_to_center_unit = None
        self.closest_to_center_my = None
        self.closest_to_center_enemy = None
        self.debug = False
        self.predicted_gs = None
        self.forward = ForwardModel()
        self.blocked_locations = set()
        self.unit_id_to_target_pos = dict()
        self.bombs_count = 0
        self.unit_id_to_diff_map_side_target_pos = dict()
        self.force_bomb_unit_ids = set()

    def reset(self):
        self.all_have_path_to_center = False
        self.has_no_path_to_center = None
        self.print_queue = deque()

    def init(self, client):
        self.client = client
        self.loop = asyncio.get_event_loop()

    def execute_actions(self, tick_number, game_state):
        self.forward.clear()
        start_time = time.time()
        self.tick_number = tick_number

        self.busy.clear()
        self.already_occupied_spots.clear()
        self.already_occupied_destinations.clear()
        self.blocked_locations.clear()
        self.tasks.clear()
        clear_time = time.time()

        self.parser = Parser(tick_number, game_state)

        parsing_time = time.time()
        self.compute_state_map()
        self.calculate_closest_to_center()
        self.compute_blocked_locations()
        self.bombs_count = len(self.parser.my_bombs)

        self.blow_up_enemies(tick_number)
        blow_up_time = time.time()

        self.place_bombs(tick_number)
        self.force_bomb_unit_ids.clear()
        bombs_time = time.time()

        self.blow_up_path_to_center(tick_number)
        path_to_center_time = time.time()
        if self.parser.free_from_endgame_fire > 49:
            self.move_units_to_different_map_parts()
        else:
            self.unit_id_to_diff_map_side_target_pos.clear()

        self.move_all_to_safer_spot(tick_number)
        move_to_spot_time = time.time()

        unit_id_to_pos = dict()
        for unit in self.parser.my_units:
            unit_id_to_pos[unit.id] = unit.pos
        postpned_actions = self.tasks
        executed_actions = []
        while postpned_actions:
            for action in postpned_actions:
                if action is MoveAction and action.target_pos:
                    has_conflict = False
                    for id, pos in unit_id_to_pos:
                        if pos == action.target_pos:
                            has_conflict = True
                            break
                    if has_conflict:
                        continue
                    unit_id_to_pos[action.unit_id] = action.target_pos
                executed_actions.append(action)
                self.loop.create_task(self.send_action_acync_impl(action, self.tick_number))
            for action in executed_actions:
                postpned_actions.remove(action)
            executed_actions.clear()

        while not self.debug and self.print_queue:
            print(*self.print_queue.popleft())
        printing_time = time.time()

        total_time = (time.time() - start_time) * 1000
        
        self.prod_print("Tick #{tick},"
                            " total time is {time}ms,\n"
                            " clear_time={clear_time}\n"
                            " path_to_center_time={path_to_center_time}\n"
                            " blow_up_time={blow_up_time}\n"
                            " bombs_time={bombs_time}\n"
                            " move_to_spot_time={move_to_spot_time}\n"
                            " printing_time={printing_time}\n"
                            "".format(tick=tick_number, time=total_time,
                                      clear_time=(clear_time - start_time) * 1000,
                                      parsing_time=(parsing_time - clear_time) * 1000,
                                      path_to_center_time=(bombs_time - path_to_center_time) * 1000,
                                      blow_up_time=(blow_up_time - parsing_time) * 1000,
                                      bombs_time=(bombs_time - blow_up_time) * 1000,
                                      move_to_spot_time=(move_to_spot_time - bombs_time) * 1000,
                                      printing_time=(printing_time - move_to_spot_time) * 1000))
        # if self.predicted_gs is not None:
        #     if self.predicted_gs != self.parser.gs:
        #         if self.predicted_gs.units != self.parser.gs.units:
        #             print("Predicted units\n", self.predicted_gs.units)
        #             print("Actual units\n", self.parser.gs.units)
        #             print("Units diff predictred\n", self.predicted_gs.units - self.parser.gs.units)
        #             print("Units diff actual\n", self.parser.gs.units - self.predicted_gs.units)
        #             print("Map\n", self.parser.gs.map)
        #         map_diff = np.ma.array(data=self.parser.gs.map, mask=self.predicted_gs.map == self.parser.gs.map)
        #         has_diff = False
        #         for el in map_diff.compressed():
        #             if not isinstance(el, Powerup):
        #                 print(el)
        #                 has_diff = True
        #         if has_diff:
        #             print("Prev map\n", self.prev_gs.map)
        #             print("Predicted map\n", self.predicted_gs.map)
        #             print("Actual map\n", self.parser.gs.map)
        #             print("Map diff\n", map_diff)
        # self.prev_gs = self.parser.gs
        # self.predicted_gs = self.forward.step(self.parser.gs)

    def compute_state_map(self):
        self.state_map = np.ones_like(self.parser.danger_map) * 4

        self.state_map += self.parser.walkable_map
        self.state_map += self.parser.danger_map
        self.state_map += self.endgame_fire_simulator.get_endgame_fire_danger(self.parser.endgame_fires)
        
        neighbours_count = 0
        last_neighbour = None
        for enemy in self.parser.enemy_units:
            if self.parser.danger_map[enemy.pos]:
                for neigbour in get_neighbours(self.parser.danger_map, enemy.pos):
                    if not self.parser.danger_map[neigbour] and not self.parser.walkable_map[neigbour]:
                        self.state_map[neigbour] += enemy_in_danger_discount
                        neighbours_count += 1
                        last_neighbour = neigbour
        if neighbours_count == 1:
            self.state_map[last_neighbour] += enemy_in_danger_one_cell_discount

    def compute_blocked_locations(self):
        for unit in self.parser.my_units:
            if unit.stunned_last_tick >= self.tick_number - 1:
                continue
            if unit.id in self.unit_id_to_target_pos and unit.pos != self.unit_id_to_target_pos[unit.id]:
                self.blocked_locations.add(self.unit_id_to_target_pos[unit.id])
        self.unit_id_to_target_pos.clear()
        self.debug_print("blocked locations before filter: ", self.blocked_locations)
        if not self.blocked_locations: 
            return

        filtered_blocked_locations = set()
        blocked_danger_map = self.parser.danger_map + self.endgame_fire_simulator.get_endgame_fire_danger(self.parser.endgame_fires)
        
        for location in self.blocked_locations:
            my_min_danger = math.inf
            for unit in self.parser.my_units:
                if manhattan_distance(unit.pos, location) == 1:
                    self.debug_print("Blocked location:", location, "my unit:", unit, "danger:", self.state_map[unit.pos])
                    my_min_danger = min(blocked_danger_map[unit.pos], my_min_danger)
            enemy_min_danger = math.inf
            for unit in self.parser.enemy_units:
                if manhattan_distance(unit.pos, location) == 1:
                    self.debug_print("Blocked location:", location, "enemy unit:", unit, "danger:", self.state_map[unit.pos])
                    enemy_min_danger = min(blocked_danger_map[unit.pos], enemy_min_danger)
            if my_min_danger >= enemy_min_danger:
                filtered_blocked_locations.add(location)
        self.blocked_locations = filtered_blocked_locations
        self.debug_print("blocked locations after filter: ", self.blocked_locations)


    def blow_up_enemies(self, tick_number):
        for enemy in self.parser.enemy_units:
            self.blow_up_if_worth_it(enemy.pos, tick_number, False)

    def blow_up_if_worth_it(self, pos: Point, tick_number, blow_if_equal):
        bombs_list = self.parser.all_bomb_explosion_map_my[pos]
        if not bombs_list:
            return False
        for bomb_entry in bombs_list:
            if bomb_entry.cluster.my_bomb_that_can_trigger:
                bomb_to_trigger = bomb_entry.cluster.my_bomb_that_can_trigger
                enemies_in_cluster = 0
                for e in self.parser.enemy_units:
                    enemy_weight = 2 if e == self.closest_to_center_unit else 1
                    if e.invincibility_last_tick and e.invincibility_last_tick > self.tick_number:
                        enemy_weight *= 0.1
                    e_bomb_entries: List[BombExplosionMapEntry] = self.parser.all_bomb_explosion_map_my[e.pos]
                    if not e_bomb_entries:
                        continue
                    for e_bomb_entry in e_bomb_entries:
                        if e_bomb_entry.cluster == bomb_entry.cluster:
                            enemies_in_cluster += enemy_weight
                            break
                my_in_cluster = 0
                for u in self.parser.my_units:
                    my_weight = 2 if u == self.closest_to_center_unit else 1
                    if u.invincibility_last_tick and u.invincibility_last_tick > self.tick_number:
                        my_weight *= 0.1
                    u_bomb_entries: List[BombExplosionMapEntry] = self.parser.all_bomb_explosion_map_my[u.pos]
                    if not u_bomb_entries:
                        continue
                    for u_bomb_entry in u_bomb_entries:
                        if u_bomb_entry.cluster == bomb_entry.cluster:
                            my_in_cluster += my_weight
                            break                    
                self.debug_print("Thinking to blow up ", pos, "my", my_in_cluster, "enemy", enemies_in_cluster)
                if my_in_cluster < enemies_in_cluster or my_in_cluster == enemies_in_cluster and blow_if_equal:
                    self.debug_print("Worth it, blowing up", pos)
                    unit_id = bomb_to_trigger.owner_unit_id
                    if self.is_busy(unit_id):
                        self.debug_print("Damn, busy", unit_id)
                        continue
                    self.execute_action(DetonateBombAction(unit_id, bomb_to_trigger), tick_number)
                    unit = self.parser.unit_id_to_unit[unit_id]
                    self.mark_detonate_bomb_danger(unit.pos, blast_r(unit.blast_diameter))
                    return True
        return False

    def place_bombs(self, tick_number):
        self.debug_print("place_bombs")
        for unit in self.parser.my_units:
            self.debug_print("place_bombs", unit)
            if self.bombs_count >= 3:
                self.debug_print("place_bombs too many bombs", unit)
                return
            if self.is_busy(unit.id):
                self.debug_print("place_bombs is busy", unit)
                continue
            if not unit.bombs:
                self.debug_print("place_bombs has no boms", unit)
                continue
            stands_on_bomb = self.parser.has_bomb_map[unit.pos]
            if stands_on_bomb:
                self.debug_print("place_bombs stands_on_bomb", unit)
                continue
            enemy_to_hit = self.parser.can_hit_enemy(unit)
            is_enemy_invincible = enemy_to_hit and is_invincible_next_tick(enemy_to_hit, tick_number)

            if self.closest_to_center_unit == self.closest_to_center_enemy and \
                self.parser.endgame_fires >= self.parser.w * self.parser.h - 25 and \
                    enemy_to_hit and not is_enemy_invincible:
                self.bombs_count += 1
                self.debug_print("hitting because endgame", unit)
                self.execute_action(BombAction(unit.id), tick_number)
                continue

            if self.is_my_unit_near(unit.pos, False):
                self.debug_print("don't blow up allies", unit)
                continue # don't blow up allies

            if unit.invincibility_last_tick and unit.invincibility_last_tick > tick_number and\
             self.parser.danger_map[unit.pos] >= explosion_danger - 4:
                self.debug_print("invincible", unit)
                if enemy_to_hit and not is_enemy_invincible:
                    self.bombs_count += 1
                    self.debug_print("hitting while invincible", unit)
                    self.execute_action(BombAction(unit.id), tick_number)
                    self.mark_detonate_bomb_danger(unit.pos, blast_r(unit.blast_diameter))
                    continue
            else:
                self.debug_print("not invincible", unit)
            force_bomb = unit.id in self.force_bomb_unit_ids
            if unit == self.closest_to_center_unit and not force_bomb:
                self.debug_print(tick_number, "Placing bomb", unit, "is closest to center")
                continue

            if not self.parser.check_free(unit.pos, blast_r(unit.blast_diameter) + 1, blast_r(unit.blast_diameter)):
                self.debug_print("Placing bomb", unit, "not free")
                continue

            bomb_clusters = self.parser.all_bomb_explosion_map_enemy[unit.pos]
            is_in_enemy_bomb_cluster = False
            if bomb_clusters:
                for entry in bomb_clusters:
                    if entry.cluster.is_enemy:
                        is_in_enemy_bomb_cluster = True
                        break
            if is_in_enemy_bomb_cluster:
                self.debug_print("Placing bomb", unit, "in enemy bomb cluster")
                continue
            equals_is_true = not force_bomb
            if not self.is_my_unit_near(unit.pos, equals_is_true):
                if force_bomb:
                    self.debug_print("Forcing bomb", unit)
                    self.bombs_count += 1
                    self.execute_action(BombAction(unit.id), tick_number)
                for enemy in self.parser.enemy_units:
                    if manhattan_distance(unit.pos, enemy.pos) == 1:
                        self.debug_print("Placing bomb", unit, "hitting", enemy)
                        self.bombs_count += 1
                        self.execute_action(BombAction(unit.id), tick_number)
                        break
            if enemy_to_hit and not is_enemy_invincible:
                path, cost = AStar(self.parser.danger_map, unit.pos, enemy_to_hit.pos).run()
                self.debug_print("Placing bomb", unit, "wanna hit", enemy_to_hit, "danger distance is ", cost, "danger map\n", self.parser.danger_map)
                if cost > 0 and cost != math.inf: # can't come to enemy and not due to my unit
                    self.bombs_count += 1
                    self.debug_print("Placed bomb", unit, "hitting remote", enemy_to_hit)
                    self.execute_action(BombAction(unit.id), tick_number)

    def move_to_safer_spot_if_in_danger(self, unit, tick_number) -> bool:
        """
        :return: True if unit submitted action
        """
        if self.parser.danger_map[unit.pos] != 0:
            self.move_to_safer_spot(unit, tick_number, True)
            return True
        return False

    def move_to_safer_spot(self, unit, tick_number, allow_occupied_position = False) -> bool:
        """
        :return: True if unit moved
        """
        if self.is_busy(unit.id):
            return False
        unit_map = np.copy(self.state_map)
        self.debug_print(unit, "state_map", unit_map)
        unit_close_cell_danger = np.copy(self.parser.cell_occupation_danger_map)
        if unit_map[unit.pos] == math.inf:
            unit_map[unit.pos] = stand_on_bomb_danger
        for other_unit in self.parser.my_units:
            if other_unit == unit:
                continue
            unit_place_danger = math.inf
            if allow_occupied_position:
                my_neighbours = set(get_neighbours(self.parser.danger_map, unit.pos))
                if other_unit.pos in my_neighbours:
                    for neighbour in get_neighbours(self.parser.danger_map, other_unit.pos):
                        if self.parser.danger_map[neighbour] <= my_bomb_starting_danger and not self.parser.walkable_map[neighbour]:
                            unit_place_danger = move_on_occupied_spot_penalty
            unit_map[other_unit.pos] += unit_place_danger
            draw_cross(unit_close_cell_danger, other_unit.pos.x, other_unit.pos.y, rad=2, value=close_cell_danger)
        self.debug_print(unit, "added units", unit_map)
        unit_map += np.square(unit_close_cell_danger)
        self.debug_print(unit, "added _cell_danger", unit_map)
        self.add_closest_to_center_enemy_discount(unit, unit_map)
        if unit != self.closest_to_center_unit:
            for power_up in self.parser.power_ups:
                unit_map[power_up.get("x"), power_up.get("y")] += power_up_discount
        discount = close_enemy_discount
        if unit == self.closest_to_center_unit:
            discount = 0
        if self.parser.danger_map[unit.pos]:
            discount = 0
        for enemy in self.parser.enemy_units:
            draw_cross(unit_map, enemy.pos.x, enemy.pos.y, rad=2, value=discount)

        unit_map[self.parser.center] += endgame_fire_center_discount * unit.hp
        
        unit_map[self.parser.center.x - 1::self.parser.center.x + 2,
        self.parser.center.y - 1::self.parser.center.y + 2] += endgame_fire_center_discount_mass
        self.debug_print(unit, "added center discounts", unit_map)

        for spot in self.already_occupied_spots:
            unit_map[spot] += explosion_danger
        self.debug_print(unit, "removed already_occupied_spots", unit_map)
        
        for spot in self.blocked_locations:
            unit_map[spot] = math.inf
        self.debug_print(unit, "removed blocked_locations", unit_map)

        search_budget = search_budget_big

        least_cost_search = LeastCostSearch(unit_map, unit.pos,
                                            exclude_points=self.already_occupied_destinations,
                                            search_budget=search_budget)
        safest_path, cost = least_cost_search.run(horizon=search_horizon)
        # good breakpoint spot
        self.already_occupied_destinations.add(safest_path[-1])
        self.debug_print(unit_map, unit, safest_path, cost)
        move = self.plan_move(unit.id, safest_path)
        move_cell = safest_path[1] if move else unit.pos
        return self.execute_move(unit.id, move, move_cell, tick_number)

    def execute_move(self, unit_id, move, move_cell, tick_number) -> bool:
        self.already_occupied_spots.append(move_cell)
        self.unit_id_to_target_pos[unit_id] = move_cell
        if move:
            self.execute_action(move, tick_number)
            return True
        else:
            self.execute_action(Action(unit_id), tick_number)
            return False

    def blow_up_path_to_center(self, tick_number):
        # if not self.all_have_path_to_center:
        #     if not self.has_no_path_to_center:
        #         self.has_no_path_to_center = self.parser.my_unit_ids
        units_with_path = list()

        search_map = np.ones_like(self.parser.wall_map)
        search_map += self.parser.wall_map * 1000
        search_map += self.parser.endgame_fires_map * 10000
        # search_map += self.parser.danger_map
        
        for spot in self.already_occupied_spots:
            search_map[spot] = 100000
            
        for spot in self.blocked_locations:
            search_map[spot] = 10000

        for unit_id in self.parser.my_unit_ids:
            if unit_id not in self.parser.unit_id_to_unit:
                # unit is dead
                units_with_path.append(unit_id)
                continue
            if unit_id in self.unit_id_to_diff_map_side_target_pos:
                continue # he is moving to center the other way
            unit = self.parser.unit_id_to_unit[unit_id]
            if self.is_busy(unit.id):
                self.debug_print("path_to_center", unit, "is busy")
                continue
            u_search_map = np.copy(search_map)
            for other in self.parser.my_units:
                if other.id != unit.id and manhattan_distance(other.pos, self.parser.center) > 2:
                    u_search_map[other.pos] = 10000
                
            path_to_center, cost = AStar(u_search_map, unit.pos, self.parser.center).run()

            if cost == math.inf and len(path_to_center) > 1:
                new_center = path_to_center[-2]
                self.debug_print("path_to_center", unit, "new center is", new_center)
                path_to_center, cost = AStar(u_search_map, unit.pos, new_center).run()

            self.debug_print(u_search_map, "\nblow up path\n", unit, cost, path_to_center)
            if cost < 1000 or cost == math.inf:
                self.debug_print("path_to_center", unit, "is free", cost)
                units_with_path.append(unit.id)
                continue
            if self.move_to_safer_spot_if_in_danger(unit, tick_number):
                self.debug_print("In danger", unit, "\n", self.parser.danger_map)
                continue
            next_pos = path_to_center[1]
            detonated_bomb = False
            for bomb in self.parser.my_armed_bombs:
                if bomb.owner_unit_id == unit.id and self.blow_up_if_worth_it(bomb.pos, tick_number, True):
                    detonated_bomb = True
                    break
            if detonated_bomb:
                continue
            already_placed_bomb = False
            for bomb in self.parser.my_bombs:
                if bomb.owner_unit_id == unit.id:
                    self.move_to_safer_spot(unit, tick_number)
                    already_placed_bomb = True
                    break
            if already_placed_bomb:
                self.debug_print("already_placed_bomb", unit)
                continue
            
            least_powerup_cost = math.inf
            powerup_path = None
            for powerup in self.parser.power_ups:
                powerup_pos = Point(powerup.get("x"), powerup.get("y"))
                path_to_powerup, powerup_cost = AStar(search_map, unit.pos, powerup_pos).run()
                should_persue_powerup = True
                for u in self.parser.my_units:
                    if u == unit:
                        continue
                    other_path, u_powerup_cost =  AStar(search_map, u.pos, powerup_pos).run()
                    if u_powerup_cost < powerup_cost:
                        should_persue_powerup = False
                        break
                    if should_persue_powerup and least_powerup_cost > cost:
                        least_powerup_cost = cost
                        powerup_path = path_to_powerup
            if least_powerup_cost != math.inf and powerup_path and len(powerup_path) > 1:
                next_pos = powerup_path[1]

            if self.parser.danger_map[next_pos.x, next_pos.y]:
                self.debug_print("Next in danger", unit, "\n", self.parser.danger_map)
                self.move_to_safer_spot(unit, tick_number)
                continue
            if self.parser.wall_map[next_pos.x, next_pos.y] and self.bombs_count < 3:
                if self.is_my_unit_near(unit.pos, equals_is_true=False):
                    continue
                if not self.parser.check_free(unit.pos, blast_r(unit.blast_diameter) + 1, blast_r(unit.blast_diameter)):
                    for neighbour in get_neighbours(search_map, unit.pos):
                        if self.parser.check_free(neighbour, blast_r(unit.blast_diameter) + 1, blast_r(unit.blast_diameter), unit.id):
                            move = self.plan_move_to_point(unit.id, unit.pos, neighbour)
                            self.execute_move(unit.id, move, neighbour, tick_number)
                            self.force_bomb_unit_ids.add(unit.id)
                            break
                    continue
                self.execute_action(BombAction(unit.id), tick_number)
                self.bombs_count += 1
                continue
            if next_pos in self.already_occupied_spots or self.parser.units_map[next_pos]:
                continue
            move = self.plan_move_to_point(unit.id, unit.pos, next_pos)
            self.execute_move(unit.id, move, next_pos, tick_number)
        # for unit_id in units_with_path:
            # self.has_no_path_to_center.remove(unit_id)
        # if not self.has_no_path_to_center:
        #     self.all_have_path_to_center = True

    def move_all_to_safer_spot(self, tick_number):
        def unit_move_importance(unit):
            return self.endgame_fire_simulator.endgame_fire_spiral[unit.pos] - self.parser.danger_map[unit.pos]
        move_order = sorted(self.parser.my_units, key=unit_move_importance)
        for unit in move_order:
            self.move_to_safer_spot(unit, tick_number, True)

    def plan_move(self, unit_id, path):
        if path is None or len(path) < 2:
            return None
        curr = path[0]
        next_move = path[1]
        return self.plan_move_to_point(unit_id, curr, next_move)

    def plan_move_to_point(self, unit_id, curr_position, target_position):
        if curr_position == target_position:
            return Action(unit_id)
        action = MoveAction.UP
        if target_position.x > curr_position.x:
            action = MoveAction.RIGHT
        if target_position.x < curr_position.x:
            action = MoveAction.LEFT
        if target_position.y < curr_position.y:
            action = MoveAction.DOWN

        return MoveAction(unit_id, action, target_pos=target_position)

    def add_closest_to_center_enemy_discount(self, unit: Unit, unit_map):
        if not unit.bombs and self.closest_to_center_unit == self.closest_to_center_enemy:
            for power_up in self.parser.power_ups:
                unit_map[power_up.get("x"), power_up.get("y")] += center_occupied_ammo_discount
            return

        my_distance = self.endgame_fire_simulator.endgame_fire_spiral[unit.pos]
        enemy_distance = self.endgame_fire_simulator.endgame_fire_spiral[self.closest_to_center_enemy.pos]

        if enemy_distance > my_distance:
            self.debug_print("{tick} Enemy {enemy} is closer "
                             "({enemy_dist} < {me_dist}) then me {me}".format(tick=self.tick_number,
                                                                              enemy=self.closest_to_center_enemy,
                                                                              enemy_dist=enemy_distance,
                                                                              me_dist=my_distance,
                                                                              me=unit))
            def should_discount(pos):
                return not self.is_my_unit_near(pos, equals_is_true=False)
            positions = filter(should_discount, get_neighbours(unit_map, unit.pos))
            for pos in positions:
                unit_map[pos] += close_to_center_enemy_discount

    def calculate_closest_to_center(self):
        enemy_max_closeness = -math.inf
        for enemy in self.parser.enemy_units:
            unit_closeness = self.endgame_fire_simulator.endgame_fire_spiral[enemy.pos]
            if unit_closeness > enemy_max_closeness:
                enemy_max_closeness = unit_closeness
                self.closest_to_center_enemy = enemy
        self.parser.my_units.sort(key=lambda my_unit: self.endgame_fire_simulator.endgame_fire_spiral[my_unit.pos], reverse=True)
        self.closest_to_center_my = self.parser.my_units[0]
        my_max_closeness = self.endgame_fire_simulator.endgame_fire_spiral[self.closest_to_center_my.pos]
        self.closest_to_center_unit = self.closest_to_center_my if \
            my_max_closeness > enemy_max_closeness else self.closest_to_center_enemy

    def move_units_to_different_map_parts(self):
        if len(self.parser.my_units) < 2:
            return
        units_to_remove = []
        for unit_id in self.unit_id_to_diff_map_side_target_pos.keys():
            if unit_id not in self.parser.unit_id_to_unit:
                units_to_remove.append(unit_id)
        for unit_id in units_to_remove:
            self.unit_id_to_diff_map_side_target_pos.pop(unit_id)
        if not self.unit_id_to_diff_map_side_target_pos:
            has_unit_in_upper_part = False
            has_unit_in_lower_part = False
            for unit in self.parser.my_units:
                if unit.pos.y >= self.parser.center.y:
                    has_unit_in_upper_part = True
                if unit.pos.y <= self.parser.center.y:
                    has_unit_in_lower_part = True
            if has_unit_in_lower_part and has_unit_in_upper_part:
                return
            
            for unit in self.parser.my_units:
                if self.is_busy(unit.id):
                    continue
                if unit == self.closest_to_center_my:
                    continue
                target_y_modifier = 1 if has_unit_in_lower_part else -1
                target_y = self.parser.center.y + target_y_modifier
                search_map = np.ones_like(self.parser.wall_map)
                search_map += self.parser.wall_map * 1000
                search_map += self.parser.endgame_fires_map * 10000
                # search_map += self.parser.danger_map
                
                for spot in self.already_occupied_spots:
                    search_map[spot] = 100000
                    
                for spot in self.blocked_locations:
                    search_map[spot] = 10000

                for other in self.parser.my_units:
                    if other.id != unit.id:
                        search_map[other.pos] = 100000
                while search_map[self.parser.center.x, target_y] > 3000 and target_y > 0 and target_y < self.parser.h-1:
                    target_y += target_y_modifier
                target = Point(self.parser.center.x, target_y)
                self.unit_id_to_diff_map_side_target_pos[unit.id] = target
                break
            
        units_reached = set()
        for unit_id, target in self.unit_id_to_diff_map_side_target_pos.items():
            unit = self.parser.unit_id_to_unit[unit_id]
            if unit.pos == target:
                units_reached.add(unit_id)
                continue
            search_map = np.ones_like(self.parser.wall_map)
            search_map += self.parser.wall_map * 1000
            search_map += self.parser.endgame_fires_map * 10000
            
            for spot in self.already_occupied_spots:
                search_map[spot] = 100000
                
            for spot in self.blocked_locations:
                search_map[spot] = 10000

            for other in self.parser.my_units:
                if other.id != unit.id:
                    search_map[other.pos] = 100000
            for enemy in self.parser.enemy_units:
                search_map[enemy.pos] = 10000
            target_y_modifier = 1 if target.y > self.parser.center.y else -1

            target_y = target.y
            while search_map[self.parser.center.x, target_y] > 3000 and target_y > 0 and target_y < self.parser.h-1:
                target_y += target_y_modifier
            target = Point(self.parser.center.x, target_y)

            if unit.pos == target:
                units_reached.add(unit_id)
                continue

            path, cost = AStar(search_map, unit.pos, target).run()

            self.debug_print("Differrent side", search_map, unit, cost, path)
            
            if self.move_to_safer_spot_if_in_danger(unit, self.tick_number):
                self.debug_print("In danger", unit, "\n", self.parser.danger_map)
                continue
            next_pos = path[1]
            detonated_bomb = False
            for bomb in self.parser.my_armed_bombs:
                if bomb.owner_unit_id == unit.id and self.blow_up_if_worth_it(bomb.pos, self.tick_number, True):
                    detonated_bomb = True
                    break
            if detonated_bomb:
                continue
            already_placed_bomb = False
            for bomb in self.parser.my_bombs:
                if bomb.owner_unit_id == unit.id:
                    self.move_to_safer_spot(unit, self.tick_number)
                    already_placed_bomb = True
                    break
            if already_placed_bomb:
                self.debug_print("already_placed_bomb", unit)
                continue
            
            least_powerup_cost = math.inf
            powerup_path = None
            for powerup in self.parser.power_ups:
                powerup_pos = Point(powerup.get("x"), powerup.get("y"))
                path_to_powerup, powerup_cost = AStar(search_map, unit.pos, powerup_pos).run()
                should_persue_powerup = True
                for u in self.parser.my_units:
                    if u == unit:
                        continue
                    other_path, u_powerup_cost =  AStar(search_map, u.pos, powerup_pos).run()
                    if u_powerup_cost < powerup_cost:
                        should_persue_powerup = False
                        break
                    if should_persue_powerup and least_powerup_cost > cost:
                        least_powerup_cost = cost
                        powerup_path = path_to_powerup
            if least_powerup_cost != math.inf and powerup_path and len(powerup_path) > 1:
                next_pos = powerup_path[1]

            if self.parser.danger_map[next_pos.x, next_pos.y]:
                self.debug_print("Next in danger", unit, "\n", self.parser.danger_map)
                self.move_to_safer_spot(unit, self.tick_number)
                continue
            if self.parser.wall_map[next_pos.x, next_pos.y] and self.bombs_count < 3:
                if self.is_my_unit_near(unit.pos, equals_is_true=False):
                    continue
                if not self.parser.check_free(unit.pos, blast_r(unit.blast_diameter) + 1, blast_r(unit.blast_diameter)):
                    continue
                self.execute_action(BombAction(unit.id), self.tick_number)
                self.bombs_count += 1
                continue
            if next_pos in self.already_occupied_spots or self.parser.units_map[next_pos]:
                continue
            move = self.plan_move_to_point(unit.id, unit.pos, next_pos)
            self.execute_move(unit.id, move, next_pos, self.tick_number)
        for unit_id in units_reached:
            self.unit_id_to_diff_map_side_target_pos.pop(unit_id) 

    def mark_detonate_bomb_danger(self, pos, blast_rad):
        maps_to_mark = [
            self.state_map,
            self.parser.danger_map
        ]
        for map in maps_to_mark:
            self.parser.raise_danger_for_potential_explosion(map, pos, explosion_danger, blast_rad)

    def is_busy(self, unit_id):
        return unit_id in self.busy

    def execute_action(self, action, tick_number):
        self.busy.add(action.unit_id)
        # self.forward.enque_action(action)
        self.tasks.append(action)

    def prod_print(self, *args):
        print("Tick #{}!\n".format(self.tick_number), *args)

    def debug_print(self, *args):
        if self.debug:
            print("Tick #{}!\n".format(self.tick_number), *args)

    async def send_action_acync_impl(self, action, tick_number):
        await action.send(self.client)
        self.prod_print("Sent action {action} on tick {tick}!".format(action=action, tick=tick_number))

    def is_my_unit_near(self, pos, equals_is_true = True) -> bool:
        enemies = 0
        for enemy in self.parser.enemy_units:
            if manhattan_distance(pos, enemy.pos) == 1:
                enemy_weight = 2 if enemy == self.closest_to_center_unit else 1
                if enemy.invincibility_last_tick and enemy.invincibility_last_tick > self.tick_number:
                    enemy_weight *= 0.1
                self.debug_print("near enemy", enemy, enemy_weight)
                enemies += enemy_weight
        my = 0
        for other in self.parser.my_units:
            if manhattan_distance(pos, other.pos) == 1:
                my_weight = 2 if other == self.closest_to_center_unit else 1
                if other.invincibility_last_tick and other.invincibility_last_tick > self.tick_number:
                    my_weight *= 0.1
                self.debug_print("near my", other, my_weight)
                my += my_weight
        return my > enemies or my == enemies and equals_is_true 
