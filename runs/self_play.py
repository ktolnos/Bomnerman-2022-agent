import asyncio
import json
import os
import subprocess
import time
from collections import Counter
from multiprocessing import Pool
from random import random
from time import sleep

import torch
import websockets

from game_state import GameState
from nn.nn_policy import PolicyNeuralNetPolicy
from rule_policy import RulePolicy, Ticker

uri_agent_a = "ws://127.0.0.1:{port}/?role=agent&agentId=agentA"
uri_agent_b = "ws://127.0.0.1:{port}/?role=agent&agentId=agentB"
uri_admin = "ws://127.0.0.1:{port}/?role=admin"
replay_dir = "self_play_replays"
replay_path = replay_dir + "/replay-{id}-{iter}.json"
logs = "self_play_logs/logs-{id}.txt"
max_seed = 9007199254740990
repeats_per_process = 5
num_processes = 12


def format_uri_with_port(uri, port):
    return uri.format(port=port)


async def connect_admin(url):
    connection = await websockets.connect(url, ping_interval=None)
    if connection.open:
        return connection


async def send_tick(admin_connection):
    await admin_connection.send("""{"type": "request_tick"}""")


async def send_reset(admin_connection):
    request = """{{"type": "request_game_reset", "world_seed":{world_seed}, "prng_seed":{prng_seed}}}"""
    request = request.format(world_seed=int(random() * max_seed), prng_seed=int(random() * max_seed))
    await admin_connection.send(request)


def run_games_repeated(proc_id: int):
    port = str(3010 + proc_id)
    game_env = dict()
    game_env["ADMIN_ROLE_ENABLED"] = "1"
    game_env["AGENT_ID_MAPPING"] = "agentA, agentB"
    game_env["INITIAL_AMMUNITION"] = "3"
    game_env["FIRE_SPAWN_INTERVAL_TICKS"] = "2"
    game_env["GAME_DURATION_TICKS"] = "300"
    game_env["GAME_START_DELAY_MS"] = "0"
    game_env["INITIAL_HP"] = "3"
    game_env["SHUTDOWN_ON_GAME_END_ENABLED"] = "0"
    game_env["TELEMETRY_ENABLED"] = "1"
    game_env["TICK_RATE_HZ"] = "10"
    game_env["TRAINING_MODE_ENABLED"] = "1"
    game_env["PORT"] = port
    gs = subprocess.Popen("./game-server-1741-osx", shell=True, env=game_env)

    sleep(3)

    policy1 = RulePolicy()
    client1 = GameState(format_uri_with_port(uri_agent_a, port))
    ticker1 = Ticker()
    policy1.init(client1, ticker1)

    model = torch.jit.load("../python3/nn/model_UNET_1.5k_vs_enemy.pth")
    policy2 = PolicyNeuralNetPolicy(model)
    client2 = GameState(format_uri_with_port(uri_agent_b, port))
    ticker2 = Ticker()
    policy2.init(client2, ticker2)

    async def _on_game_tick1(tick_number, game_state):
        print("_on_game_tick1_", proc_id, tick_number)
        ticker1.tick = tick_number
        policy1.execute_actions(tick_number, game_state)

    async def _on_game_tick2(tick_number, game_state):
        ticker2.tick = tick_number
        policy2.execute_actions(tick_number, game_state)

    loop = asyncio.get_event_loop()
    policy1.loop = loop
    policy2.loop = loop
    connection1 = loop.run_until_complete(client1.connect())
    connection2 = loop.run_until_complete(client2.connect())
    client1.set_game_tick_callback(_on_game_tick1)
    client2.set_game_tick_callback(_on_game_tick2)
    admin_connection = loop.run_until_complete(connect_admin(format_uri_with_port(uri_admin, port)))
    repeats = 0
    tick = 0
    while repeats < repeats_per_process:
        print("client tick", tick)
        while ticker1.tick < tick and not client1.replay:
            loop.run_until_complete(client1.handle_message(connection1))
        while ticker2.tick < tick and not client2.replay:
            loop.run_until_complete(client2.handle_message(connection2))

        tasks = policy1.tasks + policy2.tasks
        if tasks:
            loop.run_until_complete(asyncio.wait(tasks))
        if client1.replay:
            path = replay_path.format(id=proc_id, iter=repeats)
            with open(path, "w") as file:
                json.dump(client1.replay, file)
            client1.replay = None
            client2.replay = None
            policy1.reset()
            policy2.reset()
            repeats += 1
            tick = 0
            ticker1.tick = -1
            ticker2.tick = -1
            loop.run_until_complete(send_reset(admin_connection))
        loop.run_until_complete(send_tick(admin_connection))
        tick += 1
    gs.kill()


def main():
    started = time.time()
    pool = Pool(num_processes)
    pool.map(run_games_repeated, range(num_processes))
    score = Counter()
    for filename in os.listdir(replay_dir):
        with open(replay_dir + "/" + filename, 'r') as file:
            filedata = file.read()
            template = '"winning_agent_id": "'
            idx = filedata.find(template)
            won = filedata[idx + len(template):idx + len(template) + 1]
            if won != 'a':
                print("Lost run " + filename)
            score[won] += 1
    print(score)
    print("Time = {}s".format(
        (time.time() - started)
    ))


if __name__ == "__main__":
    main()
