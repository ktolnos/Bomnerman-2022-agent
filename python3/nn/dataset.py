import math
import os
from random import shuffle

import numpy as np
import torch
from torch.utils.data import IterableDataset
from torch.utils.data.dataset import T_co


class BombermanDataset(IterableDataset):
    def __getitem__(self, index) -> T_co:
        pass

    def __init__(self, data_dir, samples, batch_size=128, shuffle_files=True):
        super(BombermanDataset).__init__()
        self.data_dir = data_dir
        self.samples = samples
        try:
            self.samples.remove('.DS_Store')
        except ValueError:
            ...
        self.shuffle = shuffle_files
        self.batch_size = batch_size

    def __iter__(self):
        worker_info = torch.utils.data.get_worker_info()
        files_num = len(self.samples)
        if worker_info is None:  # single-process data loading, return the full iterator
            iter_start = 0
            iter_end = files_num
        else:  # in a worker process
            # split workload
            per_worker = int(math.ceil(files_num / float(worker_info.num_workers)))
            worker_id = worker_info.id
            iter_start = worker_id * per_worker
            iter_end = min(iter_start + per_worker, files_num)
        my_samples = self.samples[iter_start:iter_end]
        if self.shuffle:
            shuffle(my_samples)
        my_samples_len = len(my_samples)
        processed_samples = 0
        while processed_samples < my_samples_len:
            new_processed_samples = min(processed_samples + self.batch_size, my_samples_len)
            batch_samples = my_samples[processed_samples:new_processed_samples]
            if not batch_samples:
                break

            batch_samples_list = list()
            for sample_file in batch_samples:
                data_path = os.path.join(self.data_dir, sample_file)
                data = np.load(data_path)
                obs, unit_actions, unit_mask, bomb_actions, bomb_mask =\
                    data['observations'], \
                    data['unit_actions'], \
                    data['unit_mask'], \
                    data['bomb_actions'], \
                    data['bomb_mask'],
                for i in range(len(obs)):
                    batch_samples_list.append((obs[i], unit_actions[i], unit_mask[i], bomb_actions[i], bomb_mask[i]))
            if self.shuffle:
                shuffle(batch_samples_list)
            for tup in batch_samples_list:
                yield tup
            processed_samples = new_processed_samples
