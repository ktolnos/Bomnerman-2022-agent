import random
from typing import Union


class Action:
    async def send(self, client):
        ...


class MoveAction(Action):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    ALL = [UP, DOWN, LEFT, RIGHT]

    def __init__(self, unit_id, action=None):
        if action is None:
            action = random.choice(MoveAction.ALL)
        self.unit_id = unit_id
        self.action = action

    async def send(self, client):
        await client.send_move(self.action, self.unit_id)


class BombAction(Action):
    def __init__(self, unit_id):
        self.unit_id = unit_id

    async def send(self, client):
        await client.send_bomb(self.unit_id)


class DetonateBombAction(Action):
    def __init__(self, unit_id, bomb):
        self.unit_id = unit_id
        self.bomb = bomb

    async def send(self, client):
        x, y = self.bomb.get("x"), self.bomb.get("y")
        await client.send_detonate(x, y, self.unit_id)


class DetonateFirstAction(Action):
    def __init__(self, unit_id):
        self.unit_id = unit_id

    async def send(self, client):
        bomb_coordinates = self._get_bomb_to_detonate(client)
        if bomb_coordinates is not None:
            x, y = bomb_coordinates
            await client.send_detonate(x, y, self.unit_id)

    def _get_bomb_to_detonate(self, client) -> Union[int, int] or None:
        entities = client._state.get("entities")
        bombs = list(filter(lambda entity: entity.get(
            "unit_id") == self.unit_id and entity.get("type") == "b", entities))
        bomb = next(iter(bombs or []), None)
        if bomb is not None:
            return [bomb.get("x"), bomb.get("y")]
        else:
            return None