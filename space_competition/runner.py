import asyncio
import os
from concurrent.futures._base import Future
from concurrent.futures.thread import ThreadPoolExecutor

from game_state import GameState
from rule_policy import Ticker, np

uri = os.environ.get(
    'GAME_CONNECTION_STRING') or "ws://127.0.0.1:3000/?role=agent&agentId=agentId&name=defaultName"


class Runner:
    def __init__(self, policy):
        np.set_printoptions(precision=3, linewidth=200)

        self._client = GameState(uri)
        self._policy = policy

        policy.init(self._client)
        #policy.debug = True

        self._client.set_game_tick_callback(self._on_game_tick)

        loop = asyncio.get_event_loop()
        self._loop = loop
        connection = loop.run_until_complete(self._client.connect())
        tasks = [
            asyncio.ensure_future(self._client.handle_messages(connection)),
        ]
        loop.run_until_complete(asyncio.wait(tasks))

    async def _on_game_tick(self, tick_number, game_state):
        print("RUNNER: Tick {tick}".format(tick=tick_number))
        self._policy.execute_actions(tick_number, game_state)
