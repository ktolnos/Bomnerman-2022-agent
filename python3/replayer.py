import asyncio
import json

from game_state import GameState
from rule_policy import RulePolicy, Ticker, np

# replay_path = "../logs/replay.json"
replay_path = "../runs/arxiv/replay-78-1644097313.134485-1644097313.150521.json"
# replay_path = "../lost_runs/lucky-lock-vs-honorable-friend.json"
target_tick = 285
target_agent = 'a'


class Connection:
    def __init__(self, game_state):
        self.game_state = game_state

    def get(self, str):
        assert str == "agent_id"
        return target_agent

    async def send(self, *args):
        self.game_state.on_unit_action(json.loads(args[0]))
        print("Sent to connection:", *args)


def main():
    np.set_printoptions(precision=3, linewidth=200)

    game_state = GameState("")

    with open(replay_path, 'r') as json_file:
        replay = json.load(json_file)
    replay_payload = replay.get("payload")

    policy = RulePolicy()
    policy.debug = True
    ticker = Ticker()
    policy.init(game_state, ticker)
    initial_state = replay_payload.get("initial_state")
    connection = Connection(game_state)

    game_state.on_game_state(initial_state)
    game_state.connection = connection
    game_state.state["connection"] = connection

    loop = asyncio.get_event_loop()
    last_tick_number = 0
    for tick in replay_payload.get("history"):
        tick_number = tick.get("tick")
        if tick_number > target_tick:
            for i in range(0, target_tick - last_tick_number):
                ticker.tick = last_tick_number + i
                policy.execute_actions(ticker.tick, game_state.state)
            ticker.tick = target_tick
            policy.execute_actions(target_tick, game_state.state)
            break
        task = loop.create_task(game_state.on_game_tick(tick))
        loop.run_until_complete(asyncio.gather(task))
        last_tick_number = tick_number
        if tick_number == target_tick:
            ticker.tick = tick_number
            policy.execute_actions(tick_number, game_state.state)
            break


if __name__ == "__main__":
    main()



