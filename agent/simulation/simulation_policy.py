from parsing.extended_game_state import ExtendedGameState
from utils.actions_generator import generate_possible_actions
from simulation.forward_model import ForwardModel
import asyncio


class SimulationPolicy:
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.tasks = list()
        self.forward_model = ForwardModel()

    def init(self, client):
        pass

    def execute_actions(self, tick_number, game_state):
        extended_game_state = ExtendedGameState(game_state)
        gs = extended_game_state.gs
        actions_dict = generate_possible_actions(gs)
        for unit, actions in actions_dict.items():
            pass

    def execute_action(self, action, tick_number):
        self.tasks.append(self.loop.create_task(self.send_action_acync_impl(action, tick_number)))

    def prod_print(self, *args):
        print("Tick #{}!\n".format(self.tick_number), *args)

    def debug_print(self, *args):
        if self.debug:
            print("Tick #{}!\n".format(self.tick_number), args)
