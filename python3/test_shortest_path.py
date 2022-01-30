import math
import unittest
from unittest import IsolatedAsyncioTestCase

import numpy as np

from least_cost_search import LeastCostSearch
from utils import Point


class TestShortestPath(IsolatedAsyncioTestCase):

    def test_get_neighbours(self):
        grid = np.array([
            [0, 1, -1, 1],
            [0, 1, -1, 1],
            [0, 1, -1, 1],
            [0, math.inf, 1, 0],
        ])
        search = LeastCostSearch(grid, Point(0, 0))

        self.assertEqual(set(search.get_neighbors(Point(0, 0))),
                         {
                             Point(1, 0),
                             Point(0, 1)
                         })

        self.assertEqual(set(search.get_neighbors(Point(1, 1))),
                         {
                             Point(1, 0),
                             Point(0, 1),
                             Point(1, 2),
                             Point(2, 1),
                         })
        self.assertEqual(set(search.get_neighbors(Point(3, 0))),
                         {
                             Point(2, 0),
                         })
        self.assertEqual(set(search.get_neighbors(Point(2, 3))),
                         {
                             Point(3, 3),
                             Point(2, 2),
                             Point(1, 3),
                         })

    def test_shortest_path_finds_safe_spot(self):
        grid = np.array([
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [1, 1, 1, 0],
        ])
        path = LeastCostSearch(grid, Point(0, 0), search_budget=20).run(10)
        self.assertEqual(path[0], Point(0, 0))
        self.assertEqual(path[-1], Point(3, 3))
        self.assertEqual(len(path), 7)

    def test_shortest_path_does_not_go_to_the_safe_spot_through_danger(self):
        grid = np.array([
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [1, 1, 10, 10],
            [1, 1, 10, 0],
        ])
        path = LeastCostSearch(grid, Point(0, 0), search_budget=20).run(10)
        self.assertEqual(path[0], Point(0, 0))
        self.assertFalse(Point(3, 3) in path)
        self.assertFalse(Point(3, 2) in path)
        self.assertFalse(Point(2, 3) in path)
        self.assertFalse(Point(2, 2) in path)

    def test_shortest_path_does_go_to_the_safe_spot_through_danger_if_horizon_is_big(self):
        grid = np.array([
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [1, 1, 10, 10],
            [1, 1, 10, 0],
        ])
        path = LeastCostSearch(grid, Point(0, 0), search_budget=20).run(horizon=20)
        self.assertEqual(path[0], Point(0, 0))
        self.assertEqual(path[-1], Point(3, 3))
        self.assertEqual(len(path), 7)

    def test_shortest_path_does_go_to_the_big_reward_through_danger(self):
        grid = np.array([
            [10, 10, 10, 10],
            [10, 10, 10, 10],
            [10, 10, 20, 20],
            [10, 10, 20, 1],
        ])
        path = LeastCostSearch(grid, Point(0, 0), search_budget=20).run(horizon=10)
        self.assertEqual(path[0], Point(0, 0))
        self.assertEqual(path[-1], Point(3, 3))
        self.assertEqual(len(path), 7)


if __name__ == '__main__':
    unittest.main()
