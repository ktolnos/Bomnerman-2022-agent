import asyncio
import json
from collections import deque

from engame_fire_simulator2 import EndgameFireSimulator2
from game_state import GameState
from game_utils import point
from parser import Parser, math, blast_r, draw_cross_assign, Point
from rule_policy import np

w, h = 15, 15
observation_layers = 17
screen_shape = (w, h, observation_layers)
walls_layer = 0
my_units_layer = 1
enemy_units_layer = 2
my_bombs_layer = 3
enemy_bombs_layer = 4
explosions_layer = 5
my_bomb_future_explosions_layer = 6
enemy_bomb_future_explosions_layer = 7
my_invincibility = 8
enemy_invincibility = 9
my_explosion_radius = 10
enemy_explosion_radius = 11
my_hp = 12
enemy_hp = 13
endgame_fire = 14
steps_to_center = 15
tick_layer = 16

bomb_future_explosion_base = 0.5
explosion_base = 0.3
explosion_with_ticks_max = 0.6
bomb_future_explosion_max_ticks = 40
invincibility_ticks = 6
explosion_ticks = 10
max_tick = 300 + 15*15*2 + 2

unit_actions_size = 6
action_noop = 0
action_move_up = 1
action_move_down = 2
action_move_left = 3
action_move_right = 4
action_place_bomb = 5

bomb_actions_size = 2
bomb_action_noop = 0
bomb_action_detonate = 1

endgame_fire_simulator = EndgameFireSimulator2(w, h)


def calc_invincibility(unit, tick_number):
    if unit.invincibility_last_tick == 0:
        return 0
    if unit.invincibility_last_tick < tick_number:
        return 0
    return (unit.invincibility_last_tick - tick_number + 1) / invincibility_ticks


def calc_steps_to_center(parser):
    wall_map = parser.wall_map
    start_cell = parser.center
    queue = deque()
    queue.append((start_cell, 1))
    result = np.zeros((w, h))
    while queue:
        (cell, dist) = queue.pop()
        cost = 1
        if wall_map[cell]:
            cost = wall_map[cell] * 20
        if result[cell] and result[cell] <= dist:
            continue
        result[cell] = dist
        x, y = cell
        if x > 0:
            queue.appendleft((Point(x - 1, y), dist+cost))
        if x < w - 1:
            queue.appendleft((Point(x + 1, y), dist+cost))
        if y > 0:
            queue.appendleft((Point(x, y - 1), dist+cost))
        if y < h - 1:
            queue.appendleft((Point(x, y + 1), dist+cost))
    return result


def calc_steps_to_center_layer(parser):
    steps = calc_steps_to_center(parser)
    steps[steps == math.inf] = -1
    max_steps = np.max(steps)
    steps[steps == -1] = max_steps + 10
    steps /= max_steps + 10
    return 1. - np.sqrt(steps)


def populate_actions(tick, game_state, unit_actions, unit_mask, unit_action_freq,
                     bomb_actions, bomb_mask, bomb_action_freq, tick_number, parser, my_unit_ids):
    acted_unit_ids = set()
    detonated_bombs = set()
    total_unit_actions = 0
    if tick:
        for event in tick["events"]:
            if event["type"] == "unit":
                action_data = event["data"]
                unit_id = action_data["unit_id"]
                if unit_id not in my_unit_ids:
                    continue
                acted_unit_ids.add(unit_id)
                unit_pos = point(game_state["unit_state"][unit_id])
                action_pos = unit_pos
                action = action_noop
                if action_data["type"] == "bomb":
                    action = action_place_bomb
                elif action_data["type"] == "move":
                    direction = action_data["move"]
                    if direction == "up":
                        action = action_move_up
                    if direction == "down":
                        action = action_move_down
                    if direction == "left":
                        action = action_move_left
                    if direction == "right":
                        action = action_move_right
                elif action_data["type"] == "detonate":
                    detonation_pos = action_data["coordinates"]
                    detonation_pos = Point(detonation_pos[0], detonation_pos[1])
                    detonated_bombs.add(detonation_pos)
                    bomb_actions[tick_number - 1, detonation_pos[0], detonation_pos[1], bomb_action_detonate] = 1
                    bomb_mask[tick_number - 1, detonation_pos[0], detonation_pos[1]] = 1
                    bomb_action_freq[bomb_action_detonate] += 1
                if action != action_noop:
                    unit_actions[tick_number - 1, action_pos[0], action_pos[1], action] = 1
                    unit_mask[tick_number - 1, action_pos[0], action_pos[1]] = 1
                    unit_action_freq[action] += 1
                    total_unit_actions += 1
    for unit in parser.my_units:
        if unit.id not in acted_unit_ids:
            unit_actions[tick_number - 1, unit.pos[0], unit.pos[1], action_noop] = 1
            unit_mask[tick_number - 1, unit.pos[0], unit.pos[1]] = 1
            unit_action_freq[action_noop] += 1
            total_unit_actions += 1
    for bomb in parser.my_armed_bombs:
        if bomb.pos not in detonated_bombs:
            bomb_actions[tick_number - 1, bomb.pos[0], bomb.pos[1], bomb_action_noop] = 1
            bomb_mask[tick_number - 1, bomb.pos[0], bomb.pos[1]] = 1
            bomb_action_freq[bomb_action_noop] += 1
    if total_unit_actions > 3:
        assert False, "more than 3 units acted"


