import math
import unittest
from unittest import IsolatedAsyncioTestCase

import numpy as np

from engame_fire_simulator import EndgameFireSimulator
from least_cost_search import LeastCostSearch
from utils import Point


class TestEndgameFireSimulator(IsolatedAsyncioTestCase):
    def test_generation(self):
        np.set_printoptions(precision=1)
        print(EndgameFireSimulator(15, 15).endgame_fire_spiral)


if __name__ == '__main__':
    unittest.main()
