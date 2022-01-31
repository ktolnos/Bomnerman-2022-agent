import asyncio
import os
from concurrent.futures._base import Future
from concurrent.futures.thread import ThreadPoolExecutor

from game_state import GameState
from rule_policy import Ticker

uri = os.environ.get(
    'GAME_CONNECTION_STRING') or "ws://127.0.0.1:3000/?role=agent&agentId=agentId&name=defaultName"


class Runner:
    def __init__(self, policy):
        self._client = GameState(uri)
        self._policy = policy
        self.ticker = Ticker()
        self.futures = list()

        policy.init(self._client, self.ticker)

        self._pool = ThreadPoolExecutor(2)

        # any initialization code can go here
        self._client.set_game_tick_callback(self._on_game_tick)

        loop = asyncio.get_event_loop()
        self._loop = loop
        connection = loop.run_until_complete(self._client.connect())
        tasks = [
            asyncio.ensure_future(self._client.handle_messages(connection)),
        ]
        loop.run_until_complete(asyncio.wait(tasks))

    async def _on_game_tick(self, tick_number, game_state):
        self.ticker.tick = tick_number
        print("Tick {tick}, futures {futures}".format(tick=tick_number, futures=len(self.futures)))
        map(Future.cancel, self.futures)
        self.futures.clear()
        self._pool.submit(self._policy.execute_actions, tick_number, game_state)
