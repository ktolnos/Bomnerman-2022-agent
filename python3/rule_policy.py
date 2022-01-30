import asyncio
import math
import random

from actions import MoveAction, BombAction, DetonateBombAction, Action
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


class RulePolicy:

    def __init__(self):
        self.busy = set()  # units that already made the move

    def execute_actions(self, tick_number, game_state, client):
        self.busy.clear()
        self.client = client
        self.parser = Parser(tick_number, game_state)

        self.blow_up_enemies()
        self.collect_power_ups()
        self.place_bombs()
        self.move_at_random_safe_spot()

    def compute_map(self):
        self.path_map = np.ones_like(self.parser.danger_map)
        self.path_map[self.parser.walkable_map == 1] = math.inf
        self.path_map

    def blow_up_enemies(self):
        for enemy in self.parser.enemy_units:
            enemy_coords = point(enemy)
            bomb = self.parser.my_bomb_explosion_map_objects[enemy_coords.x][enemy_coords.y]
            if bomb is not None:
                unit_id = bomb.get(owner_init_id)
                if self.is_busy(unit_id):
                    continue
                self.execute_action(DetonateBombAction(unit_id, bomb))

    def collect_power_ups(self):
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
                self.execute_action(move)
                busy_powerups.append(path.destination)

    def place_bombs(self):
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
                    self.execute_action(BombAction(unit_id))

    def move_at_random_safe_spot(self):
        for unit in self.parser.my_units:
            if self.is_busy(uid(unit)):
                continue
            pos = point(unit)
            neighbours = get_neighbours(grid=self.parser.walkable_map, center=pos, include_center=True)
            min_danger_neighbours = []
            min_danger = 100000
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
            self.execute_action(action)

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

    def execute_action(self, action):
        self.busy.add(action.unit_id)
        asyncio.create_task(action.send(self.client))
