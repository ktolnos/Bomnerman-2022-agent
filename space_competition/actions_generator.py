from typing import List, Dict
from actions import Action, BombAction, DetonateBombAction, MoveAction
from gamestate import BombState, ParsedGameState, Wall
from space_competition.game_utils import Point
from parser import bomb_arming_ticks


def generate_possible_actions(gs: ParsedGameState) -> Dict[str, List[Action]]:
    actions = dict()
    for unit in gs.units:
        pos = unit.pos
        actions = [Action(unit.unit_id)]
        if unit.stunned <= gs.tick:
            add_action_for_pos(unit.unit_id, Point(pos.x, pos.y-1), gs, MoveAction.UP, actions)
            add_action_for_pos(unit.unit_id, Point(pos.x, pos.y+1), gs, MoveAction.DOWN, actions)
            add_action_for_pos(unit.unit_id, Point(pos.x-1, pos.y), gs, MoveAction.LEFT, actions)
            add_action_for_pos(unit.unit_id, Point(pos.x+1, pos.y), gs, MoveAction.RIGHT, actions)
            for bomb in gs.units_to_bombs:
                if bomb.created <= gs.tick - bomb_arming_ticks:
                    actions.append(DetonateBombAction(unit.unit_id, bomb))


def add_action_for_pos(unit_id: str, pos: Point, gs: ParsedGameState, action: str, actions: List[Action]):
    if pos.x < 0 or pos.x >= gs.w or pos.y < 0 or pos.y >= gs.h:
        return
    if isinstance(gs.map[pos], Wall) or isinstance(gs.map[pos], BombState):
        return
    actions.append(MoveAction(unit_id, action))