def draw_layer(rgb, screen, layer, r, g, b, alpha=1.):
    layer_of_screen = screen[layer, :, :] * alpha
    result = np.ones_like(rgb)
    result[:, :, 0] *= r
    result[:, :, 1] *= g
    result[:, :, 2] *= b
    # repeated layer is basically 1-alpha for each pixel
    repeated_layer = np.repeat(layer_of_screen[np.newaxis, :, :], axis=0, repeats=3)
    repeated_layer = np.moveaxis(repeated_layer, 0, -1)
    rgb *= 1 - repeated_layer
    rgb += result * repeated_layer


class ObservationConverter:
    def __init__(self):
        self.steps_layer = None
        self.parser = None

    def convert(self, game_state, tick_number, pov_agent_id=None):
        screen = np.zeros(screen_shape)
        parser = Parser(tick_number, game_state, calculate_wall_map=True, pov_agent_id=pov_agent_id)
        self.parser = parser
        if self.steps_layer is None:
            self.steps_layer = calc_steps_to_center_layer(parser)
        walls = parser.wall_map / 5
        walls[walls == math.inf] = 1
        screen[:, :, walls_layer] = walls
        for unit in parser.my_units:
            screen[unit.pos.x, unit.pos.y, my_units_layer] = 1
            screen[unit.pos.x, unit.pos.y, my_hp] = unit.hp / 3.
            if unit.bombs:
                draw_cross_assign(screen[:, :, my_explosion_radius], unit.pos.x, unit.pos.y,
                                  blast_r(unit.blast_diameter), 1.)
            screen[unit.pos.x, unit.pos.y, my_invincibility] = calc_invincibility(unit, tick_number)
        for enemy in parser.enemy_units:
            screen[enemy.pos.x, enemy.pos.y, enemy_units_layer] = 1
            screen[enemy.pos.x, enemy.pos.y, enemy_hp] = enemy.hp / 3.
            if enemy.bombs:
                draw_cross_assign(screen[:, :, enemy_explosion_radius], enemy.pos.x, enemy.pos.y,
                                  blast_r(enemy.blast_diameter), 1.)
            screen[enemy.pos.x, enemy.pos.y, enemy_invincibility] = calc_invincibility(enemy, tick_number)
        for bomb in parser.my_bombs:
            weight = 1. if bomb.is_armed else 0.5
            screen[bomb.pos.x, bomb.pos.y, my_bombs_layer] = weight
        for bomb in parser.enemy_bombs:
            weight = 1. if bomb.is_armed else 0.5
            screen[bomb.pos.x, bomb.pos.y, enemy_bombs_layer] = weight
        for entity in parser.entities:
            if "expires" in entity:
                expires = entity["expires"]
                ticks_left = expires - tick_number
                weight = explosion_base + explosion_with_ticks_max * ticks_left / explosion_ticks
            else:
                weight = 1  # endgame fire does not expire
            if entity["type"] == "x":
                screen[entity["x"], entity["y"], explosions_layer] = weight
        for x, y in np.ndindex(parser.all_bomb_explosion_map.shape):
            map_entry = parser.all_bomb_explosion_map[x, y]
            weight = 0.
            if map_entry:
                weight = bomb_future_explosion_base + \
                         (bomb_future_explosion_max_ticks - map_entry.cluster.ticks_till_explode) * \
                         (1. - bomb_future_explosion_base) / bomb_future_explosion_max_ticks
            if weight and map_entry.cluster.is_my:
                screen[x, y, my_bomb_future_explosions_layer] = weight
            if weight and map_entry.cluster.is_enemy:
                screen[x, y, enemy_bomb_future_explosions_layer] = weight
        fire_danger_steps = endgame_fire_simulator.endgame_fire_spiral - (parser.endgame_fires // 2)
        fire_danger_steps.clip(0, out=fire_danger_steps)  # replace negatives with zero
        fire_danger_steps[fire_danger_steps == 0] = 0.5
        screen[:, :, endgame_fire] = 0.5 / np.sqrt(fire_danger_steps)
        screen[:, :, steps_to_center] = self.steps_layer

        screen_max = np.max(screen)
        screen_min = np.min(screen)
        screen[:, :, tick_layer] = tick_number / max_tick
        if screen_max > 1. + 1e-6:
            assert False
        if screen_min < -1e-6:
            assert False
        return screen

    def screen_to_rgb(self, screen, unit_actions, bomb_actions):
        rgb = np.ones((w, h, 3))
        # draw_layer(rgb, screen, endgame_fire, 0, 0, 1)
        draw_layer(rgb, screen, walls_layer, 0, 0.2, 0.2)
        # draw_layer(rgb, screen, steps_to_center, 1, 0, 1)
        # draw_layer(rgb, screen, explosions_layer, 1, 0.55, 0)
        draw_layer(rgb, screen, my_units_layer, 0.5, 0.5, 0.5)
        draw_layer(rgb, screen, enemy_units_layer, 0.7, 0, 0)
        # draw_layer(rgb, screen, my_invincibility, 0, 1, 0, alpha=0.5)
        # draw_layer(rgb, screen, enemy_invincibility, 1, 0, 0, alpha=0.5)
        # draw_layer(rgb, screen, my_explosion_radius, 0.2, 0.4, 0.2, alpha=0.2)
        # draw_layer(rgb, screen, enemy_explosion_radius, 0.4, 0.2, 0.2, alpha=0.2)
        # draw_layer(rgb, screen, my_bomb_future_explosions_layer, 0.2, 0.5, 0, alpha=0.4)
        # draw_layer(rgb, screen, enemy_bomb_future_explosions_layer, 0.5, 0.2, 0, alpha=0.4)
        draw_layer(rgb, screen, my_bombs_layer, 0, 0.3, 0.3, alpha=0.7)
        draw_layer(rgb, screen, enemy_bombs_layer, 0.3, 0, 0.3, alpha=0.7)

        draw_layer(rgb, unit_actions, action_move_up, 0, 0, 1, alpha=0.5)
        draw_layer(rgb, unit_actions, action_move_down, 1, 0, 0, alpha=0.5)
        draw_layer(rgb, unit_actions, action_move_left, 1, 0, 1, alpha=0.5)
        draw_layer(rgb, unit_actions, action_move_right, 1, 1, 0, alpha=0.5)
        draw_layer(rgb, unit_actions, action_noop, 0, 0, 0, alpha=0.5)
        draw_layer(rgb, unit_actions, action_place_bomb, 0, 1, 1, alpha=0.5)

        draw_layer(rgb, bomb_actions, bomb_action_detonate, 1, 0, 0, alpha=0.5)
        draw_layer(rgb, bomb_actions, bomb_action_noop, 0.5, 0.5, 0.5, alpha=0.5)

        rgb *= 255

        return rgb.astype(int)

    def get_replay_history(self, replay_path):
        np.set_printoptions(precision=3, linewidth=200)

        game_state = GameState("")

        with open(replay_path, 'r') as json_file:
            replay = json.load(json_file)

        replay_payload = replay["payload"]
        winner = replay_payload["winning_agent_id"]
        history = replay_payload["history"]

        initial_state = replay_payload.get("initial_state")
        connection = Connection(game_state)

        game_state.on_game_state(initial_state)
        game_state.connection = connection

        loop = asyncio.get_event_loop()

        history_len = history[-1]["tick"]
        converted_history = np.ndarray((history_len, *screen_shape), dtype=float)
        unit_actions = np.zeros((history_len, w, h, unit_actions_size))
        bomb_actions = np.zeros((history_len, w, h, bomb_actions_size))
        unit_mask = np.zeros((history_len, w, h))
        bomb_mask = np.zeros((history_len, w, h))
        unit_action_freq = np.zeros((unit_actions_size,))
        bomb_action_freq = np.zeros((bomb_actions_size,))

        init_parser = Parser(0, game_state.state, calculate_wall_map=True, pov_agent_id=winner)
        self.parser = init_parser
        self.steps_layer = calc_steps_to_center_layer(init_parser)
        my_unit_ids = set()
        for my_unit in init_parser.my_units:
            my_unit_ids.add(my_unit.id)

        prev_tick = -1
        for tick in history:
            tick_number = tick.get("tick")
            for skipped in range(prev_tick + 1, tick_number):
                converted_history[skipped - 1, :, :, :] =\
                    self.convert(game_state.state, skipped, winner)
                populate_actions(None, game_state.state, unit_actions, unit_mask, unit_action_freq,
                                 bomb_actions, bomb_mask, bomb_action_freq, skipped, self.parser, my_unit_ids)
            prev_screen = self.convert(game_state.state, tick_number, winner)
            converted_history[tick_number - 1, :, :, :] = prev_screen
            prev_tick = tick_number
            populate_actions(tick, game_state.state, unit_actions, unit_mask, unit_action_freq,
                             bomb_actions, bomb_mask, bomb_action_freq, tick_number, self.parser, my_unit_ids)
            task = loop.create_task(game_state.on_game_tick(tick))
            loop.run_until_complete(asyncio.gather(task))

        history = np.moveaxis(converted_history, -1, 1)
        unit_actions = np.moveaxis(unit_actions, -1, 1)
        bomb_actions = np.moveaxis(bomb_actions, -1, 1)
        return history, unit_actions, unit_mask, unit_action_freq, bomb_actions, bomb_mask, bomb_action_freq


class Connection:
    def __init__(self, game_state):
        self.game_state = game_state

    async def send(self, *args):
        self.game_state.on_unit_action(json.loads(args[0]))
        print("Sent to connection:", *args)

