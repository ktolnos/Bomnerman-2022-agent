import time

import torch

from actions import MoveAction, BombAction, DetonateBombAction, Action
from nn.observation_converter import *


class PolicyNeuralNetPolicy:

    def __init__(self, model):
        self.busy = set()  # units that already made the move
        self.tasks = list()
        self.already_occupied_spots = list()
        self.loop = None
        self.print_queue = deque()
        self.client = None
        self.ticker = None
        self.last_was_cancelled = False
        self.debug = False
        self.model = model
        self.observation_converter = ObservationConverter()
        model.eval()

    def init(self, client, ticker):
        self.client = client
        self.ticker = ticker

    def execute_actions(self, tick_number, game_state):
        if tick_number != self.ticker.tick:
            self.tick_number = tick_number
            self.schedule_print("Cancelling policy right away for tick #{}".format(tick_number))
            return

        start_time = time.time()
        self.tick_number = tick_number

        self.busy.clear()
        for task in self.tasks:
            task.cancel()
        self.tasks.clear()
        self.already_occupied_spots.clear()

        if not self.loop:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        if tick_number != self.ticker.tick:
            self.schedule_print("Cancelling policy call after clear for tick #{}".format(tick_number))
            self.last_was_cancelled = True
            return

        clear_time = time.time()

        states_tensor = self.prepare_states(game_state, tick_number)
        if tick_number != self.ticker.tick:
            self.schedule_print("Cancelling policy call after prepare state for tick #{}".format(tick_number))
            self.last_was_cancelled = True
            return
        prepare_state_time = time.time()
        with torch.no_grad():
            self.follow_policy(states_tensor, tick_number)
        eval_model_time = time.time()

        self.loop.run_until_complete(asyncio.gather(*self.tasks))
        tasks_time = time.time()

        if tick_number != self.ticker.tick:
            self.schedule_print("Cancelling policy call after tasks for tick #{}".format(tick_number))
            self.last_was_cancelled = True
            return

        while not self.debug and not self.last_was_cancelled and self.print_queue:
            if tick_number != self.ticker.tick:
                self.last_was_cancelled = True
                return
            print(*self.print_queue.popleft())
        printing_time = time.time()

        total_time = (time.time() - start_time) * 1000
        self.schedule_print("Tick #{tick},"
                            " total time is {time}ms,\n"
                            " clear_time={clear_time}\n"
                            " prepare_state_time={prepare_state_time}\n"
                            " eval_model_time={eval_model_time}\n"
                            " tasks_time={tasks_time}\n"
                            " printing_time={printing_time}\n"
                            "".format(tick=tick_number, time=total_time,
                                      clear_time=(clear_time - start_time) * 1000,
                                      prepare_state_time=(prepare_state_time - clear_time) * 1000,
                                      eval_model_time=(eval_model_time - prepare_state_time) * 1000,
                                      tasks_time=(tasks_time - eval_model_time) * 1000,
                                      printing_time=(printing_time - tasks_time) * 1000))
        self.last_was_cancelled = False

    def prepare_states(self, game_state, tick_number):
        states = self.observation_converter.convert(game_state, tick_number)
        states = np.moveaxis(states, -1, 0)
        states_tensor = torch.Tensor(states)
        states_tensor = states_tensor.unsqueeze(0)
        return states_tensor

    def follow_policy(self, states_tensor, tick_number):
        unit_policy, bomb_policy = self.model(states_tensor)
        parser = self.observation_converter.parser
        for bomb in parser.my_armed_bombs:
            bomb_logits = bomb_policy[0, bomb.pos[0], bomb.pos[1]].numpy()
            bomb_action = np.argmax(bomb_logits)
            self.schedule_print(bomb_logits)
            if bomb_action == bomb_action_detonate:
                self.execute_action(DetonateBombAction(bomb.owner_unit_id, bomb), tick_number)
        for unit in parser.my_units:
            if self.is_busy(unit.id):
                continue
            unit_logits = unit_policy[0, :, unit.pos[0], unit.pos[1]].numpy()
            self.schedule_print(unit_logits)
            unit_action = np.argmax(unit_logits)
            if unit_action == action_move_up:
                self.execute_action(MoveAction(unit.id, MoveAction.UP), tick_number)
            if unit_action == action_move_left:
                self.execute_action(MoveAction(unit.id, MoveAction.LEFT), tick_number)
            if unit_action == action_move_right:
                self.execute_action(MoveAction(unit.id, MoveAction.RIGHT), tick_number)
            if unit_action == action_move_down:
                self.execute_action(MoveAction(unit.id, MoveAction.DOWN), tick_number)
            if unit_action == action_place_bomb:
                self.execute_action(BombAction(unit.id), tick_number)
            if unit_action == action_noop:
                self.execute_action(Action(unit.id), tick_number)

    def execute_move(self, unit_id, move, move_cell, tick_number) -> bool:
        self.already_occupied_spots.append(move_cell)
        if move:
            self.execute_action(move, tick_number)
            return True
        else:
            self.execute_action(Action(unit_id), tick_number)
            return False

    def is_busy(self, unit_id):
        return unit_id in self.busy

    def execute_action(self, action, tick_number):
        self.busy.add(action.unit_id)
        self.tasks.append(self.loop.create_task(self.send_action_acync_impl(action, tick_number)))

    def schedule_print(self, *args):
        self.debug_print(*args)
        self.print_queue.append(("Tick #{}!\n".format(self.tick_number),) + args)

    def debug_print(self, *args):
        if self.debug:
            print("Tick #{}!\n".format(self.tick_number), args)

    async def send_action_acync_impl(self, action, tick_number):
        if tick_number != self.ticker.tick:
            self.schedule_print("Action for tick {action_tick} is only sent on {curr_tick}, cancelling".format(
                action_tick=tick_number, curr_tick=self.ticker.tick
            ))
            return
        await action.send(self.client)
        self.schedule_print("Sent action {action} on tick {tick}!".format(action=action, tick=tick_number))
