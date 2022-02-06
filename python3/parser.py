from utils import *

owner_unit_id = "unit_id"

endgame_fire_start_danger = 3.0
endgame_fire_end_danger = 0.0  # danger of the endgame fire in the center
endgame_fire_base_multiplier = 0.1
endgame_fire_else = 40
endgame_fire_endgame_multiplier_per_fire = 0.02
endgame_fire_center_discount_mass = -0.2
endgame_fire_center_discount = -0.2  # gets multiplied by HP.

my_bomb_starting_danger = 5
enemy_bomb_starting_danger = 140
bomb_end_danger_ticks = 5
unarmed_bomb_danger_modifier = 0.9
bomb_end_danger_max = 150

close_cell_danger = 0.1

bomb_arming_ticks = 5
power_up_discount = -0.5
close_enemy_discount = -0.2
close_to_center_enemy_discount = -3
center_occupied_ammo_discount = -3
explosion_danger = 100000
stand_on_bomb_danger = 999

search_budget_big = 50
search_budget_small = 25
search_horizon = 30


class Parser:

    def __init__(self, tick_number, game_state, calculate_wall_map=False):
        w = game_state.get("world").get("width")
        h = game_state.get("world").get("height")
        self.w = w
        self.h = h
        self.center = Point(w // 2, h // 2)
        self.walkable_map = np.zeros((w, h))
        self.cell_occupation_danger_map = np.zeros((w, h))
        self.my_bomb_explosion_map_objects = [[None for i in range(h)] for j in range(w)]
        self.all_bomb_explosion_map = np.zeros((w, h), dtype=object)
        self.danger_map = np.zeros((w, h))
        self.power_ups = []
        self.bombs = []
        self.my_bombs = []
        self.my_armed_bombs = []
        self.enemy_bombs = []
        self.endgame_fires = 0
        self.my_units = []
        self.my_unit_ids = []
        self.enemy_units = []
        self.enemy_unit_ids = []
        self.unit_id_to_unit = dict()
        self.cluster_to_bombs = dict()

        if calculate_wall_map:
            self.wall_map = np.zeros_like(self.walkable_map)

        # ====== process units =====

        units = game_state.get("unit_state")
        self.units = units

        my_agent_id = game_state.get("connection").get("agent_id")
        my_units = game_state.get("agents").get(my_agent_id).get("unit_ids")
        for unit_id in my_units:
            self.parse_unit(unit_id, self.my_units, self.my_unit_ids)
        for agent_id in game_state.get("agents"):
            if agent_id == my_agent_id:
                continue
            enemy_units = game_state.get("agents").get(agent_id).get("unit_ids")
            for unit_id in enemy_units:
                self.parse_unit(unit_id, self.enemy_units, self.enemy_unit_ids)
        for unit in self.enemy_units:
            self.walkable_map[unit.pos] = math.inf
        self.my_units.sort(key=lambda u: u.hp, reverse=True)
        # ====== process entities =====

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
            if e_type == "a" or e_type == "bp":
                self.power_ups.append(entity)
                continue
            coordinates = entity.get("x"), entity.get("y")
            if e_type != "x":
                self.walkable_map[coordinates] = math.inf
            draw_cross(self.cell_occupation_danger_map, coordinates[0], coordinates[1], rad=2,
                       value=close_cell_danger)
            if e_type == "b":
                bomb_placed_tick = entity.get("created")
                bomb_will_explode_tick = entity.get("expires")
                is_armed = tick_number - bomb_placed_tick > bomb_arming_ticks

                bomb = Bomb(
                    Point(*coordinates),
                    entity.get("blast_diameter"),
                    entity.get(owner_unit_id),
                    is_armed
                )
                self.bombs.append(bomb)

                is_my_bomb = bomb.owner_unit_id in my_units

                base_danger = my_bomb_starting_danger if is_my_bomb else enemy_bomb_starting_danger

                if not is_armed:
                    base_danger *= unarmed_bomb_danger_modifier

                end_danger = 0
                if tick_number >= bomb_will_explode_tick - bomb_end_danger_ticks:
                    end_danger = bomb_end_danger_max * (1 - (bomb_will_explode_tick - tick_number - 1) /
                                                        bomb_end_danger_ticks)
                bomb_danger = base_danger + end_danger

                cluster = BombCluster(
                    bomb.pos,
                    bomb_danger,
                    is_armed,
                    can_be_triggered_by_me=is_my_bomb and is_armed,
                    can_be_triggered_by_enemy=not is_my_bomb,
                    my_bomb_that_can_trigger=bomb if is_my_bomb and is_armed else None
                )
                map_entry = BombExplosionMapEntry(bomb, cluster)
                self.all_bomb_explosion_map[bomb.pos] = map_entry
                self.cluster_to_bombs[cluster] = [map_entry]

                if is_my_bomb:
                    self.my_bombs.append(bomb)
                    if is_armed:
                        self.my_armed_bombs.append(bomb)
                else:
                    self.enemy_bombs.append(bomb)
            if e_type == "x":
                self.endgame_fires += 1
                self.danger_map[coordinates] = explosion_danger
            if calculate_wall_map:
                if e_type == "m":
                    self.wall_map[coordinates] = math.inf
                if e_type == "w" or e_type == "o":
                    self.wall_map[coordinates] = entity.get("hp")
        self.process_bombs()
        for x in range(self.all_bomb_explosion_map.shape[0]):
            for y in range(self.all_bomb_explosion_map.shape[1]):
                map_entry = self.all_bomb_explosion_map[x, y]
                if map_entry:
                    self.danger_map[x, y] += map_entry.cluster.danger

    def process_bombs(self):
        arr = self.all_bomb_explosion_map
        for bomb in self.bombs:
            x, y = bomb.pos
            rad = blast_r(bomb.blast_diameter)
            entry = self.all_bomb_explosion_map[bomb.pos]
            for i in range(1, rad):
                if x + i < arr.shape[0]:
                    other = arr[x + i, y]
                    if other:
                        self.merge(entry, other)
                        break
                    arr[x + i, y] = entry
            for i in range(1, rad):
                if x - i >= 0:
                    other = arr[x - i, y]
                    if other:
                        self.merge(entry, other)
                        break
                    arr[x - i, y] = entry
            for i in range(1, rad):
                if y + i < arr.shape[1]:
                    other = arr[x, y + i]
                    if other:
                        self.merge(entry, other)
                        break
                    arr[x, y + i] = entry
            for i in range(1, rad):
                if y - i >= 0:
                    other = arr[x, y - i]
                    if other:
                        self.merge(entry, other)
                        break
                    arr[x, y - i] = entry

    def merge(self, bomb_map_entry: BombExplosionMapEntry, other: BombExplosionMapEntry):
        other_cluster = other.cluster
        my_cluster = bomb_map_entry.cluster
        new_cluster = bomb_map_entry.cluster.merge_with(other.cluster)
        new_cluster_entries = []
        for other_cluster_entry in self.cluster_to_bombs[other_cluster]:
            other_cluster_entry.cluster = new_cluster
            new_cluster_entries.append(other_cluster_entry)
        for cluster_entry in self.cluster_to_bombs[my_cluster]:
            cluster_entry.cluster = new_cluster
            new_cluster_entries.append(cluster_entry)
        self.cluster_to_bombs[other_cluster].clear()
        self.cluster_to_bombs[my_cluster].clear()
        self.cluster_to_bombs[new_cluster] = new_cluster_entries

    def parse_unit(self, unit_id, target_list, target_ids_list):
        unit = self.units.get(unit_id)
        pos = point(unit)
        if unit.get("hp") <= 0:
            self.walkable_map[pos.x, pos.y] = math.inf
            draw_cross(self.cell_occupation_danger_map, pos.x, pos.y, rad=2, value=close_cell_danger)
        else:
            target_ids_list.append(unit_id)
            res = Unit(
                unit_id,
                pos,
                unit.get("inventory").get("bombs"),
                unit.get("hp"),
                unit.get("blast_diameter"),
            )
            target_list.append(res)
            self.unit_id_to_unit[unit_id] = res

    def check_free(self, p, rad) -> bool:
        """
        :return: True if cross has at least one direction free
        """
        x, y = p
        arr = self.cell_occupation_danger_map
        free = True
        for i in range(rad):
            if x + i < arr.shape[0] and arr[x + i, y] >= close_cell_danger * 3:
                free = False
                break
        if free:
            return True
        free = True
        for i in range(rad):
            if x - i >= 0 and arr[x - i, y] >= close_cell_danger * 3:
                free = False
                break
        if free:
            return True
        free = True
        for i in range(rad):
            if y + i < arr.shape[1] and arr[x, y + i] >= close_cell_danger * 3:
                free = False
                break
        if free:
            return True
        for i in range(rad):
            if y - i >= 0 and arr[x, y - i] >= close_cell_danger * 3:
                return False


def draw_bomb_explosion_with_obj(arr, obj_arr, bomb, value=1.):
    x, y = bomb.pos
    arr[x, y] = 1
    obj_arr[x][y] = bomb
    for i in range(blast_r(bomb.blast_diameter)):
        if x + i < arr.shape[0]:
            arr[x + i, y] += value
            obj_arr[x + i][y] = bomb
        if x - i >= 0:
            arr[x - i, y] += value
            obj_arr[x - i][y] = bomb
        if y + i < arr.shape[1]:
            arr[x, y + i] += value
            obj_arr[x][y + i] = bomb
        if y - i >= 0:
            arr[x, y - i] += value
            obj_arr[x][y - i] = bomb


def draw_bomb_explosion(arr, bomb, rad=None, value=1.):
    x, y = bomb.get("x"), bomb.get("y")
    if rad is None:
        rad = blast_r(bomb.get("blast_diameter"))
    draw_cross(arr, x, y, rad, value)


def draw_cross(arr, x, y, rad, value):
    for i in range(rad):
        if x + i < arr.shape[0]:
            arr[x + i, y] += value
        if x - i >= 0:
            arr[x - i, y] += value
        if y + i < arr.shape[1]:
            arr[x, y + i] += value
        if y - i >= 0:
            arr[x, y - i] += value
