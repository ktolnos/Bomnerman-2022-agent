import torch
import torch.nn.functional as F
from torch import nn


class DoubleConv(nn.Module):
    """(convolution => [BN] => ReLU) * 2"""

    def __init__(self, in_channels, out_channels, mid_channels=None):
        super().__init__()
        if not mid_channels:
            mid_channels = out_channels
        self.double_conv = nn.Sequential(
            nn.Conv2d(in_channels, mid_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(mid_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(mid_channels, out_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True)
        )

    def forward(self, x):
        return self.double_conv(x)


class Down(nn.Module):
    """Downscaling with maxpool then double conv"""

    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.maxpool_conv = nn.Sequential(
            nn.MaxPool2d(2),
            DoubleConv(in_channels, out_channels)
        )

    def forward(self, x):
        return self.maxpool_conv(x)


class Up(nn.Module):
    """Upscaling then double conv"""

    def __init__(self, in_channels, out_channels, bilinear=True):
        super().__init__()

        # if bilinear, use the normal convolutions to reduce the number of channels
        if bilinear:
            self.up = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True)
            self.conv = DoubleConv(in_channels, out_channels, in_channels // 2)
        else:
            self.up = nn.ConvTranspose2d(in_channels, in_channels // 2, kernel_size=2, stride=2)
            self.conv = DoubleConv(in_channels, out_channels)

    def forward(self, x1, x2):
        x1 = self.up(x1)
        # input is CHW
        diffY = x2.size()[2] - x1.size()[2]
        diffX = x2.size()[3] - x1.size()[3]

        x1 = F.pad(x1, [
            torch.div(diffX, 2, rounding_mode='floor'),
            diffX - torch.div(diffX, 2, rounding_mode='floor'),
            torch.div(diffY, 2, rounding_mode='floor'),
            diffY - torch.div(diffY, 2, rounding_mode='floor')
        ])
        # if you have padding issues, see
        # https://github.com/HaiyongJiang/U-Net-Pytorch-Unstructured-Buggy/commit/0e854509c2cea854e247a9c615f175f76fbb2e3a
        # https://github.com/xiaopeng-liao/Pytorch-UNet/commit/8ebac70e633bac59fc22bb5195e513d5832fb3bd
        x = torch.cat([x2, x1], dim=1)
        return self.conv(x)


class OutConv(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(OutConv, self).__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size=1)

    def forward(self, x):
        return self.conv(x)


class UNet(nn.Module):
    def __init__(self, n_channels, n_unit_classes, n_bomb_classes, bilinear=True):
        super(UNet, self).__init__()
        self.n_channels = n_channels
        self.n_unit_classes = n_unit_classes
        self.n_bomb_classes = n_bomb_classes
        self.bilinear = bilinear

        self.inc = DoubleConv(n_channels, 64)
        self.down1 = Down(64, 128)
        factor = 2 if bilinear else 1
        self.down2 = Down(128, 256 // factor)
        self.up3 = Up(256, 128 // factor, bilinear)
        self.up4 = Up(128, 64, bilinear)
        self.unit_outc = OutConv(64, n_unit_classes)
        self.bomb_outc = OutConv(64, n_bomb_classes)

    def forward(self, x):
        x1 = self.inc(x)
        x2 = self.down1(x1)
        x3 = self.down2(x2)
        x = self.up3(x3, x2)
        x = self.up4(x, x1)
        logits_unit = self.unit_outc(x)
        logits_bomb = self.bomb_outc(x)
        return logits_unit, logits_bomb


class DiceLoss(nn.Module):
    def __init__(self, n_classes):
        super(DiceLoss, self).__init__()
        self.n_classes = n_classes

    def _dice_loss(self, score, target):
        target = target.float()
        smooth = 1e-5
        intersect = torch.sum(score * target)
        y_sum = torch.sum(target * target)
        z_sum = torch.sum(score * score)
        loss = (2 * intersect + smooth) / (z_sum + y_sum + smooth)
        loss = 1 - loss
        return loss

    def forward(self, inputs, target):
        inputs = torch.softmax(inputs, dim=1)
        assert inputs.size() == target.size(), 'predict {} & target {} shape do not match'.format(inputs.size(), target.size())
        loss = 0.0
        for i in range(0, self.n_classes):
            dice = self._dice_loss(inputs[:, i], target[:, i])
            loss += dice
        return loss / self.n_classes


class MaskedWeightedCrossEntropyLoss(nn.Module):
    def __init__(self, n_classes, class_weights):
        super(MaskedWeightedCrossEntropyLoss, self).__init__()
        self.class_weights = class_weights
        self.n_classes = n_classes

    def forward(self, inputs, target, mask):
        inputs = torch.softmax(inputs, dim=1)
        inputs_count = torch.sum(mask)
        loss = F.cross_entropy(inputs, target, weight=self.class_weights, reduction='none')
        masked_loss = torch.mul(loss, mask)
        loss_sum = masked_loss.sum()
        if inputs_count:
            return loss_sum / inputs_count
        else:
            return 0
