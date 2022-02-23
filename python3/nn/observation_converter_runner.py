import os
from concurrent.futures.process import ProcessPoolExecutor
from dataclasses import dataclass

import numpy as np
from tqdm import tqdm

from nn.observation_converter import ObservationConverter, unit_actions_size, bomb_actions_size

replays_folder = "../../runs/replays_small"
dataset_folder = "../../runs/dataset_small_separate_actions"


@dataclass(frozen=True)
class WorkerOutput:
    unit_action_freq: np.ndarray  # [unit_actions_size]
    bomb_action_freq: np.ndarray  # [unit_actions_size]
    steps: int


def convert_replays_worker(replays):
    converter = ObservationConverter()
    unit_action_freq_agr = np.zeros((unit_actions_size,))
    bomb_action_freq_agr = np.zeros((bomb_actions_size,))
    total_steps = 0
    for filename in tqdm(replays):
        replay_path = replays_folder + "/" + filename
        history, unit_actions, unit_mask, unit_action_freq, bomb_actions, bomb_mask, bomb_action_freq = \
            converter.get_replay_history(replay_path)
        unit_action_freq_agr += unit_action_freq
        bomb_action_freq_agr += bomb_action_freq
        steps = history.shape[0]
        total_steps += steps
        result_path = dataset_folder + "/" + filename.replace(".json", "_{steps}_steps.npz".format(steps=steps))
        np.savez_compressed(result_path,
                            observations=history,
                            unit_actions=unit_actions,
                            unit_mask=unit_mask,
                            bomb_actions=bomb_actions,
                            bomb_mask=bomb_mask)
    return WorkerOutput(
        unit_action_freq_agr,
        bomb_action_freq_agr,
        total_steps
    )

def convert_replays_to_dataset():
    n_workers = 1
    pool = ProcessPoolExecutor(n_workers)
    paths = os.listdir(replays_folder)
    path_len = len(paths)
    paths_for_worker = list()

    paths_per_worker = path_len // n_workers
    processed_paths = 0
    for i in range(n_workers):
        paths_for_worker.append(paths[processed_paths:min(processed_paths + paths_per_worker, path_len)])
        processed_paths += paths_per_worker
    worker_outputs = pool.map(convert_replays_worker, paths_for_worker)
    unit_action_freq_agr = np.zeros((unit_actions_size,))
    bomb_action_freq_agr = np.zeros((bomb_actions_size,))
    total_steps = 0
    for output in worker_outputs:
        unit_action_freq_agr += output.unit_action_freq
        bomb_action_freq_agr += output.bomb_action_freq
        total_steps += output.steps

    print(f"Total Steps: {total_steps}, Unit: {unit_action_freq_agr}, Bomb: {bomb_action_freq_agr}")
    unit_class_weight = 1. - unit_action_freq_agr / np.sum(unit_action_freq_agr)
    bomb_class_weight = 1. - bomb_action_freq_agr / np.sum(bomb_action_freq_agr)
    print(f"Class weights unit: {unit_class_weight},"
          f" bomb: {bomb_class_weight}")


if __name__ == '__main__':
    convert_replays_to_dataset()
