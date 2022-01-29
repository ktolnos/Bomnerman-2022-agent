import asyncio
import random

from actions import MoveAction, BombAction, DetonateBombAction
from parser import Parser, owner_init_id
from pathfinding import AStar
from utils import *


@dataclass
class PathProposal:
    path: list
    unit: dict
    destination: dict

    def __lt__(self, other):
        return len(self.path) < len(other.path)


class Policy:

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
            neighbors = AStar(self.parser.walkable_map, Point(0, 0), Point(0, 0), 0).get_neighbors(pos)
            list_neighbours = list(neighbors)
            if not list_neighbours:
                continue
            not_dangerous = []
            not_potential_explosion = []
            for n in list_neighbours:
                if self.parser.dangerous_map[n.x, n.y] == 0:
                    not_dangerous.append(n)
                if self.parser.all_bomb_explosion_map[n.x, n.y] == 0:
                    not_potential_explosion.append(n)
            target_list = not_dangerous if not_dangerous \
                else not_potential_explosion if not_potential_explosion \
                else list_neighbours
            target = random.choice(target_list)
            action = self.plan_move_to_point(uid(unit), pos, target)
            self.execute_action(action)

    def plan_move(self, unit_id, path):
        if path is None or len(path) < 2:
            return None
        curr = path[0]
        next_move = path[1]
        return self.plan_move_to_point(unit_id, curr, next_move)

    def plan_move_to_point(self, unit_id, curr_position, target_position):
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
