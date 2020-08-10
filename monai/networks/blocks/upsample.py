# Copyright 2020 MONAI Consortium
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Optional, Sequence, Union

import torch
import torch.nn as nn

from monai.networks.layers.factories import Conv
from monai.networks.utils import icnr_init, pixelshuffle
from monai.utils import UpsampleMode, ensure_tuple_rep


class UpSample(nn.Module):
    """
    Upsample with either kernel 1 conv + interpolation or transposed conv.
    """

    def __init__(
        self,
        spatial_dims: int,
        in_channels: int,
        out_channels: Optional[int] = None,
        scale_factor: Union[Sequence[float], float] = 2,
        with_conv: bool = False,
        mode: Union[UpsampleMode, str] = UpsampleMode.LINEAR,
        align_corners: Optional[bool] = True,
    ) -> None:
        """
        Args:
            spatial_dims: number of spatial dimensions of the input image.
            in_channels: number of channels of the input image.
            out_channels: number of channels of the output image. Defaults to `in_channels`.
            scale_factor: multiplier for spatial size. Has to match input size if it is a tuple. Defaults to 2.
            with_conv: whether to use a transposed convolution for upsampling. Defaults to False.
            mode: {``"nearest"``, ``"linear"``, ``"bilinear"``, ``"bicubic"``, ``"trilinear"``}
                If ends with ``"linear"`` will use ``spatial dims`` to determine the correct interpolation.
                This corresponds to linear, bilinear, trilinear for 1D, 2D, and 3D respectively.
                The interpolation mode. Defaults to ``"linear"``.
                See also: https://pytorch.org/docs/stable/nn.html#upsample
            align_corners: set the align_corners parameter of `torch.nn.Upsample`. Defaults to True.
        """
        super().__init__()
        scale_factor_ = ensure_tuple_rep(scale_factor, spatial_dims)
        if not out_channels:
            out_channels = in_channels
        if not with_conv:
            mode = UpsampleMode(mode)
            linear_mode = [UpsampleMode.LINEAR, UpsampleMode.BILINEAR, UpsampleMode.TRILINEAR]
            if mode in linear_mode:  # choose mode based on spatial_dims
                mode = linear_mode[spatial_dims - 1]
            self.upsample = nn.Sequential(
                Conv[Conv.CONV, spatial_dims](in_channels=in_channels, out_channels=out_channels, kernel_size=1),
                nn.Upsample(scale_factor=scale_factor_, mode=mode.value, align_corners=align_corners),
            )
        else:
            self.upsample = Conv[Conv.CONVTRANS, spatial_dims](
                in_channels=in_channels, out_channels=out_channels, kernel_size=scale_factor_, stride=scale_factor_
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Tensor in shape (batch, channel, spatial_1[, spatial_2, ...).
        """
        return torch.as_tensor(self.upsample(x))


class SubpixelUpsample(nn.Module):
    """
    Upsample via using a subpixel CNN. This module supports 1D, 2D and 3D input images.
    The module is consisted with two parts. First of all, a convolutional layer is employed
    to increase the number of channels into: ``in_channels * (scale_factor ** spatial_dims)``.
    Secondly, a pixel shuffle manipulation is utilized to aggregates the feature maps from
    low resolution space and build the super resolution space.
    The first part of the module is not fixed, a sequential layers can be used to replace the
    default single layer.
    The idea comes from:
    https://arxiv.org/abs/1609.05158
    The pixel shuffle mechanism refers to:
    https://github.com/pytorch/pytorch/blob/master/aten/src/ATen/native/PixelShuffle.cpp
    and:
    https://github.com/pytorch/pytorch/pull/6340/files
    """

    def __init__(
        self, spatial_dims: int, in_channels: int, scale_factor: int = 2, conv_block: Optional[nn.Module] = None,
    ) -> None:
        """
        Args:
            spatial_dims: number of spatial dimensions of the input image.
            in_channels: number of channels of the input image.
            scale_factor: multiplier for spatial size. Defaults to 2.
            conv_block: a conv block to extract feature maps before upsampling. Defaults to None.
                When ``conv_block is None``, one reserved conv layer will be utilized.
        """
        super().__init__()

        if scale_factor <= 0:
            raise ValueError("the `scale_factor` multiplier should be an integer and no less than 1.")
        
        self.spatial_dims = spatial_dims
        self.scale_factor = scale_factor
        
        if conv_block is None:
            conv_out_channels = in_channels * (scale_factor ** spatial_dims)
            self.conv_block = Conv[Conv.CONV, spatial_dims](
                in_channels=in_channels, out_channels=conv_out_channels, kernel_size=3, stride=1, padding=1,
            )
            
            icnr_init(self.conv_block, self.scale_factor)
        else:
            self.conv_block = conv_block

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Tensor in shape (batch, channel, spatial_1[, spatial_2, ...).
        """
        x = self.conv_block(x)
        x = pixelshuffle(x, self.spatial_dims, self.scale_factor)
        return x
