import numpy as np

from parsing.settings import enemy_in_danger_discount, enemy_in_danger_one_cell_discount
from utils.game_utils import get_neighbours


def compute_state_map(state):
    state.state_map = np.ones_like(state.parser.danger_map) * 4

    state.state_map += state.parser.walkable_map
    state.state_map += state.parser.danger_map
    state.state_map += state.endgame_fire_simulator.get_endgame_fire_danger(state.parser.endgame_fires)

    neighbours_count = 0
    last_neighbour = None
    for enemy in state.parser.enemy_units:
        if state.parser.danger_map[enemy.pos]:
            for neigbour in get_neighbours(state.parser.danger_map, enemy.pos):
                if not state.parser.danger_map[neigbour] and not state.parser.walkable_map[neigbour]:
                    state.state_map[neigbour] += enemy_in_danger_discount
                    neighbours_count += 1
                    last_neighbour = neigbour
    if neighbours_count == 1:
        state.state_map[last_neighbour] += enemy_in_danger_one_cell_discount
        