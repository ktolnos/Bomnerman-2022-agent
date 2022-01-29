from typing import Dict, Iterator, List, Optional

import numpy as np

from utils import Point, PriorityQueue


class AStar:
    def __init__(self, grid: np.ndarray, start: Point, end: Point, offset: int):
        self.offset = offset
        self.grid = grid
        self.start = start
        self.end = end

    @staticmethod
    def h_score(current_node, end):
        return abs(current_node.x - end.x) + abs(current_node.y - end.y)

    def get_neighbors(self, point: Point) -> Iterator[Point]:
        x = point.x
        y = point.y
        neighbors = [
            Point(x + 1, y),
            Point(x - 1, y),
            Point(x, y - 1),
            Point(x, y + 1),
        ]

        if (x + y) % 2 == 0:  # to prevent ugly (diagonal) paths
            neighbors.reverse()

        size_x = self.grid.shape[0] - 1
        size_y = self.grid.shape[1] - 1
        # s = self.offset

        def is_valid(p: Point) -> bool:
            if p == self.end:
                return True
            if p.x < 0 or p.x >= size_x:
                return False
            if p.y < 0 or p.y >= size_y:
                return False
            # left = max(p.x - s, 0)
            # right = min(p.x + s + 1, size_x)
            # top = max(p.y - s, 0)
            # bottom = min(p.y + s + 1, size_y)
            return self.grid[p.x, p.y] == 0

        return filter(is_valid, neighbors)

    def run(self) -> List[Point]:
        frontier = PriorityQueue()
        frontier.put(self.start, 0)
        came_from: Dict[Point, Optional[Point]] = dict()
        cost_so_far: Dict[Point, float] = dict()
        came_from[self.start] = None
        cost_so_far[self.start] = 0

        while not frontier.empty():
            current: Point = frontier.get()

            if current == self.end:
                break

            for neighbor in self.get_neighbors(current):
                new_cost = cost_so_far[current] + 1
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
        return path
