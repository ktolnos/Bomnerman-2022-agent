import torch

from nn.nn_policy import PolicyNeuralNetPolicy, observation_layers
from runner import Runner


def main():
    model = torch.jit.load("nn/model_UNET_1.5k_vs_enemy_corrected_weights.pth")
    for i in range(5):  # warm up
        model.forward(torch.rand(1, observation_layers, 15, 15))

    Runner(PolicyNeuralNetPolicy(model))


if __name__ == "__main__":
    main()
