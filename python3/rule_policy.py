import asyncio
import time
from collections import deque, Counter

from actions import MoveAction, BombAction, DetonateBombAction, Action
from astar import AStar
from engame_fire_simulator import EndgameFireSimulator
from least_cost_search import LeastCostSearch
from parser import *
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
        self.last_was_cancelled = False
        self.closest_to_center_unit = None
        self.closest_to_center_my = None
        self.closest_to_center_enemy = None
        self.debug = False

    def init(self, client, ticker):
        self.client = client
        self.ticker = ticker

    def execute_actions(self, tick_number, game_state):
        if tick_number != self.ticker.tick:
            self.tick_number = tick_number
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
            self.last_was_cancelled = True
            return

        clear_time = time.time()

        self.parser = Parser(tick_number, game_state, calculate_wall_map=not self.all_have_path_to_center)
        parsing_time = time.time()
        self.compute_state_map()
        self.calculate_closest_to_center()
        if tick_number != self.ticker.tick:
            self.schedule_print("Cancelling policy call after parsing for tick #{}".format(tick_number))
            self.last_was_cancelled = True
            return

        self.blow_up_path_to_center(tick_number)
        path_to_center_time = time.time()

        if tick_number != self.ticker.tick:
            self.schedule_print("Cancelling policy call after path to center for tick #{}".format(tick_number))
            self.last_was_cancelled = True
            return

        self.blow_up_enemies(tick_number)
        blow_up_time = time.time()

        if tick_number != self.ticker.tick:
            self.schedule_print("Cancelling policy call after blow up for tick #{}".format(tick_number))
            self.last_was_cancelled = True
            return

        self.place_bombs(tick_number)
        bombs_time = time.time()

        if tick_number != self.ticker.tick:
            self.schedule_print("Cancelling policy call after place bombs for tick #{}".format(tick_number))
            self.last_was_cancelled = True
            return

        self.move_all_to_safer_spot(tick_number)
        move_to_spot_time = time.time()

        if tick_number != self.ticker.tick:
            self.schedule_print("Cancelling policy call after move all for tick #{}".format(tick_number))
            self.last_was_cancelled = True
            return

        self.loop.run_until_complete(asyncio.gather(*self.tasks))
        tasks_time = time.time()

        if tick_number != self.ticker.tick:
            self.schedule_print("Cancelling policy call after tasks for tick #{}".format(tick_number))
            self.last_was_cancelled = True
            return

        while not self.debug and not self.last_was_cancelled and self.print_queue:
            if tick_number != self.ticker.tick:
                self.last_was_cancelled = True
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
        self.last_was_cancelled = False

    def compute_state_map(self):
        self.state_map = np.ones_like(self.parser.danger_map) * 3

        self.state_map += self.parser.walkable_map
        self.state_map += self.parser.danger_map
        self.state_map += self.endgame_fire_simulator.get_endgame_fire_danger(self.parser.endgame_fires)

    def blow_up_enemies(self, tick_number):
        bomb_to_enemies = Counter()
        for enemy in self.parser.enemy_units:
            bomb = self.parser.my_bomb_explosion_map_objects[enemy.pos.x][enemy.pos.y]
            if bomb is not None:
                bomb_to_enemies[bomb] += 1
        bomb_to_my_units = Counter()
        for unit in self.parser.my_units:
            bomb = self.parser.my_bomb_explosion_map_objects[unit.pos.x][unit.pos.y]
            if bomb is not None:
                bomb_to_my_units[bomb] += 1
        for bomb in bomb_to_enemies:
            if bomb_to_enemies[bomb] > bomb_to_my_units[bomb]:
                unit_id = bomb.owner_unit_id
                if self.is_busy(unit_id):
                    continue
                self.execute_action(DetonateBombAction(unit_id, bomb), tick_number)

    def place_bombs(self, tick_number):
        for unit in self.parser.my_units:
            if self.is_busy(unit.id):
                continue
            if not unit.bombs:
                continue
            if unit == self.closest_to_center_unit:
                self.debug_print(tick_number, "Placing bomb", unit, "is closest to center")
                continue
            else:
                self.debug_print(tick_number, "Placing bomb", unit, "is NOT closest to center, closest is ",
                                 self.closest_to_center_unit,
                                 self.endgame_fire_simulator.endgame_fire_spiral[unit.pos],
                                 self.endgame_fire_simulator.endgame_fire_spiral[self.closest_to_center_unit.pos])

            stands_on_bomb = False
            for bomb in self.parser.my_bombs:
                if unit.pos == bomb.pos:
                    stands_on_bomb = True
                    break
            if stands_on_bomb:
                continue

            my_unit_is_near = False
            for other in self.parser.my_units:
                if manhattan_distance(unit.pos, other.pos) == 1:
                    my_unit_is_near = True
                    break  # don't blow up allies
            if my_unit_is_near:
                continue

            wm = self.parser.walkable_map
            pos = unit.pos
            can_escape = False
            if unit.pos.x > 0 and wm[pos.x - 1, pos.y] != math.inf:
                can_escape = True
            if not can_escape and unit.pos.x < self.parser.w - 1 and wm[pos.x + 1, pos.y] != math.inf:
                can_escape = True
            if not can_escape and unit.pos.y > 0 and wm[pos.x, pos.y - 1] != math.inf:
                can_escape = True
            if not can_escape and unit.pos.y < self.parser.h - 1 and wm[pos.x, pos.y + 1] != math.inf:
                can_escape = True
            if not can_escape:
                continue

            for enemy in self.parser.enemy_units:
                for other in self.parser.my_units:
                    self.debug_print(tick_number,
                                     "Placing bomb, distance to other is {}".format(
                                         manhattan_distance(unit.pos, other.pos)))
                if manhattan_distance(unit.pos, enemy.pos) == 1:
                    self.execute_action(BombAction(unit.id), tick_number)
                    break

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
        unit_map = np.copy(self.state_map)
        unit_close_cell_danger = np.copy(self.parser.cell_occupation_danger_map)
        if unit_map[unit.pos] == math.inf:
            unit_map[unit.pos] = stand_on_bomb_danger
        for other_unit in self.parser.my_units:
            if other_unit == unit:
                continue
            unit_map[other_unit.pos] = math.inf
            draw_cross(unit_close_cell_danger, other_unit.pos.x, other_unit.pos.y, rad=2, value=close_cell_danger)
        unit_map += np.square(unit_close_cell_danger)
        self.add_closest_to_center_enemy_discount(unit, unit_map)
        if unit != self.closest_to_center_unit:
            for power_up in self.parser.power_ups:
                unit_map[power_up.get("x"), power_up.get("y")] += power_up_discount
            for enemy in self.parser.enemy_units:
                draw_cross(unit_map, enemy.pos.x, enemy.pos.y, rad=2, value=close_enemy_discount)

        unit_map[self.parser.center] += endgame_fire_center_discount * unit.hp
        unit_map[self.parser.center.x - 1::self.parser.center.x + 2,
        self.parser.center.y - 1::self.parser.center.y + 2] += endgame_fire_center_discount_mass

        for spot in self.already_occupied_spots:
            unit_map[spot] = math.inf

        search_budget = search_budget_small if self.last_was_cancelled else search_budget_big
        least_cost_search = LeastCostSearch(unit_map, unit.pos,
                                            exclude_points=self.already_occupied_destinations,
                                            search_budget=search_budget)

        safest_path, cost = least_cost_search.run(horizon=search_horizon)
        self.already_occupied_destinations.add(safest_path[-1])
        self.debug_print(unit_map, unit, safest_path, cost)
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
                    continue
                unit = self.parser.unit_id_to_unit[unit_id]
                if self.is_busy(unit.id):
                    self.debug_print("path_to_center", unit, "is busy")
                    continue
                path_to_center, cost = AStar(search_map, unit.pos, self.parser.center).run()

                self.debug_print(self.parser.wall_map, "\n", unit, cost, path_to_center)
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
                    if bomb.owner_unit_id == unit.id:
                        self.execute_action(DetonateBombAction(unit.id, bomb), tick_number)
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

                if self.parser.wall_map[next_pos.x, next_pos.y]:
                    self.execute_action(BombAction(unit.id), tick_number)
                    continue
                if self.parser.danger_map[next_pos.x, next_pos.y]:
                    self.debug_print("Next in danger", unit, "\n", self.parser.danger_map)
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

    def add_closest_to_center_enemy_discount(self, unit: Unit, unit_map):
        if not unit.bombs and self.closest_to_center_unit == self.closest_to_center_enemy:
            for power_up in self.parser.power_ups:
                unit_map[power_up.get("x"), power_up.get("y")] += center_occupied_ammo_discount
            return

        my_distance = self.endgame_fire_simulator.endgame_fire_spiral[unit.pos]
        enemy_distance = self.endgame_fire_simulator.endgame_fire_spiral[self.closest_to_center_enemy.pos]

        if enemy_distance < my_distance:
            self.debug_print("{tick} Enemy {enemy} is closer "
                             "({enemy_dist} < {me_dist}) then me {me}".format(tick=self.tick_number,
                                                                              enemy=self.closest_to_center_enemy,
                                                                              enemy_dist=enemy_distance,
                                                                              me_dist=my_distance,
                                                                              me=unit))
            draw_cross(unit_map, self.closest_to_center_enemy.pos.x, self.closest_to_center_enemy.pos.y, rad=2,
                       value=close_to_center_enemy_discount)

    def calculate_closest_to_center(self):
        enemy_min_distance = math.inf
        for enemy in self.parser.enemy_units:
            unit_distance = self.endgame_fire_simulator.endgame_fire_spiral[enemy.pos]
            if unit_distance < enemy_min_distance:
                enemy_min_distance = unit_distance
                self.closest_to_center_enemy = enemy
        my_min_distance = math.inf
        for my_unit in self.parser.my_units:
            unit_distance = self.endgame_fire_simulator.endgame_fire_spiral[my_unit.pos]
            if unit_distance < my_min_distance:
                my_min_distance = unit_distance
                self.closest_to_center_my = my_unit
        self.closest_to_center_unit = self.closest_to_center_my if \
            my_min_distance < enemy_min_distance else self.closest_to_center_enemy

    def is_busy(self, unit_id):
        return unit_id in self.busy

    def execute_action(self, action, tick_number):
        self.busy.add(action.unit_id)
        self.tasks.append(self.loop.create_task(self.send_action_acync_impl(action, tick_number)))

    def schedule_print(self, *args):
        self.debug_print(*args)
        self.print_queue.append(("Tick #{}!\n".format(self.tick_number),) + args)

    def debug_print(self, *args):
        if self.debug:
            print("Tick #{}!\n".format(self.tick_number), args)

    async def send_action_acync_impl(self, action, tick_number):
        if tick_number != self.ticker.tick:
            self.schedule_print("Action for tick {action_tick} is only sent on {curr_tick}, cancelling".format(
                action_tick=tick_number, curr_tick=self.ticker.tick
            ))
            return
        await action.send(self.client)
        self.schedule_print("Sent action {action} on tick {tick}!".format(action=action, tick=tick_number))
