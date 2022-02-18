import math
import unittest
from unittest import IsolatedAsyncioTestCase

import numpy as np

from astar import AStar
from game_utils import Point
from least_cost_search import LeastCostSearch


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
        path, cost = LeastCostSearch(grid, Point(0, 0), search_budget=20).run(10)
        self.assertEqual(path[0], Point(0, 0))
        self.assertEqual(path[-1], Point(3, 3))
        self.assertEqual(len(path), 7)

    def test_in_safe_environment_goes_somewhere(self):
        grid = np.array([
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
        ])
        path, cost = LeastCostSearch(grid, Point(0, 0), search_budget=20).run(10)
        self.assertEqual(path[0], Point(0, 0))
        self.assertEqual(path[-1], Point(3, 3))
        self.assertEqual(len(path), 7)

    def test_inf_is_wall(self):
        grid = np.array([
            [0, math.inf, math.inf, math.inf],
            [0, 0, 0, math.inf],
            [math.inf, math.inf, 0, math.inf],
            [math.inf, math.inf, math.inf, math.inf],
        ])
        path, cost = LeastCostSearch(grid, Point(0, 0), search_budget=20).run(10)
        self.assertEqual(path[0], Point(0, 0))
        self.assertEqual(path[-1], Point(2, 2))
        self.assertEqual(len(path), 5)

    def test_shortest_path_does_not_go_to_the_safe_spot_through_danger(self):
        grid = np.array([
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [1, 1, 10, 10],
            [1, 1, 10, 0],
        ])
        path, cost = LeastCostSearch(grid, Point(0, 0), search_budget=20).run(10)
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
        path, cost = LeastCostSearch(grid, Point(0, 0), search_budget=20).run(horizon=20)
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
        path, cost = LeastCostSearch(grid, Point(0, 0), search_budget=20).run(horizon=10)
        self.assertEqual(path[0], Point(0, 0))
        self.assertEqual(path[-1], Point(3, 3))
        self.assertEqual(len(path), 7)

    def test_in_real_env(self):
        """
        Use debugger to check why behaviour is wrong.
        """
        inf = math.inf
        grid = np.array(
            [[inf, inf, inf, 1., 1., 0., inf, 0., 1., 0., 0., 1., 0., 1., inf],
             [inf, 1., 1., 1., 1., 0., inf, 0., 1., 0., inf, 1., 0., inf, 1.],
             [0., 3., 0., inf, 3., inf, inf, 0., 0., 0., inf, 1., 0., inf, 0.],
             [0., 1., inf, 3., 0., 0., 0., inf, inf, 0., 0., 0., 0., inf, inf],
             [0., inf, 1., 0., 3., 0., 3., 0., inf, 0., 0., inf, 3., 1., 1.],
             [1., 1., inf, 1., 0., 1., inf, 0., 0., 1., 0., 3., inf, 0., 1.],
             [0., 1., 1., 1., 0., 1., 0., 0., 0., 0., 0., 0., 1., 0., 0.],
             [0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0.],
             [0., 1., 1., 1., 0., 1., 0., 0., 0., 0., 0., 0., 1., 0., 0.],
             [1., 1., inf, 1., 0., 1., inf, 0., 0., 1., 0., 3., inf, 0., 1.],
             [0., inf, 1., 0., 3., 0., 3., 0., inf, 0., 0., inf, 3., 1., 1.],
             [0., 1., inf, 3., 0., 0., 0., inf, inf, 0., 0., 0., 0., inf, inf],
             [0., 3., 0., inf, 3., inf, inf, 0., 0., 0., inf, 1., 0., inf, 0.],
             [inf, 1., 1., 1., 1., 0., inf, 0., 1., 0., inf, 1., 0., inf, 1.],
             [inf, inf, inf, 1., 1., 0., inf, 0., 1., 0., 0., 1., 0., 1., inf], ],
        )
        path, cost = AStar(grid, Point(3, 10), Point(7, 7)).run()


if __name__ == '__main__':
    unittest.main()
