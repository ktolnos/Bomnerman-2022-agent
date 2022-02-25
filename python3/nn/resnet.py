from typing import Callable

import torch
from torch import nn

from nn.network import OutConv

hidden_dim = 64
kernel_size = 3
n_blocks = 12


class SELayer(nn.Module):
    def __init__(self, n_channels: int, reduction: int = 16):
        super(SELayer, self).__init__()
        self.fc = nn.Sequential(
            nn.Linear(n_channels, n_channels // reduction, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(n_channels // reduction, n_channels, bias=False),
            nn.Sigmoid()
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, c, _, _ = x.shape
        # Average feature planes
        y = torch.flatten(x, start_dim=-2, end_dim=-1).mean(dim=-1)
        y = self.fc(y.view(b, c)).view(b, c, 1, 1)
        return x * y.expand_as(x)


class ResidualBlock(nn.Module):
    def __init__(
            self,
            in_channels: int,
            out_channels: int,
            height: int,
            width: int,
            kernel_size: int = 3,
            normalize: bool = False,
            activation: Callable = nn.ReLU,
            squeeze_excitation: bool = True,
            rescale_se_input: bool = True,
            **conv2d_kwargs
    ):
        super(ResidualBlock, self).__init__()

        # Calculate "same" padding
        # https://pytorch.org/docs/stable/generated/torch.nn.Conv2d.html
        # https://www.wolframalpha.com/input/?i=i%3D%28i%2B2x-k-%28k-1%29%28d-1%29%2Fs%29+%2B+1&assumption=%22i%22+-%3E+%22Variable%22
        assert "padding" not in conv2d_kwargs.keys()
        k = kernel_size
        d = conv2d_kwargs.get("dilation", 1)
        s = conv2d_kwargs.get("stride", 1)
        padding = (k - 1) * (d + s - 1) / (2 * s)
        assert padding == int(padding), f"padding should be an integer, was {padding:.2f}"
        padding = int(padding)

        self.conv1 = nn.Conv2d(
            in_channels=in_channels,
            out_channels=out_channels,
            kernel_size=(kernel_size, kernel_size),
            padding=(padding, padding),
            **conv2d_kwargs
        )
        # We use LayerNorm here since the size of the input "images" may vary based on the board size
        self.norm1 = nn.LayerNorm([in_channels, height, width]) if normalize else nn.Identity()
        self.act1 = activation()

        self.conv2 = nn.Conv2d(
            in_channels=out_channels,
            out_channels=out_channels,
            kernel_size=(kernel_size, kernel_size),
            padding=(padding, padding),
            **conv2d_kwargs
        )
        self.norm2 = nn.LayerNorm([in_channels, height, width]) if normalize else nn.Identity()
        self.final_act = activation()

        if in_channels != out_channels:
            self.change_n_channels = nn.Conv2d(in_channels, out_channels, (1, 1))
        else:
            self.change_n_channels = nn.Identity()

        if squeeze_excitation:
            self.squeeze_excitation = SELayer(out_channels, rescale_se_input)
        else:
            self.squeeze_excitation = nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        identity = x
        x = self.conv1(x)
        x = self.act1(self.norm1(x))
        x = self.conv2(x)
        x = self.squeeze_excitation(self.norm2(x))
        x = x + self.change_n_channels(identity)
        return self.final_act(x)


class ResNet(nn.Module):
    def __init__(self, n_channels, n_unit_classes, n_bomb_classes, width, height):
        super(ResNet, self).__init__()
        self.n_channels = n_channels
        self.n_unit_classes = n_unit_classes
        self.n_bomb_classes = n_bomb_classes

        self.base_model = nn.Sequential(
            ResidualBlock(
                in_channels=n_channels,
                out_channels=hidden_dim,
                height=height,
                width=width,
                kernel_size=kernel_size
            ),
            *[ResidualBlock(
                in_channels=hidden_dim,
                out_channels=hidden_dim,
                height=height,
                width=width,
                kernel_size=kernel_size
            ) for _ in range(n_blocks)]
        )
        self.unit_outc = OutConv(hidden_dim, n_unit_classes)
        self.bomb_outc = OutConv(hidden_dim, n_bomb_classes)

    def forward(self, x):
        x = self.base_model(x)
        logits_unit = self.unit_outc(x)
        logits_bomb = self.bomb_outc(x)
        return logits_unit, logits_bomb
