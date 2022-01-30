import heapq
from dataclasses import dataclass
from typing import Any, List, Tuple, Iterator

import numpy as np


def point(unit):
    coordinates = unit.get("coordinates")
    return Point(*coordinates)


def blast_r(blast_diameter):
    return (blast_diameter + 1) // 2


def uid(unit):
    return unit.get("unit_id")


@dataclass(frozen=True)
class Point:
    x: int
    y: int

    def __lt__(self, other):
        return self.x < other.x


def get_neighbours(grid: np.array, center: Point, include: Point = None, include_center=False,
                   predicate=lambda x: x == 0) -> Iterator[Point]:
    x = center.x
    y = center.y
    neighbors = [
        Point(x + 1, y),
        Point(x - 1, y),
        Point(x, y - 1),
        Point(x, y + 1),
    ]

    if (x + y) % 2 == 0:  # to prevent ugly (diagonal) paths
        neighbors.reverse()

    size_x = grid.shape[0] - 1
    size_y = grid.shape[1] - 1

    def is_valid(p: Point) -> bool:
        if p == include:
            return True
        if p.x < 0 or p.x > size_x:
            return False
        if p.y < 0 or p.y > size_y:
            return False
        return predicate(grid[p.x, p.y])

    result = filter(is_valid, neighbors)
    if include_center:
        result_list = list(result)
        result_list.append(center)
        return result_list
    return result


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int


class PriorityQueue:
    def __init__(self):
        self.elements: List[Tuple[int, Any]] = []

    def empty(self) -> bool:
        return not self.elements

    def put(self, item: Any, priority: int):
        heapq.heappush(self.elements, (priority, item))

    def get(self) -> Any:
        return heapq.heappop(self.elements)[1]
