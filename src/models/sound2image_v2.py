import torch
import torch.nn as nn
from torch.nn import functional as F
from modules.inverted_residual import InvertedRes2d
from modules.residual import FirstBlockDown2d, BlockUpsample2d
from modules.upsample import Upsample
from modules.self_attention import SelfAttention2d
from modules.norms import NORMS, perform_sn


class ImageFeature2Image(nn.Module):
    def __init__(self, self_attention=True, sn=False, norm="BN", dropout=0):
        super().__init__()

        bias = False
        if norm is None:
            bias = True

        # UP:
        self.up_block1 = BlockUpsample2d(
            in_channels=4096,
            out_channels=512,
            dropout=dropout,
            activation="relu",
            normalization=norm,
            seblock=False,
            sn=sn,
            bias=bias,
        )

        self.up_block2 = BlockUpsample2d(
            in_channels=512,
            out_channels=256,
            dropout=dropout,
            activation="relu",
            normalization=norm,
            seblock=False,
            sn=sn,
            bias=bias,
        )

        self.up_block3 = BlockUpsample2d(
            in_channels=256,
            out_channels=128,
            dropout=0,
            activation="relu",
            normalization=norm,
            seblock=False,
            sn=sn,
            bias=bias,
        )

        self.up_block4 = BlockUpsample2d(
            in_channels=128,
            out_channels=64,
            dropout=0,
            activation="relu",
            normalization=norm,
            seblock=False,
            sn=sn,
            bias=bias,
        )

        self.up_block5 = BlockUpsample2d(
            in_channels=64,
            out_channels=64,
            dropout=0,
            activation="relu",
            normalization=norm,
            seblock=True,
            sn=sn,
            bias=bias,
        )

        self.sa_layer = None
        if self_attention is True:
            self.sa_layer = SelfAttention2d(in_channels=64, sn=sn)

        self.up_block6 = BlockUpsample2d(
            in_channels=64,
            out_channels=32,
            dropout=0,
            activation="relu",
            normalization=norm,
            seblock=False,
            sn=sn,
            bias=bias,
        )

        self.up_block7 = BlockUpsample2d(
            in_channels=32,
            out_channels=32,
            dropout=0,
            activation="relu",
            normalization=norm,
            seblock=False,
            sn=sn,
            bias=bias,
        )

        self.up_block8 = BlockUpsample2d(
            in_channels=32,
            out_channels=16,
            dropout=0,
            activation="relu",
            normalization=norm,
            seblock=False,
            sn=sn,
            bias=bias,
        )

        self.last_norm = None
        if norm is not None:
            self.last_norm = NORMS[norm](num_channels=16)

        self.last_act = getattr(F, "relu")

        self.last_conv = perform_sn(
            nn.Conv2d(
                in_channels=16,
                out_channels=3,
                kernel_size=1,
                bias=True,
                padding=0,
                stride=1,
            ),
            sn=sn,
        )

        self.last_tanh = nn.Tanh()

    def forward(self, input):
        # UP:
        #   BLOCK: Residual block
        #   ACTIVATION_FUNC: ReLU
        #   NORM: BN (AdaIN?)
        # Dimention -> [B, 4096, 1, 1] with drop_out -> [B, 1024, 2, 2])
        up = self.up_block1(input.view(-1, 4096, 1, 1))

        # Dimention -> [B, 1024, 2, 2] with drop_out -> [B, 512, 4, 4]
        up = self.up_block2(up)

        # Dimention -> [B, 512, 4, 4] with drop_out -> [B, 256, 8, 8]
        up = self.up_block3(up)

        # Dimention -> [B, 128, 16, 16]
        up = self.up_block4(up)

        # Dimention -> [B, 128, 32, 32]
        up = self.up_block5(up)

        if self.sa_layer is not None:
            up = self.sa_layer(up)

        # Dimention -> [B, 64, 64, 64]
        up = self.up_block6(up)

        # Dimention -> [B, 32, 128, 128]
        up = self.up_block7(up)

        # Dimention -> [B, 16, 256, 256]
        up = self.up_block8(up)

        # last norm
        if self.last_norm is not None:
            up = self.last_norm(up)

        up = self.last_act(up)

        # Dimention -> [B, 3, 256, 256]
        up = self.last_tanh(self.last_conv(up))

        return up


