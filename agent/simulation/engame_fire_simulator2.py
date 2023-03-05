from parsing.parser import *

fires_per_step = 2


class EndgameFireSimulator2:

    def __init__(self, w: int, h: int):
        self.endgame_fire_spiral = np.zeros((w, h))
        total_steps = w * h // 2

        NORTH, S, W, E = (0, -1), (0, 1), (-1, 0), (1, 0)  # directions
        turn_left = {NORTH: W, E: NORTH, S: E, W: S}  # old -> new direction

        x, y = w // 2, h // 2  # start near the center
        dx, dy = E  # initial direction
        steps = total_steps
        while True:
            self.endgame_fire_spiral[y, x] = steps  # visit
            self.endgame_fire_spiral[h - y - 1, w - x - 1] = steps  # visit
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
            steps -= 1

    def get_endgame_fire_danger(self, n_fires):
        fire_danger_steps = self.endgame_fire_spiral - (n_fires // 2)
        multiplier = endgame_fire_base_multiplier if n_fires == 0 else endgame_fire_else
        fire_danger_steps.clip(0, out=fire_danger_steps)  # replace negatives with zero
        fire_danger_steps[fire_danger_steps == 0] = 0.35
        fire_danger_steps[fire_danger_steps == 1] = 0.45  # Counter({'b': 74, 'a': 45, '': 1})
        fire_danger_steps[fire_danger_steps == 2] = 0.55
        fire_danger = 1. / fire_danger_steps
        np.square(fire_danger, out=fire_danger)
        return fire_danger * multiplier
