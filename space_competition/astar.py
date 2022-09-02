import math
from typing import Dict, Iterator, List, Optional

import numpy as np

from game_utils import Point, PriorityQueue, get_neighbours, manhattan_distance


class AStar:
    def __init__(self, grid: np.ndarray, start: Point, end: Point):
        self.grid = grid
        self.start = start
        self.end = end

    @staticmethod
    def h_score(current_node, end):
        return manhattan_distance(current_node, end)

    def get_neighbors(self, point: Point) -> Iterator[Point]:
        return get_neighbours(self.grid, point, include=self.end)

    def run(self) -> (List[Point], float):
        frontier = PriorityQueue()
        frontier.put(self.start, 0)
        came_from: Dict[Point, Optional[Point]] = dict()
        cost_so_far: Dict[Point, float] = dict()
        came_from[self.start] = None
        cost_so_far[self.start] = self.grid[self.start]

        while not frontier.empty():
            current: Point = frontier.get()

            if current == self.end:
                break

            for neighbor in self.get_neighbors(current):
                new_cost = cost_so_far[current] + self.grid[neighbor]
                if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = new_cost
                    priority = new_cost + self.h_score(neighbor, self.end)
                    frontier.put(neighbor, priority)
                    came_from[neighbor] = current

        path = []
        node = self.end
        while node in came_from:
            path.append(node)
            node = came_from[node]

        path.reverse()
        cost = cost_so_far[self.end] if self.end in cost_so_far else math.inf
        return path, cost