class Generator(nn.Module):
    def __init__(self, self_attention=True, sn=False, norm="BN", dropout=0):
        super().__init__()
        self.imgfeat2img = ImageFeature2Image(
            self_attention=self_attention, sn=sn, norm=norm, dropout=dropout
        )

        bias = False
        if norm is None:
            bias = True

        # DOWN:
        self.dn_block1 = FirstBlockDown2d(
            in_channels=2,
            out_channels=16,
            activation="leaky_relu",
            normalization=norm,
            downscale=True,
            seblock=False,
            sn=sn,
            bias=bias,
        )

        self.dn_block2 = InvertedRes2d(
            in_channels=16,
            planes=32,  # 64
            out_channels=32,
            dropout=0,
            activation="leaky_relu",
            normalization=norm,
            downscale=True,
            seblock=False,
            sn=sn,
            bias=bias,
        )

        self.dn_block3 = InvertedRes2d(
            in_channels=32,
            planes=64,  # 128
            out_channels=64,
            dropout=0,
            activation="leaky_relu",
            normalization=norm,
            downscale=True,
            seblock=False,
            sn=sn,
            bias=bias,
        )

        self.dn_block4 = InvertedRes2d(
            in_channels=64,
            planes=128,  # 256
            out_channels=128,
            dropout=0,
            activation="leaky_relu",
            normalization=norm,
            downscale=True,
            seblock=False,
            sn=sn,
            bias=bias,
        )

        self.sa_layer = None
        if self_attention is True:
            self.sa_layer = SelfAttention2d(in_channels=128, sn=sn)

        self.dn_block5 = InvertedRes2d(
            in_channels=128,
            planes=256,  # 512
            out_channels=256,
            dropout=0,
            activation="leaky_relu",
            normalization=norm,
            downscale=True,
            seblock=True,
            sn=sn,
            bias=bias,
        )

        self.dn_block6 = InvertedRes2d(
            in_channels=256,
            planes=512,
            out_channels=512,
            dropout=0,
            activation="leaky_relu",
            normalization=norm,
            downscale=True,
            seblock=False,
            sn=sn,
            bias=bias,
        )

        self.global_avg_pool = nn.AdaptiveAvgPool2d([2, 2])

        self.last_norm = None
        if norm is not None:
            self.last_norm = NORMS[norm](num_channels=512)

        self.last_act = getattr(F, "relu")

        self.last_conv = perform_sn(
            nn.Conv2d(
                in_channels=512,
                out_channels=4096,
                kernel_size=2,
                bias=True,
                padding=0,
                stride=1,
            ),
            sn=sn,
        )

    def forward(self, input, is_feature=False):
        # DOWN:
        #   BLOCK: Inverted Residual block
        #   ACTIVATION_FUNC: LReLU
        #   NORM: IN
        # Input Dimention: [B, 2, 1024, 128]
        # Dimention -> [B, 16, 512, 64]

        if is_feature is False:
            dn = self.dn_block1(input)

            # Dimention -> [B, 32, 256, 32]
            dn = self.dn_block2(dn)

            # Dimention -> [B, 64, 128, 16]
            dn3 = self.dn_block3(dn)

            # Dimention -> [B, 128, 64, 8]
            dn4 = self.dn_block4(dn3)

            if self.sa_layer is not None:
                dn4 = self.sa_layer(dn4)

            # Dimention -> [B, 256, 32, 4]
            dn5 = self.dn_block5(dn4)

            # Dimention -> [B, 512, 16, 2]
            dn6 = self.dn_block6(dn5)

            # Dimention -> [B, 4096]
            latent_vec = self.last_conv(
                self.global_avg_pool(self.last_act(self.last_norm(dn6)))
            ).view(-1, 4096)

        elif is_feature is True:
            latent_vec = input

        generated_img = self.imgfeat2img(latent_vec)

        return generated_img, latent_vec


