import os
from random import shuffle

import torch
import tqdm
from torch import optim
from torch.utils.data import DataLoader
from torchsummary import summary

from nn.dataset import BombermanDataset
from nn.network import MaskedWeightedCrossEntropyLoss
from nn.observation_converter import observation_layers
from nn.resnet import ResNet

dataset_folder = "../../runs/dataset_small_separate_actions"


def train_model(model, dataloader, validation_loader, unit_criterion, bomb_criterion, optimizer, scheduler, num_epochs):
    model.train()
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device)

    for epoch in range(num_epochs):
        epoch_loss = 0.0
        total_len = 0
        model.train()
        for item in tqdm.tqdm(dataloader):
            states = item[0].to(device).float()
            unit_actions = item[1].to(device).long()
            unit_mask = item[2].to(device).bool()
            bomb_actions = item[3].to(device).long()
            bomb_mask = item[4].to(device).bool()

            optimizer.zero_grad()

            unit_policy, bomb_policy = model(states)
            unit_loss = unit_criterion(unit_policy, unit_actions, unit_mask)
            bomb_loss = bomb_criterion(bomb_policy, bomb_actions, bomb_mask)

            loss = unit_loss + bomb_loss
            loss.backward()
            optimizer.step()

            batch_size = len(states)
            total_len += batch_size
            epoch_loss += loss.item() * batch_size

        epoch_loss = epoch_loss / total_len
        scheduler.step()

        valid_loss = 0.0
        model.eval()
        valid_len = 0
        for item in tqdm.tqdm(validation_loader):
            states = item[0].to(device).float()
            unit_actions = item[1].to(device).long()
            unit_mask = item[2].to(device).bool()
            bomb_actions = item[3].to(device).long()
            bomb_mask = item[4].to(device).bool()

            unit_policy, bomb_policy = model(states)
            unit_loss = unit_criterion(unit_policy, unit_actions, unit_mask)
            bomb_loss = bomb_criterion(bomb_policy, bomb_actions, bomb_mask)

            loss = unit_loss + bomb_loss

            batch_size = len(states)
            valid_len += batch_size
            valid_loss += loss.item() * batch_size
        valid_loss /= valid_len
        print(
            f'Epoch {epoch + 1}/{num_epochs} | Loss: {epoch_loss:.4f} | Validation loss: {valid_loss:.4f} | LR: {scheduler.get_last_lr()[0]:.6f}')
    model.eval()
    model.cpu()
    traced = torch.jit.trace(model, torch.rand(1, model.n_channels, 15, 15))
    traced.save('model.pth')


def execute_training():
    model = ResNet(n_channels=observation_layers, n_unit_classes=6, n_bomb_classes=2, width=15, height=15)
    summary(model, (17, 15, 15), batch_size=256)
    samples = os.listdir(dataset_folder)
    shuffle(samples)
    val_train_split = 0.1
    val_start_idx = int(len(samples) * (1 - val_train_split))
    dataloader = DataLoader(
        BombermanDataset(dataset_folder, samples[:val_start_idx], batch_size=256),
        batch_size=256,
        num_workers=0
    )
    validation_loader = DataLoader(
        BombermanDataset(dataset_folder, samples[val_start_idx:], batch_size=1, shuffle_files=False),
        batch_size=256,
        num_workers=0
    )
    unit_criterion = MaskedWeightedCrossEntropyLoss(
        model.n_unit_classes,
        class_weights=torch.Tensor([0.06404648, 1.7984221, 1.80659228, 1.87150684, 1.88965003, 10.14628923])
    )
    bomb_criterion = MaskedWeightedCrossEntropyLoss(model.n_bomb_classes,
                                                    class_weights=torch.Tensor([3.49787056, 40.3708781]))
    optimizer = optim.AdamW(model.parameters(), lr=1e-3)
    epochs = 5
    scheduler = optim.lr_scheduler.CosineAnnealingWarmRestarts(optimizer, T_0=epochs, eta_min=1e-6)
    train_model(model, dataloader, validation_loader, unit_criterion, bomb_criterion
                , optimizer, scheduler, num_epochs=epochs)


if __name__ == '__main__':
    execute_training()
