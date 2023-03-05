from copy import deepcopy

from parsing.bombs import Bomb, BombCluster, BombExplosionMapEntry
from parsing.settings import *
from utils.grid import draw_cross, check_free
from utils.game_utils import *
from parsing.gamestate import ParsedGameState, owner_unit_id


class Parser:

    def __init__(self, tick_number, game_state, pov_agent_id=None):
        self.gs = ParsedGameState(game_state)
        self.gs.tick = tick_number
        w = self.gs.w
        h = self.gs.h
        self.w = w
        self.h = h
        self.center = Point(w // 2, h // 2)
        self.walkable_map = np.zeros((w, h))
        self.cell_occupation_danger_map = np.zeros((w, h))
        self.all_bomb_explosion_map_my = np.zeros((w, h), dtype=object)
        self.all_bomb_explosion_map_enemy = np.zeros((w, h), dtype=object)
        self.has_bomb_map = np.zeros((w, h))
        self.danger_map = np.zeros((w, h))
        self.power_ups = []
        self.bombs = []
        self.my_bombs = []
        self.my_armed_bombs = []
        self.enemy_bombs = []
        self.endgame_fires = 0
        self.endgame_fires_map = np.zeros((w, h))
        self.my_units = []
        self.my_unit_ids = []
        self.enemy_units = []
        self.enemy_unit_ids = []
        self.units_map = np.zeros((w, h), dtype=object)
        self.dead_units_map = np.zeros((w, h), dtype=object)
        self.unit_id_to_unit = dict()
        self.cluster_to_bombs_my = dict()
        self.cluster_to_bombs_enemy = dict()
        self.wall_map = np.zeros_like(self.walkable_map)
        self.free_from_endgame_fire = 0

        # ====== process units =====

        units = game_state.get("unit_state")
        self.units = units

        if pov_agent_id is None:
            my_agent_id = game_state.get("connection").get("agent_id")
        else:
            my_agent_id = pov_agent_id
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
            self.units_map[unit.pos] = unit
        for unit in self.my_units:
            self.units_map[unit.pos] = unit
        self.my_units.sort(key=lambda u: u.hp, reverse=True)
        # ====== process entities =====

        entities = game_state.get("entities")
        self.entities = entities

        self.cell_occupation_danger_map[:, 0] = close_cell_danger
        self.cell_occupation_danger_map[0, :] = close_cell_danger
        self.cell_occupation_danger_map[:, h - 1] = close_cell_danger
        self.cell_occupation_danger_map[w - 1, :] = close_cell_danger

        # a: ammunition
        # b: Bomb
        # x: Blast
        # bp: Blast Powerup
        # fp: Freeze Powerup
        # m: Metal Block
        # o: Ore Block
        # w: Wooden Block
        for entity in entities:
            e_type = entity.get("type")
            if e_type == "fp" or e_type == "bp":
                self.power_ups.append(entity)
                continue
            coordinates = entity.get("x"), entity.get("y")
            if e_type != "x":
                self.walkable_map[coordinates] = math.inf
            draw_cross(self.cell_occupation_danger_map, coordinates[0], coordinates[1], rad=2,
                       value=close_cell_danger)
            if e_type == "b":
                self.parse_bomb(entity, coordinates)
            if e_type == "x":
                if "expires" not in entity:
                    self.endgame_fires += 1
                    self.endgame_fires_map[coordinates] = 1
                self.danger_map[coordinates] = explosion_danger
            if e_type == "m":
                self.wall_map[coordinates] = math.inf
            if e_type == "w" or e_type == "o":
                self.wall_map[coordinates] = entity.get("hp")

        self.free_from_endgame_fire = self.w * self.h - self.endgame_fires

        self.add_enemy_suicide_bomb_danger()
        self.add_enclosed_bomb_danger()
        self.process_bombs()
        self.add_enemy_bombs_danger()

    def parse_bomb(self, entity, coordinates):
        bomb_placed_tick = entity.get("created")
        bomb_will_explode_tick = entity.get("expires")
        owner_id = entity.get(owner_unit_id)
        owner = self.unit_id_to_unit.get(owner_id, None)
        is_owner_stunned = owner and owner.stunned_last_tick and owner.stunned_last_tick >= self.gs.tick
        is_armed = self.gs.tick - bomb_placed_tick > bomb_arming_ticks and owner and not is_owner_stunned

        bomb = Bomb(
            Point(*coordinates),
            entity.get("blast_diameter"),
            owner_id,
            is_armed
        )
        self.bombs.append(bomb)

        is_my_bomb = bomb.owner_unit_id in self.my_unit_ids

        base_danger = my_bomb_starting_danger if is_my_bomb else enemy_bomb_starting_danger

        if not is_armed:
            owner_will_be_stunned_next_tick = owner and owner.stunned_last_tick and\
                                              owner.stunned_last_tick >= self.gs.tick + 1
            will_be_armed_next_tick = self.gs.tick + 1 - bomb_placed_tick > bomb_arming_ticks and not\
                owner_will_be_stunned_next_tick
            if not will_be_armed_next_tick:
                base_danger *= unarmed_bomb_danger_modifier_my if is_my_bomb else unarmed_bomb_danger_modifier_enemy

        end_danger = 0
        if self.gs.tick >= bomb_will_explode_tick - bomb_end_danger_ticks:
            end_danger = bomb_end_danger_max * (1 - (bomb_will_explode_tick - self.gs.tick - 1) /
                                                bomb_end_danger_ticks)
        bomb_danger = base_danger + end_danger

        cluster = BombCluster(
            bomb.pos,
            bomb_danger,
            is_armed,
            is_my=is_my_bomb,
            is_enemy=not is_my_bomb,
            ticks_till_explode=bomb_will_explode_tick - self.gs.tick,
            my_bomb_that_can_trigger=bomb if is_my_bomb and is_armed else None
        )
        map_entry = BombExplosionMapEntry(bomb, cluster)
        enemy_entry = deepcopy(map_entry)
        self.all_bomb_explosion_map_my[bomb.pos] = [map_entry]
        self.all_bomb_explosion_map_enemy[bomb.pos] = [enemy_entry]
        self.has_bomb_map[bomb.pos] = 1
        self.cluster_to_bombs_my[cluster] = [map_entry]
        self.cluster_to_bombs_enemy[cluster] = [enemy_entry]

        if is_my_bomb:
            self.my_bombs.append(bomb)
            if is_armed:
                self.my_armed_bombs.append(bomb)
        else:
            self.enemy_bombs.append(bomb)

    def add_enclosed_bomb_danger(self):
        for bomb in self.bombs:
            for neighbour in get_neighbours(self.danger_map, bomb.pos):
                if self.cell_occupation_danger_map[neighbour] >= 4 * close_cell_danger:
                    self.danger_map[neighbour] += enclosed_bomb_danger
                    continue
                if self.cell_occupation_danger_map[neighbour] >= 3 * close_cell_danger - 0.001:
                    for neigbours_neighbour in get_neighbours(self.danger_map, neighbour):
                        if not self.walkable_map[neigbours_neighbour]:
                            for n_n_neigbour in get_neighbours(self.danger_map, neigbours_neighbour):
                                if self.units_map[n_n_neigbour] and \
                                        self.units_map[n_n_neigbour].id in self.enemy_unit_ids:
                                    self.danger_map[neighbour] += possibly_enclosed_bomb_danger
                                    break

    def add_enemy_suicide_bomb_danger(self):
        for enemy in self.enemy_units:
            if self.danger_map[enemy.pos] >= explosion_danger:  # enemies can spawn bombs
                self.raise_danger_for_potential_explosion(self.danger_map, enemy.pos, enemy_potential_bomb_danger,
                                                          blast_r(enemy.blast_diameter))
                for neigbour in get_neighbours(self.danger_map, enemy.pos):
                    if not self.walkable_map[neigbour] and self.danger_map[neigbour] >= explosion_danger:
                        self.raise_danger_for_potential_explosion(self.danger_map, enemy.pos,
                                                                  enemy_potential_bomb_danger,
                                                                  blast_r(enemy.blast_diameter))

    def add_enemy_bombs_danger(self):
        for x, y in np.ndindex(self.all_bomb_explosion_map_enemy.shape):
            enemy_entries = self.all_bomb_explosion_map_enemy[x, y]
            my_entries = self.all_bomb_explosion_map_my[x, y]
            max_danger = 0
            if enemy_entries:
                for map_entry in enemy_entries:
                    max_danger = max(max_danger, map_entry.cluster.danger)
            if my_entries:
                for map_entry in my_entries:
                    max_danger = max(max_danger, map_entry.cluster.danger)
            if max_danger != 0:
                draw_cross(self.cell_occupation_danger_map, x, y, rad=2, value=close_cell_danger)
            self.danger_map[x, y] += max_danger

    def process_bombs(self):
        self.process_bombs_helper(self.all_bomb_explosion_map_my, self.my_bombs, self.cluster_to_bombs_my)
        self.process_bombs_helper(self.all_bomb_explosion_map_enemy, self.enemy_bombs, self.cluster_to_bombs_enemy)

    def process_bombs_helper(self, all_bomb_explosion_map, bombs, cluster_to_bombs):
        arr = all_bomb_explosion_map
        for bomb in bombs:
            x, y = bomb.pos
            rad = blast_r(bomb.blast_diameter)
            entry = all_bomb_explosion_map[bomb.pos][0]
            # now intersection entries are not max of both
            for i in range(1, rad):
                if x + i >= arr.shape[0]:
                    break
                if self.process_bomb(x + i, y, entry, arr, cluster_to_bombs):
                    break
            for i in range(1, rad):
                if x - i < 0:
                    break
                if self.process_bomb(x - i, y, entry, arr, cluster_to_bombs):
                    break
            for i in range(1, rad):
                if y + i >= arr.shape[1]:
                    break
                if self.process_bomb(x, y + i, entry, arr, cluster_to_bombs):
                    break
            for i in range(1, rad):
                if y - i < 0:
                    break
                if self.process_bomb(x, y - i, entry, arr, cluster_to_bombs):
                    break

    def process_bomb(self, x, y, entry, all_bomb_explosion_map, cluster_to_bombs) -> bool:
        """returns true if stampled across other bomb or wall and cycle should end"""
        other = all_bomb_explosion_map[x, y]

        if other and self.has_bomb_map[x, y]:
            entry.merge_with(other[0], cluster_to_bombs)
            return False  # it seems in latest versions bombs go through  other bombs
        if self.wall_map[x, y] != 0 and not self.dead_units_map[x, y]:  # explosions pass through dead units
            return True
        if not all_bomb_explosion_map[x, y]:
            all_bomb_explosion_map[x, y] = []
        all_bomb_explosion_map[x, y].append(entry)
        return False

    def parse_unit(self, unit_id, target_list, target_ids_list):
        unit = self.units.get(unit_id)
        pos = point(unit)
        if unit.get("hp") <= 0:
            self.wall_map[pos] = math.inf
            self.walkable_map[pos] = math.inf
            self.dead_units_map[pos] = unit
            draw_cross(self.cell_occupation_danger_map, pos.x, pos.y, rad=2,
                       value=close_cell_danger)
        else:
            target_ids_list.append(unit_id)
            res = Unit(
                unit_id,
                pos,
                unit.get("inventory").get("bombs"),
                unit.get("hp"),
                unit.get("blast_diameter"),
                unit.get("invulnerable"),
                unit.get("stunned")
            )
            target_list.append(res)
            self.unit_id_to_unit[unit_id] = res

    def raise_danger_for_potential_explosion(self, arr, pos, danger, rad):
        def raise_danger(x, y):
            if x < 0 or x >= self.w or y < 0 or y >= self.h:
                return True
            if self.wall_map[x, y] != 0:
                return True
            arr[x, y] = max(arr[x, y], danger)
            return False

        raise_danger(*pos)
        x, y = pos
        for i in range(1, rad):
            if raise_danger(x + i, y):
                break
        for i in range(1, rad):
            if raise_danger(x - i, y):
                break
        for i in range(1, rad):
            if raise_danger(x, y - i):
                break
        for i in range(1, rad):
            if raise_danger(x, y + i):
                break

    def calculate_not_free_map(self, unit):
        blast_rad = blast_r(unit.blast_diameter)
        rad = blast_rad + 1

        def free_checker(x, y):
            if self.walkable_map[x, y] or self.danger_map[x, y]:
                return False
            other = self.units_map[x, y]
            if other and other.id != unit.id and other.id in self.my_unit_ids:
                return False
            return check_free(self.w, self.h, self.walkable_map, self.danger_map, self.units_map, self.enemy_units,
                              self.cell_occupation_danger_map, Point(x, y), rad, blast_rad, unit.id)

        check_map = np.zeros_like(self.walkable_map)
        for x, y in np.ndindex(self.all_bomb_explosion_map.shape):
            check_map[x, y] = not free_checker(x, y)
        return check_map