class Discriminator(nn.Module):
    def __init__(self, self_attention=True, sn=True, norm=None):
        super().__init__()

        bias = False
        if norm is None:
            bias = True

        # DOWN:
        self.dn_block1 = FirstBlockDown2d(
            in_channels=3,
            out_channels=8,
            activation="leaky_relu",
            normalization=norm,
            downscale=True,
            seblock=False,
            sn=sn,
            bias=bias,
        )

        self.dn_block2 = InvertedRes2d(
            in_channels=8,
            planes=16,  # 64
            out_channels=16,
            dropout=0,
            activation="leaky_relu",
            normalization=norm,
            downscale=True,
            seblock=False,
            sn=sn,
            bias=bias,
        )

        self.dn_block3 = InvertedRes2d(
            in_channels=16,
            planes=32,  # 128
            out_channels=32,
            dropout=0,
            activation="leaky_relu",
            normalization=norm,
            downscale=True,
            seblock=False,
            sn=sn,
            bias=bias,
        )

        self.sa_layer = None
        if self_attention is True:
            self.sa_layer = SelfAttention2d(in_channels=32, sn=sn)

        self.dn_block4 = InvertedRes2d(
            in_channels=32,
            planes=64,  # 256
            out_channels=64,
            dropout=0,
            activation="leaky_relu",
            normalization=norm,
            downscale=True,
            seblock=True,
            sn=sn,
            bias=bias,
        )

        self.dn_block5 = InvertedRes2d(
            in_channels=64,
            planes=128,  # 256
            out_channels=128,
            dropout=0,
            activation="leaky_relu",
            normalization=norm,
            downscale=True,
            seblock=False,
            sn=sn,
            bias=bias,
        )

        self.dn_block6 = InvertedRes2d(
            in_channels=128,
            planes=256,  # 512
            out_channels=256,
            dropout=0,
            activation="leaky_relu",
            normalization=norm,
            downscale=True,
            seblock=False,
            sn=sn,
            bias=bias,
        )

        self.global_avg_pool = nn.AdaptiveAvgPool2d([1, 1])

        self.last_norm = None
        if norm is not None:
            self.last_norm = NORMS[norm](num_channels=256)

        self.last_act = getattr(F, "leaky_relu")

        self.output = perform_sn(
            nn.Conv2d(
                in_channels=256,
                out_channels=1,
                kernel_size=1,
                bias=True,
                padding=0,
                stride=1,
            ),
            sn=sn,
        )

    def forward(self, input):
        # DOWN:
        #   BLOCK: Inverted Residual block
        #   ACTIVATION_FUNC: LReLU
        #   NORM: SN
        # Input Dimention: [B, 3, 256, 256]
        # Dimention -> [B, 8, 128, 128]
        dn = self.dn_block1(input)

        # Dimention -> [B, 16, 64, 64]
        dn = self.dn_block2(dn)

        # Dimention -> [B, 32, 32, 32]
        dn = self.dn_block3(dn)

        if self.sa_layer is not None:
            dn = self.sa_layer(dn)

        # Dimention -> [B, 64, 16, 16]
        dn = self.dn_block4(dn)

        # Dimention -> [B, 128, 8, 8]
        dn = self.dn_block5(dn)

        # Dimention -> [B, 256, 4, 4]
        dn = self.dn_block6(dn)

        # last norm
        if self.last_norm is not None:
            dn = self.last_norm(dn)

        # Dimention -> [B, 512, 1, 1]
        dn = self.last_act(dn)

        dn = self.global_avg_pool(dn)

        output = self.output(dn)

        return output
