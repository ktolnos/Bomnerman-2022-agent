import torch

from nn.nn_policy import PolicyNeuralNetPolicy
from runner import Runner


def main():
    model = torch.jit.load("nn/model.pth")
    Runner(PolicyNeuralNetPolicy(model))


if __name__ == "__main__":
    main()
