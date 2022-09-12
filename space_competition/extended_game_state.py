#full info that is required for policy
from space_competition.gamestate import ParsedGameState


class ExtendedGameState():
    def __init__(self, json) -> None:
        self.gs = ParsedGameState(json)

        my_agent_id = json.get("connection").get("agent_id")

        self.my_unit_ids = set()
        self.enemy_unit_ids = set()

        for unit in json["unit_state"].values():
            if unit["agent_id"] == my_agent_id:
                self.my_unit_ids.add(unit["unit_id"])
            else:
                self.enemy_unit_ids.add(unit["unit_id"])
