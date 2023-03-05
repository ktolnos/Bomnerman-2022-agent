import asyncio

from actions import MoveAction
from rule.blow_up_enemies import blow_up_enemies
from rule.blow_up_path_to_center import blow_up_path_to_center
from rule.move_to_different_map_parts import move_units_to_different_map_parts
from rule.move_to_safer_spot import move_all_to_safer_spot
from rule.place_bombs import place_bombs
from rule.rule_policy_state import RulePolicyState
from rule.suicide_bomb import suicide_bomb
from utils.policy import prod_print


class RulePolicy:

    def __init__(self):
        self.state = RulePolicyState()

    def reset(self):
        self.state = RulePolicyState()

    def init(self, client):
        self.state.client = client
        self.state.loop = asyncio.get_event_loop()

    def execute_actions(self, tick_number, game_state):
        self.state.update(tick_number, game_state)

        blow_up_enemies(self.state)
        place_bombs(self.state)
        suicide_bomb(self.state)
        blow_up_path_to_center(self.state)

        if self.state.parser.free_from_endgame_fire > 49:
            move_units_to_different_map_parts(self.state)
        else:
            self.state.unit_id_to_diff_map_side_target_pos.clear()

        move_all_to_safer_spot(self.state)

        self.__execute_pending_actions()

        while not self.state.debug and self.state.print_queue:
            print(*self.state.print_queue.popleft())

    def __execute_pending_actions(self):
        unit_id_to_pos = dict()
        for unit in self.state.parser.my_units:
            unit_id_to_pos[unit.id] = unit.pos
        postpned_actions = self.state.tasks
        executed_actions = []
        while postpned_actions:
            for action in postpned_actions:
                if action is MoveAction and action.target_pos:
                    has_conflict = False  # execute actions that move out of conflicting positions first
                    for id, pos in unit_id_to_pos:
                        if pos == action.target_pos:
                            has_conflict = True
                            break
                    if has_conflict:
                        continue
                    unit_id_to_pos[action.unit_id] = action.target_pos
                executed_actions.append(action)
                self.state.loop.create_task(self.__send_action_async_impl(action, self.state.tick_number))
            for action in executed_actions:
                postpned_actions.remove(action)
            executed_actions.clear()

    async def __send_action_async_impl(self, action, tick_number):
        await action.send(self.state.client)
        prod_print(self.state, "Sent action {action} on tick {tick}!".format(action=action, tick=tick_number))