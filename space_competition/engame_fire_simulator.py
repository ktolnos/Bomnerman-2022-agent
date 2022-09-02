import numpy as np

from parser import *


class EndgameFireSimulator:

    def __init__(self, w: int, h: int,
                 start_danger=endgame_fire_start_danger,
                 end_danger=endgame_fire_end_danger):
        self.endgame_fire_spiral = np.zeros((w, h))
        total_steps = w * h // 2
        danger_step = (start_danger - end_danger) / total_steps

        NORTH, S, W, E = (0, -1), (0, 1), (-1, 0), (1, 0)  # directions
        turn_left = {NORTH: W, E: NORTH, S: E, W: S}  # old -> new direction

        x, y = w // 2, h // 2  # start near the center
        dx, dy = E  # initial direction
        danger = end_danger
        while True:
            danger += danger_step
            self.endgame_fire_spiral[y, x] = danger  # visit
            self.endgame_fire_spiral[h - y - 1, w - x - 1] = danger  # visit
            # try to turn left
            new_dx, new_dy = turn_left[dx, dy]
            new_x, new_y = x + new_dx, y + new_dy
            if (0 <= new_x < w and 0 <= new_y < h and
                    self.endgame_fire_spiral[new_y, new_x] == 0.):  # can turn right
                x, y = new_x, new_y
                dx, dy = new_dx, new_dy
            else:  # try to move straight
                x, y = x + dx, y + dy
                if not (0 <= x < w and 0 <= y < h):
                    break

    def get_endgame_fire_danger(self, n_fires):
        multiplier = endgame_fire_base_multiplier + n_fires * endgame_fire_endgame_multiplier_per_fire
        return self.endgame_fire_spiral * multiplier
