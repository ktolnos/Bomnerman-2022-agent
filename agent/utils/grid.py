from typing import List, TYPE_CHECKING

import numpy as np
from parsing.settings import close_cell_danger
from utils.game_utils import manhattan_distance, Point, Unit
if TYPE_CHECKING:
    from parsing.parser import Parser


def draw_cross(arr: np.ndarray, x: int, y: int, rad: int, value: int, draw_cross_four_times: bool = False):
    arr[x, y] += value * 4 if draw_cross_four_times else value
    for i in range(1, rad):
        if x + i < arr.shape[0]:
            arr[x + i, y] += value
        if x - i >= 0:
            arr[x - i, y] += value
        if y + i < arr.shape[1]:
            arr[x, y + i] += value
        if y - i >= 0:
            arr[x, y - i] += value


def draw_cross_assign(arr: np.ndarray, x: int, y: int, rad: int, value: int):
    for i in range(rad):
        if x + i < arr.shape[0]:
            arr[x + i, y] = value
        if x - i >= 0:
            arr[x - i, y] = value
        if y + i < arr.shape[1]:
            arr[x, y + i] = value
        if y - i >= 0:
            arr[x, y - i] = value


def check_side_wall(
        parser: 'Parser',
        point: Point,
        ignore_unit_id: str
) -> bool:
    if point.x < 0 or point.y < 0 or point.x >= parser.w or point.y >= parser.h:
        return False
    if parser.walkable_map[point] != 0 or parser.danger_map[point] != 0:
        return False
    unit = parser.units_map[point]
    if unit and unit.id != ignore_unit_id:
        return False
    for enemy in parser.enemy_units:
        if manhattan_distance(point, enemy.pos) == 1:
            return False
    return True


def check_cell_free(
        parser: 'Parser',
        x: int,
        y: int,
        count_any_non_danger_wall_as_free: bool,
        is_horizontal: bool,
        ignore_unit_id: str
):
    if x < 0 or x >= parser.w or y < 0 or y >= parser.h:
        return False, True  # not free and stop iter
    if parser.walkable_map[x, y] != 0 or parser.danger_map[x, y] != 0:
        return False, True  # not free and stop iter
    unit = parser.units_map[x, y]
    if unit and unit.id != ignore_unit_id:
        return False, True  # not free and stop iter
    for enemy in parser.enemy_units:
        if manhattan_distance(Point(x, y), enemy.pos) <= 1:
            return False, True
    if count_any_non_danger_wall_as_free:
        return True, True  # free and stop iter
    side_wall_1 = Point(x, y + 1) if is_horizontal else Point(x + 1, y)
    if check_side_wall(parser, side_wall_1, ignore_unit_id):
        return True, True
    side_wall_2 = Point(x, y - 1) if is_horizontal else Point(x - 1, y)
    if check_side_wall(parser, side_wall_2, ignore_unit_id):
        return True, True

    if parser.cell_occupation_danger_map[x, y] <= close_cell_danger * 1:
        return True, True  # free and stop iter
    return False, False  # not free, look further


def check_free(parser: 'Parser', p: Point, rad: int, bomb_rad: int,
               ignore_unit_id: str = None) -> bool:
    """
    :return: True if cross has at least one direction free
    """
    x, y = p
    for i in range(1, rad):
        free, stop_iter = check_cell_free(parser, x + i, y, i >= bomb_rad, True, ignore_unit_id)
        if free:
            return True
        if stop_iter:
            break
    for i in range(1, rad):
        free, stop_iter = check_cell_free(parser, x - i, y, i >= bomb_rad, True, ignore_unit_id)
        if free:
            return True
        if stop_iter:
            break
    for i in range(1, rad):
        free, stop_iter = check_cell_free(parser, x, y + i, i >= bomb_rad, False, ignore_unit_id)
        if free:
            return True
        if stop_iter:
            break
    for i in range(1, rad):
        free, stop_iter = check_cell_free(parser, x, y - i, i >= bomb_rad, False, ignore_unit_id)
        if free:
            return True
        if stop_iter:
            break
    return False
