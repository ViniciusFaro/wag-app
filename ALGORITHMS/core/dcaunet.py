"""DCA U-Net architecture reproduced from AGENTS/specification.MD."""

import math

import torch
from torch import nn
from torch.nn import functional as F


class RoPE(nn.Module):
    def __init__(self, sequence_len, embedding_dim):
        super().__init__()

        self.sequence_len = sequence_len
        self.embedding_dim = embedding_dim

        pos_vec = torch.arange(0, sequence_len, 1, dtype=torch.float32)
        dims_vec = torch.arange(0, embedding_dim // 2, 1, dtype=torch.float32)

        unity = torch.ones([sequence_len, embedding_dim // 2])
        pos = pos_vec.reshape(sequence_len, 1) * unity
        dims = dims_vec.reshape(1, embedding_dim // 2) * unity

        theta = pos / 10000 ** (2 * dims / embedding_dim)
        self.register_buffer("sin", torch.sin(theta))
        self.register_buffer("cos", torch.cos(theta))

    def forward(self, x):
        batch_size = x.size()[0]
        pairs = x.reshape(batch_size, self.sequence_len, self.embedding_dim // 2, 2)
        out1 = self.cos * pairs[:, :, :, 0] - self.sin * pairs[:, :, :, 1]
        out2 = self.sin * pairs[:, :, :, 0] + self.cos * pairs[:, :, :, 1]
        out = torch.stack((out1, out2), dim=-1)
        return out.reshape(batch_size, self.sequence_len, self.embedding_dim)


class DoubleConv(nn.Module):
    def __init__(self, in_channels, out_channels, dropout_prob=0.20):
        super().__init__()

        # define double convolution operation with dropout
        self.operation = nn.Sequential(
            nn.Conv2d(
                in_channels=in_channels,
                out_channels=out_channels,
                kernel_size=3,
                stride=1,
                padding=1,
            ),
            nn.BatchNorm2d(num_features=out_channels),
            nn.ReLU(inplace=True),
            nn.Dropout(p=dropout_prob),
            nn.Conv2d(
                in_channels=out_channels,
                out_channels=out_channels,
                kernel_size=3,
                stride=1,
                padding=1,
            ),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Dropout(p=dropout_prob),
        )

    def forward(self, x):
        return self.operation(x)


class SelfAttention(nn.Module):
    """
    Efficient spatial self-attention for CNN feature maps.

    Input:  [B, C, H, W]
    Output: [B, C, H, W]

    Features:
      - Multi-head scaled dot-product attention
      - 2D Rotary Positional Embeddings
      - Spatial token reduction
      - Learnable residual scaling
    """

    def __init__(
        self,
        semantic: int,
        compressed: int = 1,
        num_heads: int = 4,
        max_tokens: int = 576,
        dropout: float = 0.0,
    ):
        super().__init__()

        if semantic % num_heads != 0:
            raise ValueError("semantic must be divisible by num_heads")

        self.head_dim = semantic // num_heads

        if self.head_dim % 4 != 0:
            raise ValueError("head_dim must be divisible by 4 for 2D RoPE")

        if compressed < 1 or max_tokens < 1:
            raise ValueError("compressed and max_tokens must be positive")

        self.compressed = compressed
        self.max_tokens = max_tokens
        self.num_heads = num_heads
        self.channels = semantic
        self.dropout = dropout

        # Pre-attention normalization
        self.norm = nn.LayerNorm(semantic)

        # Joint QKV projection
        self.qkv = nn.Linear(semantic, 3 * semantic)

        # Output projection
        self.proj = nn.Linear(semantic, semantic)
        self.out_dropout = nn.Dropout(dropout)

        # Small initial residual contribution
        self.gamma = nn.Parameter(torch.tensor(1e-2))

        # RoPE frequencies for each spatial axis
        axis_dim = self.head_dim // 2

        inv_freq = 1.0 / (
            10000 ** (torch.arange(0, axis_dim, 2, dtype=torch.float32) / axis_dim)
        )

        self.register_buffer("inv_freq", inv_freq, persistent=False)

    @staticmethod
    def _rotate(t, cos, sin):
        even = t[..., 0::2]
        odd = t[..., 1::2]

        return torch.stack(
            (
                even * cos - odd * sin,
                even * sin + odd * cos,
            ),
            dim=-1,
        ).flatten(-2)

    def _rope2d(self, t, h, w):
        """
        t: [B, heads, H*W, head_dim]
        """
        b, heads, n, d = t.shape

        t = t.reshape(b, heads, h, w, d)
        half = d // 2

        yy = torch.arange(h, device=t.device, dtype=self.inv_freq.dtype)
        xx = torch.arange(w, device=t.device, dtype=self.inv_freq.dtype)

        angle_y = torch.outer(yy, self.inv_freq)
        angle_x = torch.outer(xx, self.inv_freq)

        cos_y = angle_y.cos().to(t.dtype)[None, None, :, None, :]
        sin_y = angle_y.sin().to(t.dtype)[None, None, :, None, :]

        cos_x = angle_x.cos().to(t.dtype)[None, None, None, :, :]
        sin_x = angle_x.sin().to(t.dtype)[None, None, None, :, :]

        # Rotate height and width channel groups separately
        y = self._rotate(t[..., :half], cos_y, sin_y)
        x = self._rotate(t[..., half:], cos_x, sin_x)

        return torch.cat((y, x), dim=-1).reshape(b, heads, n, d)

    def forward(self, x):
        b, c, h, w = x.shape

        # ----------------------------------------
        # 1. Spatial token reduction
        # ----------------------------------------
        ph = max(1, h // self.compressed)
        pw = max(1, w // self.compressed)

        # Enforce maximum attention token budget
        if ph * pw > self.max_tokens:
            ratio = math.sqrt(self.max_tokens / (ph * pw))

            ph = max(1, int(ph * ratio))
            pw = max(1, int(pw * ratio))

        z = F.adaptive_avg_pool2d(x, (ph, pw))

        # [B, C, ph, pw] -> [B, N, C]
        z = z.flatten(2).transpose(1, 2)
        z = self.norm(z)

        # ----------------------------------------
        # 2. Multi-head QKV projection
        # ----------------------------------------
        qkv = self.qkv(z).reshape(
            b,
            ph * pw,
            3,
            self.num_heads,
            self.head_dim,
        )

        # [3, B, heads, N, head_dim]
        q, k, v = qkv.permute(2, 0, 3, 1, 4).unbind(0)

        # ----------------------------------------
        # 3. 2D RoPE applied to Q and K
        # ----------------------------------------
        q = self._rope2d(q, ph, pw)
        k = self._rope2d(k, ph, pw)

        # ----------------------------------------
        # 4. Optimized PyTorch attention
        # ----------------------------------------
        z = F.scaled_dot_product_attention(
            q,
            k,
            v,
            dropout_p=(self.dropout if self.training else 0.0),
            is_causal=False,
        )

        # ----------------------------------------
        # 5. Restore spatial layout
        # ----------------------------------------
        z = z.transpose(1, 2).contiguous()
        z = z.reshape(b, ph * pw, c)

        z = self.out_dropout(self.proj(z))

        z = z.transpose(1, 2).reshape(b, c, ph, pw)

        # Recover original feature-map resolution
        z = F.interpolate(
            z,
            size=(h, w),
            mode="bilinear",
            align_corners=False,
        )

        # ----------------------------------------
        # 6. Residual connection
        # ----------------------------------------
        return x + self.gamma * z


class DCAUNet(nn.Module):
    def __init__(self):
        super().__init__()

        # input [3, 768, 576]

        # encoder: [64, 256, 384, 384]
        self.encoder1 = DoubleConv(in_channels=3, out_channels=64)
        self.encoder2 = DoubleConv(in_channels=64, out_channels=256)
        self.encoder3 = DoubleConv(in_channels=256, out_channels=384)
        self.encoder4 = DoubleConv(in_channels=384, out_channels=384)

        self.selfatt1 = SelfAttention(
            semantic=64, compressed=8, num_heads=4, max_tokens=576
        )

        self.selfatt2 = SelfAttention(
            semantic=256, compressed=4, num_heads=4, max_tokens=576
        )

        self.selfatt3 = SelfAttention(
            semantic=384, compressed=2, num_heads=8, max_tokens=576
        )

        self.selfatt4 = SelfAttention(
            semantic=384, compressed=1, num_heads=8, max_tokens=576
        )

        # bottleneck
        self.bottom_conv = nn.Conv2d(384, 384, kernel_size=3, stride=1, padding=1)
        self.bottom_normalizer = nn.BatchNorm2d(384)

        self.unity_conv = nn.Conv2d(384, 384, kernel_size=1, stride=1, padding=0)
        self.bottom_drop = nn.Dropout(p=0.20)

        # decoder
        self.transpose3 = nn.ConvTranspose2d(384, 384, kernel_size=2, stride=2)
        self.decoder3 = DoubleConv(in_channels=768, out_channels=384)

        self.transpose2 = nn.ConvTranspose2d(384, 256, kernel_size=2, stride=2)
        self.decoder2 = DoubleConv(in_channels=512, out_channels=256)

        self.transpose1 = nn.ConvTranspose2d(256, 64, kernel_size=2, stride=2)
        self.decoder1 = DoubleConv(in_channels=128, out_channels=64)

        self.final_conv = nn.Conv2d(64, 4, kernel_size=3, stride=1, padding=1)

        self.pool = nn.MaxPool2d(2, 2)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):

        # encoder
        enc1 = self.selfatt1(self.encoder1(x))
        enc2 = self.selfatt2(self.encoder2(self.pool(enc1)))
        enc3 = self.selfatt3(self.encoder3(self.pool(enc2)))
        enc4 = self.selfatt4(self.encoder4(self.pool(enc3)))

        # bottleneck
        bottom1 = self.bottom_drop(
            self.relu(self.bottom_normalizer(self.bottom_conv(enc4)))
        )
        bottom2 = self.bottom_drop(
            self.relu(self.bottom_normalizer(self.unity_conv(bottom1)))
        )

        # decoder
        dec3 = self.decoder3(torch.cat([self.transpose3(bottom2), enc3], dim=1))
        dec2 = self.decoder2(torch.cat([self.transpose2(dec3), enc2], dim=1))
        dec1 = self.decoder1(torch.cat([self.transpose1(dec2), enc1], dim=1))

        return self.final_conv(dec1)
