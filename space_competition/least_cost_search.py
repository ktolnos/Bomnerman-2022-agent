import math
from typing import Dict, Iterator, List, Optional

import numpy as np

from game_utils import Point, PriorityQueue, get_neighbours

exclude_point_stay_cost = 10
class LeastCostSearch:

    def __init__(self, grid: np.ndarray, start: Point, exclude_points=set(), search_budget: int = 100):
        self.grid = grid
        self.start = start
        self.search_budget = search_budget
        self.exclude_points = exclude_points

    def get_neighbors(self, point: Point) -> Iterator[Point]:
        return get_neighbours(self.grid, point)

    def run(self, horizon: int) -> List[Point]:
        frontier = PriorityQueue()
        frontier.put(self.start, 0)
        came_from: Dict[Point, Optional[Point]] = dict()
        cost_so_far: Dict[Point, float] = dict()
        path_len: Dict[Point, float] = dict()
        came_from[self.start] = None
        cost_so_far[self.start] = self.grid[self.start.x, self.start.y]
        path_len[self.start] = 0
        searches = 0

        while not frontier.empty() and searches < self.search_budget:
            current: Point = frontier.get()
            searches += 1

            for neighbor in self.get_neighbors(current):
                new_cost = cost_so_far[current] + self.grid[current.x, current.y]
                if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = new_cost
                    came_from[neighbor] = current
                    path_length = path_len[current] + 1
                    path_len[neighbor] = path_length

                    if path_length >= horizon:
                        continue
                    priority = new_cost
                    frontier.put(neighbor, priority)

        min_cost = math.inf
        min_cost_point = None
        for p, length in path_len.items():
            p_stay_cost = self.grid[p.x, p.y]
            if p in self.exclude_points:
                p_stay_cost += exclude_point_stay_cost
            p_cost = cost_so_far[p] + p_stay_cost + max(0, p_stay_cost * (horizon - length - 1))
            min_cost_path_len = -1 if min_cost_point is None else path_len[min_cost_point]
            if p_cost < min_cost or (p_cost == min_cost and path_len[p] > min_cost_path_len):
                min_cost = p_cost
                min_cost_point = p

        path = []
        node = min_cost_point
        while node in came_from:
            path.append(node)
            node = came_from[node]
        path.reverse()
        return path, min_cost
