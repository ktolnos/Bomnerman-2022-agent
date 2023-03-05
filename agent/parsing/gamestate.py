from collections import defaultdict
from dataclasses import dataclass
import numpy as np
from utils.game_utils import point
from utils.game_utils import Point

owner_unit_id = "unit_id"


@dataclass(frozen=True)
class UnitState:
    unit_id: str
    agent_id: str
    pos: Point
    hp: int
    blast_r: int
    invulnerable: int
    stunned: int


def parse_unit(json) -> UnitState:
    return UnitState(
        json["unit_id"],
        json["agent_id"],
        point(json),
        json["hp"],
        json["blast_diameter"],
        json["invulnerable"],
        json["stunned"]
    )


@dataclass(frozen=True)
class Powerup():
    pos: Point
    type: str
    expires: int

    def __repr__(self) -> str:
        return f"P({self.expires})"


@dataclass(frozen=True)
class Wall():
    pos: Point
    hp: int

    def __repr__(self) -> str:
        return f"W({self.hp})"


@dataclass(frozen=True)
class Explosion():
    pos: Point
    expires: int

    def __repr__(self) -> str:
        return f"E({self.expires})"


@dataclass(frozen=True)
class BombState():
    pos: Point
    blast_r: int
    owner_unit_id: str
    created: int
    expires: int

    def __repr__(self) -> str:
        return f"B(exp={self.expires}, r={self.blast_r})"


# partial info that is required for forward model
class ParsedGameState:

    def __init__(self, json) -> None:
        self.units = set(map(parse_unit, json["unit_state"].values()))
        w = json.get("world").get("width")
        h = json.get("world").get("height")
        self.w = w
        self.h = h
        self.map = np.empty((w, h), dtype=object)
        self.expiry_dict = defaultdict(list)
        self.units_map = dict()
        self.units_to_bombs = defaultdict(list)
        for unit in self.units:
            self.units_map[unit.unit_id] = unit
        self.tick = json["tick"]
        for entity in json["entities"]:
            e_type = entity["type"]
            coords = Point(entity["x"], entity["y"])
            new_entity = None
            if e_type == "b":
                new_entity = BombState(
                    coords,
                    entity["blast_diameter"],
                    entity.get(owner_unit_id),
                    entity["created"],
                    entity["expires"]
                )
                self.units_to_bombs[entity.get(owner_unit_id)].append(new_entity)
            elif e_type == "fp" or e_type == "bp":
                new_entity = Powerup(
                    coords,
                    entity["type"],
                    entity["expires"]
                )
            elif e_type == "m" or e_type == "w" or e_type == "o":
                new_entity = Wall(
                    coords,
                    entity.get("hp")
                )
            elif e_type == "x":
                new_entity = Explosion(
                    coords,
                    entity.get("expires", 10000)
                )
            if "expires" in entity:
                self.expiry_dict[entity["expires"]].append(coords)
            self.map[coords] = new_entity

    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, ParsedGameState) and self.units == __o.units and np.array_equal(self.map, __o.map)

    def __hash__(self) -> int:
        return hash((self.units, self.map))

    def __str__(self) -> str:
        return "GameState(" + str(self.map) + ")"
