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
        self.ticker = Ticker()
        self.future = None

        policy.init(self._client, self.ticker)

        self._pool = ThreadPoolExecutor(max_workers=1)

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
        print("RUNNER: Tick {tick}".format(tick=tick_number))
        if self.future and not self.future.done():
            print("RUNNER: Cancelled prev in thread pull for tick {}".format(tick_number))
            self._policy.last_was_cancelled = True
            self.future.cancel()
        self.future = self._pool.submit(self._policy.execute_actions, tick_number, game_state)
        self.future.add_done_callback(worker_callbacks)


def worker_callbacks(f: Future):
    if f.cancelled():
        return

    e = f.exception()

    if e is None:
        return

    trace = []
    tb = e.__traceback__
    while tb is not None:
        trace.append({
            "filename": tb.tb_frame.f_code.co_filename,
            "name": tb.tb_frame.f_code.co_name,
            "lineno": tb.tb_lineno
        })
        tb = tb.tb_next
    print(str({
        'type': type(e).__name__,
        'message': str(e),
        'trace': trace
    }))
