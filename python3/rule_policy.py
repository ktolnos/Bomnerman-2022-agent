import asyncio
import math
import random

from actions import MoveAction, BombAction, DetonateBombAction, Action
from least_cost_search import LeastCostSearch
from parser import Parser, owner_init_id
from astar import AStar
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

    def init(self, client, ticker):
        self.client = client
        self.ticker = ticker

    def execute_actions(self, tick_number, game_state):
        self.tick_number = tick_number

        self.busy.clear()
        for task in self.tasks:
            task.cancel()
        self.tasks.clear()

        if tick_number != self.ticker.tick:
            print("0 Cancelling policy call for tick #{}".format(tick_number))
            return

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.parser = Parser(tick_number, game_state)

        if tick_number != self.ticker.tick:
            print("1 Cancelling policy call for tick #{}".format(tick_number))
            return

        self.compute_state_map()


        self.blow_up_enemies(tick_number)
        # self.collect_power_ups()
        self.place_bombs(tick_number)

        if tick_number != self.ticker.tick:
            print("2 Cancelling policy call for tick #{}".format(tick_number))
            return
        self.move_at_safer_spot(tick_number)
        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    def compute_state_map(self):
        self.state_map = np.zeros_like(self.parser.danger_map)
        self.state_map[self.parser.walkable_map == 1] = math.inf
        self.state_map += self.parser.danger_map

    def blow_up_enemies(self, tick_number):
        for enemy in self.parser.enemy_units:
            enemy_coords = point(enemy)
            bomb = self.parser.my_bomb_explosion_map_objects[enemy_coords.x][enemy_coords.y]
            if bomb is not None:
                unit_id = bomb.get(owner_init_id)
                if self.is_busy(unit_id):
                    continue
                self.execute_action(DetonateBombAction(unit_id, bomb), tick_number)

    def collect_power_ups(self, tick_number):
        paths = []
        for power_up in self.parser.power_ups:
            tar_x, tar_y = power_up.get("x"), power_up.get("y")
            for unit in self.parser.my_units:
                if self.is_busy(uid(unit)):
                    continue
                path = AStar(self.parser.walkable_map,
                             point(unit),
                             Point(tar_x, tar_y),
                             0).run()
                paths.append(PathProposal(path, unit, power_up))
        paths.sort()
        busy_powerups = []
        for path in paths:
            if self.is_busy(uid(path.unit)):
                continue
            if path.destination in busy_powerups:
                continue
            move = self.plan_move(uid(path.unit), path.path)
            if move:
                self.execute_action(move, tick_number)
                busy_powerups.append(path.destination)

    def place_bombs(self, tick_number):
        for unit in self.parser.my_units:
            unit_id = uid(unit)
            if self.is_busy(unit_id):
                continue
            if not unit.get("inventory").get("bombs"):
                continue
            unit_pos = point(unit)
            if self.parser.entities_map[unit_pos.x][unit_pos.y] is not None:
                continue
            for enemy in self.parser.enemy_units:
                if AStar.h_score(unit_pos, point(enemy)) < blast_r(unit.get("blast_diameter")):
                    self.execute_action(BombAction(unit_id), tick_number)

    def move_at_safer_spot(self, tick_number):
        already_occupied_spots = list()
        for unit in self.parser.my_units:
            unit_id = uid(unit)
            if self.is_busy(unit_id):
                continue
            pos = point(unit)
            unit_map = np.copy(self.state_map)
            unit_map[pos.x, pos.y] = self.parser.danger_map[pos.x, pos.y]
            for spot in already_occupied_spots:
                unit_map[spot.x, spot.y] = math.inf
            least_cost_search = LeastCostSearch(unit_map, pos, search_budget=10000)
            safest_path, cost = least_cost_search.run(horizon=10)
            self.print_async(unit_map, pos, safest_path, cost)
            move = self.plan_move(unit_id, safest_path)
            move_cell = safest_path[1] if move else pos
            already_occupied_spots.append(move_cell)
            if move:
                self.print_async(move.action)
                self.execute_action(move, tick_number)
            else:
                self.execute_action(Action(unit_id), tick_number)
            if tick_number != self.ticker.tick:
                print("3 Cancelling policy call for tick #{}".format(tick_number))
                return

    def move_at_random_safe_spot(self, tick_number):
        for unit in self.parser.my_units:
            if self.is_busy(uid(unit)):
                continue
            pos = point(unit)
            neighbours = get_neighbours(grid=self.parser.walkable_map, center=pos, include_center=True)
            min_danger_neighbours = []
            min_danger = math.inf
            for neighbour in neighbours:
                danger = self.parser.danger_map[neighbour.x, neighbour.y]
                if danger == min_danger:
                    min_danger_neighbours.append(neighbour)
                if danger < min_danger:
                    min_danger_neighbours.clear()
                    min_danger_neighbours.append(neighbour)
                    min_danger = danger

            target = random.choice(min_danger_neighbours)
            action = self.plan_move_to_point(uid(unit), pos, target)
            self.execute_action(action, tick_number)

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

    def print_async(self, *args):
        self.tasks.append(self.loop.create_task(self.print_async_impl(*args)))

    async def print_async_impl(self, *args):
        print("Tick #{}".format(self.tick_number), *args)

    async def send_action_acync_impl(self, action, tick_number):
        if tick_number != self.ticker.tick:
            print("Action for tick {action_tick} is only sent on {curr_tick}".format(
                action_tick=tick_number, curr_tick=self.ticker.tick
            ))
            return
        await action.send(self.client)
        print("Sent action for unit {unit_id} on tick {tick}".format(unit_id=action.unit_id, tick=tick_number))
