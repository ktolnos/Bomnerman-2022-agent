import unittest
from unittest import IsolatedAsyncioTestCase

import numpy as np

from engame_fire_simulator import EndgameFireSimulator
from engame_fire_simulator2 import EndgameFireSimulator2


class TestEndgameFireSimulator(IsolatedAsyncioTestCase):
    def test_generation(self):
        np.set_printoptions(precision=1)
        print(EndgameFireSimulator(15, 15).endgame_fire_spiral)

    def test_generation2(self):
        np.set_printoptions(precision=1, linewidth=200)
        print(EndgameFireSimulator2(15, 15).endgame_fire_spiral)

    def test_get_danger2(self):
        np.set_printoptions(precision=2, linewidth=250, suppress=True)
        print(EndgameFireSimulator2(15, 15).get_endgame_fire_danger(200))


if __name__ == '__main__':
    unittest.main()
