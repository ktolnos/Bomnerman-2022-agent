from utils import *

walkable_entities = {"a", "bp"}
power_ups = walkable_entities
owner_init_id = "unit_id"

endgame_fire_danger = 0.5
my_bomb_starting_danger = 0.1
enemy_bomb_starting_danger = 1.
bomb_end_danger_ticks = 5
bomb_end_danger_max = 1.

bomb_arming_ticks = 5


class Parser:

    def __init__(self, tick_number, game_state):
        w = game_state.get("world").get("width")
        h = game_state.get("world").get("height")

        self.walkable_map = np.zeros((w, h))
        self.my_bomb_explosion_map = np.zeros((w, h))
        self.my_bomb_explosion_map_objects = [[None for i in range(h)] for j in range(w)]
        self.entities_map = [[None for i in range(h)] for j in range(w)]
        self.all_bomb_explosion_map = np.zeros((w, h))
        self.danger_map = np.zeros((w, h))
        self.power_ups = []
        self.bombs = []
        self.my_bombs = []
        self.my_armed_bombs = []
        self.enemy_bombs = []

        units = game_state.get("unit_state")
        self.units = units

        my_agent_id = game_state.get("connection").get("agent_id")
        my_units = game_state.get("agents").get(my_agent_id).get("unit_ids")
        self.my_units = []
        self.enemy_units = []
        for unit_id in my_units:
            unit = units.get(unit_id)
            if unit.get("hp") <= 0:
                continue
            self.my_units.append(units.get(unit_id))
        for agent_id in game_state.get("agents"):
            if agent_id == my_agent_id:
                continue
            enemy_units = game_state.get("agents").get(agent_id).get("unit_ids")
            for unit_id in enemy_units:
                unit = units.get(unit_id)
                if unit.get("hp") <= 0:
                    continue
                self.enemy_units.append(units.get(unit_id))

        for unit_name in units:
            unit = units.get(unit_name)
            coordinates = unit.get("coordinates")
            self.walkable_map[coordinates[0], coordinates[1]] = 1

        entities = game_state.get("entities")
        self.entities = entities

        # a: ammunition
        # b: Bomb
        # x: Blast
        # bp: Blast Powerup
        # m: Metal Block
        # o: Ore Block
        # w: Wooden Block
        for entity in entities:
            e_type = entity.get("type")
            if e_type in walkable_entities:
                self.power_ups.append(entity)
                continue
            coordinates = entity.get("x"), entity.get("y")
            self.walkable_map[coordinates[0], coordinates[1]] = 1
            self.entities_map[coordinates[0]][coordinates[1]] = entity
            if e_type == "b":
                self.bombs.append(entity)
                draw_bomb_explosion(self.all_bomb_explosion_map, entity)

                is_my_bomb = entity.get(owner_init_id) in my_units
                base_danger = my_bomb_starting_danger if is_my_bomb else enemy_bomb_starting_danger
                bomb_placed_tick = entity.get("created")
                bomb_will_explode_tick = entity.get("expires")
                end_danger = 0
                if tick_number >= bomb_will_explode_tick + bomb_end_danger_ticks:
                    end_danger = bomb_end_danger_max / (bomb_will_explode_tick - tick_number)
                bomb_danger = base_danger + end_danger
                draw_bomb_explosion(self.danger_map, entity, value=bomb_danger)

                if is_my_bomb:
                    self.my_bombs.append(entity)
                    if tick_number - bomb_placed_tick > bomb_arming_ticks:
                        draw_bomb_explosion_with_obj(self.my_bomb_explosion_map,
                                                     self.my_bomb_explosion_map_objects,
                                                     entity)
                        self.my_armed_bombs.append(entity)
                else:
                    self.enemy_bombs.append(entity)
            if e_type == "x":
                draw_bomb_explosion(self.danger_map, entity, rad=2, value=endgame_fire_danger)

        print(self.danger_map)


def draw_bomb_explosion_with_obj(arr, obj_arr, bomb, value=1.):
    x, y = bomb.get("x"), bomb.get("y")
    arr[x, y] = 1
    obj_arr[x][y] = bomb
    for i in range(blast_r(bomb.get("blast_diameter"))):
        if x + i < arr.shape[0]:
            arr[x + i, y] = value
            obj_arr[x + i][y] = bomb
        if x - i >= 0:
            arr[x - i, y] = value
            obj_arr[x - i][y] = bomb
        if y + i < arr.shape[1]:
            arr[x, y + i] = value
            obj_arr[x][y + i] = bomb
        if y - i >= 0:
            arr[x, y - i] = value
            obj_arr[x][y - i] = bomb


def draw_bomb_explosion(arr, bomb, rad=None, value=1.):
    x, y = bomb.get("x"), bomb.get("y")
    if rad is None:
        rad = blast_r(bomb.get("blast_diameter"))
    arr[x, y] = value
    for i in range(rad):
        if x + i < arr.shape[0]:
            arr[x + i, y] = value
        if x - i >= 0:
            arr[x - i, y] = value
        if y + i < arr.shape[1]:
            arr[x, y + i] = value
        if y - i >= 0:
            arr[x, y - i] = value
