from copy import deepcopy
from curses.ascii import GS
from operator import ne
from tkinter import W
from actions import Action, MoveAction, BombAction, DetonateBombAction

from gamestate import BombState, Explosion, ParsedGameState, Powerup, UnitState, Wall
from game_utils import Bomb, Point
from parser import bomb_arming_ticks
from collections import defaultdict

bomb_expiry_ticks = 30
blast_expiry_ticks = 5
invulnurability_ticks = 5
# TODO implement endgame fire
# game_duration_ticks = 200
# fire_spawn_interval_ticks = 2

class ForwardModel():
    def __init__(self) -> None:
        self.move_actions = set()
        self.detonate_actions = set()
        self.bomb_actions = set()

        
    def clear(self):
        self.move_actions.clear()
        self.detonate_actions.clear()
        self.bomb_actions.clear()

    def enque_action(self, action: Action):
        if isinstance(action, BombAction):
            self.bomb_actions.add(action)
        elif isinstance(action, DetonateBombAction):
            self.detonate_actions.add(action)
        else:
            self.move_actions.add(action)
        
    def step(self, game_state: ParsedGameState) -> ParsedGameState:
        new_gs = deepcopy(game_state)
        new_gs.tick += 1

        expire_entities(new_gs)
        pickup_powerups(new_gs)
        self.process_bomb_actions(new_gs)
        self.process_detonate_actions(new_gs)
        self.process_move_actions(new_gs)
           
        return new_gs

    def process_bomb_actions(self, new_gs: ParsedGameState):
        for action in self.bomb_actions:
            unit_id = action.unit_id
            unit: UnitState = new_gs.units_map[unit_id]
            if unit.stunned >= new_gs.tick:
                continue
            if len(new_gs.units_to_bombs[unit_id]) >= 3:
                continue
            bomb = BombState(
                    unit.pos,
                    unit.blast_r,
                    action.unit_id,
                    new_gs.tick,
                    new_gs.tick + bomb_expiry_ticks
                )
            new_gs.map[unit.pos] = bomb
            new_gs.units_to_bombs[unit_id].append(bomb)

    def process_detonate_actions(self, new_gs: ParsedGameState):    
        for action in self.detonate_actions:
            potential_bomb = new_gs.map[action.bomb.pos]
            if potential_bomb != None and isinstance(potential_bomb, BombState):
            #and game_state.tick - potential_bomb.created >= bomb_arming_ticks:
                detonate_bomb(action.bomb.pos, new_gs)

    def process_move_actions(self, new_gs: ParsedGameState):
        intended_positions = defaultdict(int)
        for action in self.move_actions:
            unit_id = action.unit_id
            unit = new_gs.units_map[unit_id]
            if unit.stunned >= new_gs.tick:
                intended_positions[unit.pos] += 1
                continue
            intended_positions[get_target_pos(action, unit)] += 1

        for action in self.move_actions:
            unit_id = action.unit_id
            unit = new_gs.units_map[unit_id]
            new_pos = get_target_pos(action, unit)
            if intended_positions[new_pos] >= 2:
                continue
          
            if unit.stunned >= new_gs.tick:
                continue
            target_obj = new_gs.map[new_pos]
            blast_r = unit.blast_r
            if isinstance(target_obj, Explosion):
                damage_unit(unit, new_gs)
            elif target_obj is not None and not isinstance(target_obj, Powerup): # wall or bomb
                continue
            unit = new_gs.units_map[unit_id]
            new_gs.units.remove(unit)
            new_unit = UnitState(
                unit.unit_id,
                unit.agent_id,
                new_pos,
                unit.hp,
                blast_r,
                unit.invulnerable,
                unit.stunned,
            )
            new_gs.units.add(new_unit)
            new_gs.units_map[unit.unit_id] = new_unit

def expire_entities(new_gs: ParsedGameState):
    for point in new_gs.expiry_dict[new_gs.tick]:
        if isinstance(new_gs.map[point], BombState):
            detonate_bomb(point, new_gs)
        else:
            new_gs.map[point] = None
    new_gs.expiry_dict.pop(new_gs.tick, None)

def pickup_powerups(new_gs: ParsedGameState):
    units_to_replace = dict()
    for unit in new_gs.units:
        if isinstance(new_gs.map[unit.pos], Powerup):
            blast_r = unit.blast_r
            if new_gs.map[unit.pos].type == "bp":
                blast_r += 2
            # TODO handle fp
            new_gs.map[unit.pos] = None
            units_to_replace[unit] = UnitState(
                unit.unit_id,
                unit.agent_id,
                unit.pos,
                unit.hp,
                blast_r,
                unit.invulnerable,
                unit.stunned,
            )
    for unit, new_unit in units_to_replace.items():
        new_gs.units.remove(unit)
        new_gs.units.add(new_unit)
        new_gs.units_map[unit.unit_id] = new_unit

        
def detonate_bomb(pos: Point, gs: ParsedGameState):
    bomb: BombState = gs.map[pos]
    gs.map[pos] = None
    gs.units_to_bombs[bomb.owner_unit_id].remove(bomb)
    rad = bomb.blast_r // 2 + 1
    arr = gs.map
    x, y = pos
    for i in range(rad):
        if x + i >= arr.shape[0]:
            break
        if explode(arr[x+i, y], gs, Point(x+i, y)):
            break
    for i in range(rad):
        if x - i < 0:
            break
        if explode(arr[x - i, y], gs, Point(x - i, y)):
            break
    for i in range(rad):
        if y + i >= arr.shape[1]:
            break
        if explode(arr[x, y + i], gs, Point(x, y + i)):
            break
    for i in range(rad):
        if y - i < 0:
            break
        if explode(arr[x, y - i], gs, Point(x, y - i)):
            return False

def explode(obj, gs, pos) -> bool:
    for unit in gs.units:
        if unit.pos == pos:
            damage_unit(unit, gs)
    if obj is None or isinstance(obj, Powerup) or isinstance(obj, Explosion):
        gs.map[pos] = Explosion(
                pos,
                gs.tick + blast_expiry_ticks
            )
        return False
    if isinstance(obj, Wall):
        hp = obj.hp
        if hp == -1 or hp is None:
            return True
        hp -= 1
        if hp <= 0:
            gs.map[pos] = None
        else:
            gs.map[pos] = Wall(pos, hp)
        return True
    if isinstance(obj, BombState):
        detonate_bomb(obj, gs)


def damage_unit(unit: UnitState, gs: ParsedGameState):
    if unit.invulnerable <= gs.tick:
        gs.units.remove(unit)
        new_unit = UnitState(
            unit.unit_id,
            unit.agent_id,
            unit.pos,
            unit.hp-1,
            unit.blast_r,
            gs.tick + invulnurability_ticks,
            unit.stunned,
        )
        gs.units.add(new_unit)
        gs.units_map[unit.unit_id] = new_unit

def get_target_pos(action: Action, unit: UnitState):
    new_pos = unit.pos
    if not isinstance(action, MoveAction):
        return new_pos
    if action.action == MoveAction.UP:
        new_pos = Point(unit.pos.x, unit.pos.y + 1)
    if action.action == MoveAction.DOWN:
        new_pos = Point(unit.pos.x, unit.pos.y - 1)
    if action.action == MoveAction.LEFT:
        new_pos = Point(unit.pos.x - 1, unit.pos.y)
    if action.action == MoveAction.RIGHT:
        new_pos = Point(unit.pos.x + 1, unit.pos.y)
    return new_pos