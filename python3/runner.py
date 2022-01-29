import asyncio
import os
import time

from game_state import GameState

uri = os.environ.get(
    'GAME_CONNECTION_STRING') or "ws://127.0.0.1:3000/?role=agent&agentId=agentId&name=defaultName"


class Runner:
    def __init__(self, policy):
        self._client = GameState(uri)
        self._policy = policy

        # any initialization code can go here
        self._client.set_game_tick_callback(self._on_game_tick)

        loop = asyncio.get_event_loop()
        connection = loop.run_until_complete(self._client.connect())
        tasks = [
            asyncio.ensure_future(self._client.handle_messages(connection)),
        ]
        loop.run_until_complete(asyncio.wait(tasks))

    async def _on_game_tick(self, tick_number, game_state):
        start_time = time.time()
        self._policy.execute_actions(tick_number, game_state, self._client)
        exec_time = (time.time() - start_time) * 1000
        print("Tick time is %s ms" % exec_time)
