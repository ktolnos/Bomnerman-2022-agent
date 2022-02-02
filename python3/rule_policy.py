import asyncio
import copy
import math
import time
from collections import deque

from actions import MoveAction, BombAction, DetonateBombAction, Action
from astar import AStar
from engame_fire_simulator import EndgameFireSimulator
from least_cost_search import LeastCostSearch
from parser import Parser, owner_init_id, power_up_discount, search_budget, draw_cross, close_cell_danger, \
    search_horizon
from utils import *


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
        self.endgame_fire_simulator = EndgameFireSimulator(15, 15)
        self.has_no_path_to_center = None
        self.all_have_path_to_center = False
        self.already_occupied_spots = list()
        self.already_occupied_destinations = set()
        self.loop = None
        self.print_queue = deque()
        self.parser = None
        self.client = None
        self.ticker = None

    def init(self, client, ticker):
        self.client = client
        self.ticker = ticker

    def execute_actions(self, tick_number, game_state):
        if tick_number != self.ticker.tick:
            self.schedule_print("Cancelling policy right away for tick #{}".format(tick_number))
            return

        start_time = time.time()
        self.tick_number = tick_number

        self.busy.clear()
        for task in self.tasks:
            task.cancel()
        self.tasks.clear()
        self.already_occupied_spots.clear()
        self.already_occupied_destinations.clear()

        if not self.loop:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        if tick_number != self.ticker.tick:
            self.schedule_print("Cancelling policy call after clear for tick #{}".format(tick_number))
            return

        clear_time = time.time()

        self.parser = Parser(tick_number, game_state, calculate_wall_map=not self.all_have_path_to_center)
        parsing_time = time.time()
        self.compute_state_map()
        if tick_number != self.ticker.tick:
            self.schedule_print("Cancelling policy call after parsing for tick #{}".format(tick_number))
            return

        self.blow_up_path_to_center(tick_number)
        path_to_center_time = time.time()

        if tick_number != self.ticker.tick:
            self.schedule_print("Cancelling policy call after path to center for tick #{}".format(tick_number))
            return

        self.blow_up_enemies(tick_number)
        blow_up_time = time.time()

        if tick_number != self.ticker.tick:
            self.schedule_print("Cancelling policy call after blow up for tick #{}".format(tick_number))
            return

        self.place_bombs(tick_number)
        bombs_time = time.time()

        if tick_number != self.ticker.tick:
            self.schedule_print("Cancelling policy call after place bombs for tick #{}".format(tick_number))
            return

        self.move_all_to_safer_spot(tick_number)
        move_to_spot_time = time.time()

        if tick_number != self.ticker.tick:
            self.schedule_print("Cancelling policy call after move all for tick #{}".format(tick_number))
            return

        self.loop.run_until_complete(asyncio.gather(*self.tasks))
        tasks_time = time.time()

        if tick_number != self.ticker.tick:
            self.schedule_print("Cancelling policy call after tasks for tick #{}".format(tick_number))
            return

        while self.print_queue:
            if tick_number != self.ticker.tick:
                return
            print(*self.print_queue.popleft())
        printing_time = time.time()

        total_time = (time.time() - start_time) * 1000
        self.schedule_print("Tick #{tick},"
                            " total time is {time}ms,\n"
                            " clear_time={clear_time}\n"
                            " path_to_center_time={path_to_center_time}\n"
                            " blow_up_time={blow_up_time}\n"
                            " bombs_time={bombs_time}\n"
                            " move_to_spot_time={move_to_spot_time}\n"
                            " tasks_time={tasks_time}\n"
                            " printing_time={printing_time}\n"
                            "".format(tick=tick_number, time=total_time,
                                      clear_time=(clear_time - start_time) * 1000,
                                      parsing_time=(parsing_time - clear_time) * 1000,
                                      path_to_center_time=(path_to_center_time - parsing_time) * 1000,
                                      blow_up_time=(blow_up_time - path_to_center_time) * 1000,
                                      bombs_time=(bombs_time - blow_up_time) * 1000,
                                      move_to_spot_time=(move_to_spot_time - bombs_time) * 1000,
                                      tasks_time=(tasks_time - move_to_spot_time) * 1000,
                                      printing_time=(printing_time - tasks_time) * 1000))

    def compute_state_map(self):
        self.state_map = np.ones_like(self.parser.danger_map)

        for power_up in self.parser.power_ups:
            self.state_map[power_up.get("x"), power_up.get("y")] -= power_up_discount

        self.state_map += self.parser.walkable_map
        self.state_map += self.parser.danger_map
        self.state_map += self.endgame_fire_simulator.get_endgame_fire_danger(self.parser.endgame_fires)
        self.state_map += self.parser.cell_occupation_danger_map

    def blow_up_enemies(self, tick_number):
        for enemy in self.parser.enemy_units:
            bomb = self.parser.my_bomb_explosion_map_objects[enemy.pos.x][enemy.pos.y]
            if bomb is not None:
                unit_id = bomb.get(owner_init_id)
                if self.is_busy(unit_id):
                    continue
                self.execute_action(DetonateBombAction(unit_id, bomb), tick_number)

    def place_bombs(self, tick_number):
        for unit in self.parser.my_units:
            if self.is_busy(unit.id):
                continue
            if not unit.bombs:
                continue
            if self.parser.entities_map[unit.pos.x][unit.pos.y] is not None:
                continue
            for enemy in self.parser.enemy_units:
                if AStar.h_score(unit.pos, enemy.pos) < blast_r(unit.blast_diameter):
                    self.execute_action(BombAction(unit.id), tick_number)

    def move_to_safer_spot_if_in_danger(self, unit, tick_number) -> bool:
        """
        :return: True if unit submitted action
        """
        if self.parser.danger_map[unit.pos] != 0:
            self.move_to_safer_spot(unit, tick_number)
            return True
        return False

    def move_to_safer_spot(self, unit, tick_number) -> bool:
        """
        :return: True if unit moved
        """
        if self.is_busy(unit.id):
            return False
        unit_map = copy.deepcopy(self.state_map)
        if unit_map[unit.pos] == math.inf:
            unit_map[unit.pos] = 999  # allows to choose path with non-infinite cost
        for other_unit in self.parser.my_units:
            if other_unit == unit:
                continue
            unit_map[other_unit.pos] = math.inf
            draw_cross(unit_map, other_unit.pos.x, other_unit.pos.y, rad=1, value=close_cell_danger)

        for spot in self.already_occupied_spots:
            unit_map[spot] = math.inf

        least_cost_search = LeastCostSearch(unit_map, unit.pos,
                                            exclude_points=self.already_occupied_destinations,
                                            search_budget=search_budget)

        safest_path, cost = least_cost_search.run(horizon=search_horizon)
        self.already_occupied_destinations.add(safest_path[-1])
        self.schedule_print(unit_map, unit, safest_path, cost)
        move = self.plan_move(unit.id, safest_path)
        move_cell = safest_path[1] if move else unit.pos
        return self.execute_move(unit.id, move, move_cell, tick_number)

    def execute_move(self, unit_id, move, move_cell, tick_number) -> bool:
        self.already_occupied_spots.append(move_cell)
        if move:
            self.execute_action(move, tick_number)
            return True
        else:
            self.execute_action(Action(unit_id), tick_number)
            return False

    def blow_up_path_to_center(self, tick_number):
        if not self.all_have_path_to_center:
            if not self.has_no_path_to_center:
                self.has_no_path_to_center = self.parser.my_unit_ids
            units_with_path = list()

            search_map = np.ones_like(self.parser.wall_map)
            search_map += self.parser.wall_map * 1000

            for unit_id in self.has_no_path_to_center:
                if unit_id not in self.parser.unit_id_to_unit:
                    # unit is dead
                    units_with_path.append(unit_id)
                unit = self.parser.unit_id_to_unit[unit_id]
                if self.is_busy(unit.id):
                    self.schedule_print("path_to_center", unit, "is busy")
                    continue
                path_to_center, cost = AStar(search_map, unit.pos, self.parser.center).run()

                self.schedule_print(self.parser.wall_map, "\n", unit, cost, path_to_center)
                if cost < 1000 or cost == math.inf:
                    self.schedule_print("path_to_center", unit, "is free", cost)
                    units_with_path.append(unit.id)
                    continue
                if self.move_to_safer_spot_if_in_danger(unit, tick_number):
                    self.schedule_print("In danger", unit, "\n", self.parser.danger_map)
                    continue
                next_pos = path_to_center[1]
                detonated_bomb = False
                for bomb in self.parser.my_armed_bombs:
                    if bomb.get(owner_init_id) == unit.id:
                        self.execute_action(DetonateBombAction(unit.id, bomb), tick_number)
                        detonated_bomb = True
                        break
                if detonated_bomb:
                    continue
                already_placed_bomb = False
                for bomb in self.parser.my_bombs:
                    if bomb.get(owner_init_id) == unit.id:
                        self.move_to_safer_spot(unit, tick_number)
                        already_placed_bomb = True
                        break
                if already_placed_bomb:
                    self.schedule_print("already_placed_bomb", unit)
                    continue

                if self.parser.wall_map[next_pos.x, next_pos.y]:
                    self.execute_action(BombAction(unit.id), tick_number)
                    continue
                if self.parser.danger_map[next_pos.x, next_pos.y]:
                    self.schedule_print("Next in danger", unit, "\n", self.parser.danger_map)
                    self.move_to_safer_spot(unit, tick_number)
                    continue
                move = self.plan_move_to_point(unit.id, unit.pos, next_pos)
                self.already_occupied_spots.append(next_pos)
                self.execute_move(unit.id, move, next_pos, tick_number)
            for unit_id in units_with_path:
                self.has_no_path_to_center.remove(unit_id)
            if not self.has_no_path_to_center:
                self.all_have_path_to_center = True

    def move_all_to_safer_spot(self, tick_number):
        for unit in self.parser.my_units:
            self.move_to_safer_spot(unit, tick_number)

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

        return MoveAction(unit_id, action)

    def is_busy(self, unit_id):
        return unit_id in self.busy

    def execute_action(self, action, tick_number):
        self.busy.add(action.unit_id)
        self.tasks.append(self.loop.create_task(self.send_action_acync_impl(action, tick_number)))

    def schedule_print(self, *args):
        self.print_queue.append(("Tick #{}!\n".format(self.tick_number),) + args)

    async def send_action_acync_impl(self, action, tick_number):
        if tick_number != self.ticker.tick:
            self.schedule_print("Action for tick {action_tick} is only sent on {curr_tick}, cancelling".format(
                action_tick=tick_number, curr_tick=self.ticker.tick
            ))
            return
        await action.send(self.client)
        self.schedule_print("Sent action {action} on tick {tick}!".format(action=action, tick=tick_number))
