# Copyright (c) MONAI Consortium
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# =========================================================================
# Adapted from https://github.com/huggingface/diffusers
# which has the following license:
# https://github.com/huggingface/diffusers/blob/main/LICENSE
#
# Copyright 2022 UC Berkeley Team and The HuggingFace Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========================================================================

from __future__ import annotations

from collections.abc import Sequence

import torch
from torch import nn

__all__ = ["DiffusionModelUNetMaisi"]


from monai.networks.nets.diffusion_model_unet import DiffusionModelUNet
from generative.networks.nets.diffusion_model_unet import get_timestep_embedding


class DiffusionModelUNetMaisi(DiffusionModelUNet):
    def __init__(
        self,
        spatial_dims: int,
        in_channels: int,
        out_channels: int,
        num_res_blocks: Sequence[int] | int = (2, 2, 2, 2),
        num_channels: Sequence[int] = (32, 64, 64, 64),
        attention_levels: Sequence[bool] = (False, False, True, True),
        norm_num_groups: int = 32,
        norm_eps: float = 1e-6,
        resblock_updown: bool = False,
        num_head_channels: int | Sequence[int] = 8,
        with_conditioning: bool = False,
        transformer_num_layers: int = 1,
        cross_attention_dim: int | None = None,
        num_class_embeds: int | None = None,
        upcast_attention: bool = False,
        use_flash_attention: bool = False,
        dropout_cattn: float = 0.0,
        input_top_region_index: bool = False,
        input_bottom_region_index: bool = False,
        input_spacing: bool = False,
    ) -> None:
        super().__init__(
            spatial_dims=spatial_dims,
            in_channels=in_channels,
            out_channels=out_channels,
            num_res_blocks=num_res_blocks,
            num_channels=num_channels,
            attention_levels=attention_levels,
            norm_num_groups=norm_num_groups,
            norm_eps=norm_eps,
            resblock_updown=resblock_updown,
            num_head_channels=num_head_channels,
            with_conditioning=with_conditioning,
            transformer_num_layers=transformer_num_layers,
            cross_attention_dim=cross_attention_dim,
            num_class_embeds=num_class_embeds,
            upcast_attention=upcast_attention,
            use_flash_attention=use_flash_attention,
            dropout_cattn=dropout_cattn,
        )
        
        self.input_top_region_index = input_top_region_index
        self.input_bottom_region_index = input_bottom_region_index
        self.input_spacing = input_spacing
        
        time_embed_dim = num_channels[0] * 4
        new_time_embed_dim = time_embed_dim
        if self.input_top_region_index:
            self.top_region_index_layer = nn.Sequential(
                nn.Linear(4, time_embed_dim),
                nn.SiLU(),
                nn.Linear(time_embed_dim, time_embed_dim),
            )
            new_time_embed_dim += time_embed_dim
        if self.input_bottom_region_index:
            self.bottom_region_index_layer = nn.Sequential(
                nn.Linear(4, time_embed_dim),
                nn.SiLU(),
                nn.Linear(time_embed_dim, time_embed_dim),
            )
            new_time_embed_dim += time_embed_dim
        if self.input_spacing:
            self.spacing_layer = nn.Sequential(
                nn.Linear(3, time_embed_dim),
                nn.SiLU(),
                nn.Linear(time_embed_dim, time_embed_dim),
            )
            new_time_embed_dim += time_embed_dim

        self.time_embed = nn.Sequential(
            nn.Linear(num_channels[0], time_embed_dim),
            nn.SiLU(),
            nn.Linear(time_embed_dim, new_time_embed_dim),
        )

    def forward(
        self,
        x: torch.Tensor,
        timesteps: torch.Tensor,
        context: torch.Tensor | None = None,
        class_labels: torch.Tensor | None = None,
        down_block_additional_residuals: tuple[torch.Tensor] | None = None,
        mid_block_additional_residual: torch.Tensor | None = None,
        top_region_index_tensor: torch.Tensor | None = None,
        bottom_region_index_tensor: torch.Tensor | None = None,
        spacing_tensor: torch.Tensor | None = None,
    ) -> torch.Tensor:
        t_emb = get_timestep_embedding(timesteps, self.block_out_channels[0]).to(dtype=x.dtype)
        emb = self.time_embed(t_emb)

        if self.num_class_embeds is not None and class_labels is not None:
            class_emb = self.class_embedding(class_labels).to(dtype=x.dtype)
            emb = emb + class_emb

        if self.input_top_region_index and top_region_index_tensor is not None:
            emb = torch.cat((emb, self.top_region_index_layer(top_region_index_tensor)), dim=1)
        if self.input_bottom_region_index and bottom_region_index_tensor is not None:
            emb = torch.cat((emb, self.bottom_region_index_layer(bottom_region_index_tensor)), dim=1)
        if self.input_spacing and spacing_tensor is not None:
            emb = torch.cat((emb, self.spacing_layer(spacing_tensor)), dim=1)

        h = self.conv_in(x)
        down_block_res_samples = [h]
        for downsample_block in self.down_blocks:
            h, res_samples = downsample_block(hidden_states=h, temb=emb, context=context)
            down_block_res_samples.extend(res_samples)

        if down_block_additional_residuals is not None:
            down_block_res_samples = [res + add_res for res, add_res in zip(down_block_res_samples, down_block_additional_residuals)]

        h = self.middle_block(hidden_states=h, temb=emb, context=context)
        if mid_block_additional_residual is not None:
            h = h + mid_block_additional_residual

        for upsample_block in self.up_blocks:
            res_samples = down_block_res_samples[-len(upsample_block.resnets):]
            down_block_res_samples = down_block_res_samples[:-len(upsample_block.resnets)]
            h = upsample_block(hidden_states=h, res_hidden_states_list=res_samples, temb=emb, context=context)

        h = self.out(h)
        return h