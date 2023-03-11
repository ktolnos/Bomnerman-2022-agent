from typing import List, Optional

from actions import Action, MoveAction
from rule.state.rule_policy_state import RulePolicyState
from utils.game_utils import Point


def execute_action(state: RulePolicyState, action):
    state.busy.add(action.unit_id)
    # state.forward.enque_action(action)
    state.tasks.append(action)


def execute_move(state: RulePolicyState, unit_id, move, move_cell) -> bool:
    state.already_occupied_spots.append(move_cell)
    state.unit_id_to_target_pos[unit_id] = move_cell
    if move:
        execute_action(state, move)
        return True
    else:
        execute_action(state, Action(unit_id))
        return False


def plan_move(unit_id: str, path: List[Point]) -> Optional[Action]:
    if path is None or len(path) < 2:
        return None
    curr = path[0]
    next_move = path[1]
    return plan_move_to_point(unit_id, curr, next_move)


def plan_move_to_point(unit_id: str, curr_position: Point, target_position: Point) -> Action:
    if curr_position == target_position:
        return Action(unit_id)
    action = MoveAction.UP
    if target_position.x > curr_position.x:
        action = MoveAction.RIGHT
    if target_position.x < curr_position.x:
        action = MoveAction.LEFT
    if target_position.y < curr_position.y:
        action = MoveAction.DOWN

    return MoveAction(unit_id, action, target_pos=target_position)
