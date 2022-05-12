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

from copy import deepcopy
from typing import Sequence, Union

import numpy as np
import torch

from monai.config.type_definitions import NdarrayOrTensor
from monai.utils.module import look_up_option
from monai.utils.type_conversion import convert_data_type, convert_to_dst_type, convert_to_numpy, convert_to_tensor

# We support several box modes, i.e., representation of a bounding box
CORNER_CORNER_MODE = ["xyxy", "xyzxyz"]  # [xmin, ymin, xmax, ymax] and [xmin, ymin, zmin, xmax, ymax, zmax]
XXYYZZ_MODE = ["xxyy", "xxyyzz"]  # [xmin, xmax, ymin, ymax] and [xmin, xmax, ymin, ymax, zmin, zmax]
CORNER_SIZE_MODE = ["xywh", "xyzwhd"]  # [xmin, ymin, xsize, ysize] and [xmin, ymin, zmin, xsize, ysize, zsize]
CENTER_SIZE_MODE = [
    "ccwh",
    "cccwhd",
]  # [xcenter, ycenter, xsize, ysize] and [xcenter, ycenter, zcenter, xsize, ysize, zsize]

STANDARD_MODE = CORNER_CORNER_MODE  # standard box modes supported by all the box util functions
SUPPORTED_MODE = (
    CORNER_CORNER_MODE + XXYYZZ_MODE + CORNER_SIZE_MODE + CENTER_SIZE_MODE
)  # supported box modes for some box util functions

# TO_REMOVE = 0 if in 'xxyy','xxyyzz' mode, the bottom-right corner is not included in the box,
#      i.e., when xmin=1, xmax=2, we have w = 1
# TO_REMOVE = 1  if in 'xxyy','xxyyzz' mode, the bottom-right corner is included in the box,
#       i.e., when xmin=1, xmax=2, we have w = 2
# Currently only TO_REMOVE = 0 has been tested. Please keep TO_REMOVE = 0
TO_REMOVE = 0  # xmax-xmin = w -TO_REMOVE.


def convert_to_list(in_sequence: Union[Sequence, torch.Tensor, np.ndarray]) -> list:
    """
    Convert a torch.Tensor, or np array input to list
    Args:
        in_sequence: Sequence or torch.Tensor or np.ndarray
    Returns:
        a list

    """
    return in_sequence.tolist() if isinstance(in_sequence, (torch.Tensor, np.ndarray)) else list(in_sequence)


def get_dimension(
    bbox: Union[torch.Tensor, np.ndarray, None] = None,
    image_size: Union[Sequence[int], torch.Tensor, np.ndarray, None] = None,
    mode: Union[str, None] = None,
) -> int:
    """
    Get spatial dimension for the giving setting.
    Missing input is allowed. But at least one of the input value should be given.
    It raises ValueError if the dimensions of multiple inputs do not match with each other.
    Args:
        bbox: bounding box, Nx4 or Nx6 torch tensor or ndarray
        image_size: Length of 2 or 3. Data format is list, or np.ndarray, or tensor of int
        mode: box mode, choose from SUPPORTED_MODE. If mode is not given, this func will assume mode is STANDARD_MODE
    Returns:
        spatial_dimension: 2 or 3

    Example:
        bbox = torch.ones(10,6)
        get_dimension(bbox, mode="xyxy") will raise ValueError
        get_dimension(bbox, mode="xyzxyz") will return 3
        get_dimension(bbox, mode="xyzxyz", image_size=[100,200,200]) will return 3
        get_dimension(mode="xyzxyz") will return 3
    """
    spatial_dims_set = set()
    if image_size is not None:
        spatial_dims_set.add(len(image_size))
    if mode is not None:
        spatial_dims_set.add(int(len(mode) / 2))
    if bbox is not None:
        spatial_dims_set.add(int(bbox.shape[1] / 2))
    spatial_dims_list = list(spatial_dims_set)
    if len(spatial_dims_list) == 0:
        raise ValueError("At least one of bbox, image_size, and mode needs to be non-empty.")
    elif len(spatial_dims_list) == 1:
        spatial_dims = int(spatial_dims_list[0])
        spatial_dims = look_up_option(spatial_dims, supported=[2, 3])
        return int(spatial_dims)
    else:
        raise ValueError("The dimension of bbox, image_size, mode should match with each other.")


def get_standard_mode(spatial_dims: int) -> str:
    """
    Get the mode name for the given spatial dimension
    Args:
        spatial_dims: 2 or 3
    Returns:
        mode name, choose from STANDARD_MODE

    Example:
        get_standard_mode(spatial_dims = 2)

    """
    if spatial_dims == 2:
        return STANDARD_MODE[0]
    elif spatial_dims == 3:
        return STANDARD_MODE[1]
    else:
        raise ValueError(f"Images should have 2 or 3 dimensions, got {spatial_dims}")


def check_box_mode(bbox: NdarrayOrTensor, mode: Union[str, None] = None):
    """
    This function checks whether the bbox is valid.
    It ensures the box size is non-negative.
    Args:
        bbox: bounding box, Nx4 or Nx6 torch tensor or ndarray
        mode: box mode, choose from SUPPORTED_MODE. If mode is not given, this func will assume mode is STANDARD_MODE
    Returns:
        raise Error is mode is not supported
        return False if box has negative size
        return True if no issue found

    Example:
        bbox = torch.ones(10,6)
        check_box_mode(bbox, mode="cccwhd")
    """
    if mode is None:
        mode = get_standard_mode(int(bbox.shape[1] / 2))
    mode = look_up_option(mode, supported=SUPPORTED_MODE)
    spatial_dims = get_dimension(bbox=bbox, mode=mode)

    # we need box size to be non-negative
    if mode in ["ccwh", "cccwhd", "xywh", "xyzwhd"]:
        box_error = bbox[:, spatial_dims] < 0
        for axis in range(1, spatial_dims):
            box_error = box_error | (bbox[:, spatial_dims + axis] < 0)
    elif mode in ["xxyy", "xxyyzz"]:
        box_error = bbox[:, 1] < bbox[:, 0]
        for axis in range(1, spatial_dims):
            box_error = box_error | (bbox[:, 2 * axis + 1] < bbox[:, 2 * axis])
    elif mode in ["xyxy", "xyzxyz"]:
        box_error = bbox[:, spatial_dims] < bbox[:, 0]
        for axis in range(1, spatial_dims):
            box_error = box_error | (bbox[:, spatial_dims + axis] < bbox[:, axis])
    else:
        raise ValueError(f"Box mode {mode} not in {SUPPORTED_MODE}.")

    if box_error.sum() > 0:
        return False

    return True


def split_into_corners(bbox: NdarrayOrTensor, mode: Union[str, None] = None):
    """
    This internal function outputs the corner coordinates of the bbox
    Args:
        bbox: bounding box, Nx4 or Nx6 torch tensor or ndarray
        mode: box mode, choose from SUPPORTED_MODE. If mode is not given, this func will assume mode is STANDARD_MODE
    Returns:
        if 2D image, outputs (xmin, xmax, ymin, ymax)
        if 3D images, outputs (xmin, xmax, ymin, ymax, zmin, zmax)
        xmin for example, is a Nx1 tensor

    Example:
        bbox = torch.ones(10,6)
        split_into_corners(bbox, mode="cccwhd")
    """
    # convert numpy to tensor if needed
    bbox_t, *_ = convert_data_type(bbox, torch.Tensor)

    # convert to float32 when computing torch.clamp, which does not support float16
    box_dtype = bbox_t.dtype
    compute_dtype = torch.float32

    if mode is None:
        mode = get_standard_mode(int(bbox_t.shape[1] / 2))
    mode = look_up_option(mode, supported=SUPPORTED_MODE)

    # split tensor into corners
    if mode in ["xxyy", "xxyyzz"]:
        split_result = bbox_t.split(1, dim=-1)
    elif mode == "xyzxyz":
        xmin, ymin, zmin, xmax, ymax, zmax = bbox_t.split(1, dim=-1)
        split_result = (xmin, xmax, ymin, ymax, zmin, zmax)
    elif mode == "xyxy":
        xmin, ymin, xmax, ymax = bbox_t.split(1, dim=-1)
        split_result = (xmin, xmax, ymin, ymax)
    elif mode == "xyzwhd":
        xmin, ymin, zmin, w, h, d = bbox_t.split(1, dim=-1)
        split_result = (
            xmin,
            xmin + (w - TO_REMOVE).to(dtype=compute_dtype).clamp(min=0).to(dtype=box_dtype),
            ymin,
            ymin + (h - TO_REMOVE).to(dtype=compute_dtype).clamp(min=0).to(dtype=box_dtype),
            zmin,
            zmin + (d - TO_REMOVE).to(dtype=compute_dtype).clamp(min=0).to(dtype=box_dtype),
        )
    elif mode == "xywh":
        xmin, ymin, w, h = bbox_t.split(1, dim=-1)
        split_result = (xmin, xmin + (w - TO_REMOVE).clamp(min=0), ymin, ymin + (h - TO_REMOVE).clamp(min=0))
    elif mode == "cccwhd":
        xc, yc, zc, w, h, d = bbox_t.split(1, dim=-1)
        split_result = (
            xc - ((w - TO_REMOVE) / 2.0).to(dtype=compute_dtype).clamp(min=0).to(dtype=box_dtype),
            xc + ((w - TO_REMOVE) / 2.0).to(dtype=compute_dtype).clamp(min=0).to(dtype=box_dtype),
            yc - ((h - TO_REMOVE) / 2.0).to(dtype=compute_dtype).clamp(min=0).to(dtype=box_dtype),
            yc + ((h - TO_REMOVE) / 2.0).to(dtype=compute_dtype).clamp(min=0).to(dtype=box_dtype),
            zc - ((d - TO_REMOVE) / 2.0).to(dtype=compute_dtype).clamp(min=0).to(dtype=box_dtype),
            zc + ((d - TO_REMOVE) / 2.0).to(dtype=compute_dtype).clamp(min=0).to(dtype=box_dtype),
        )
    elif mode == "ccwh":
        xc, yc, w, h = bbox_t.split(1, dim=-1)
        split_result = (
            xc - ((w - TO_REMOVE) / 2.0).to(dtype=compute_dtype).clamp(min=0).to(dtype=box_dtype),
            xc + ((w - TO_REMOVE) / 2.0).to(dtype=compute_dtype).clamp(min=0).to(dtype=box_dtype),
            yc - ((h - TO_REMOVE) / 2.0).to(dtype=compute_dtype).clamp(min=0).to(dtype=box_dtype),
            yc + ((h - TO_REMOVE) / 2.0).to(dtype=compute_dtype).clamp(min=0).to(dtype=box_dtype),
        )
    else:
        raise RuntimeError("Should not be here")

    # convert tensor back to numpy if needed
    split_result, *_ = convert_to_dst_type(src=split_result, dst=bbox)
    return split_result


def box_convert_mode(
    bbox: NdarrayOrTensor, src_mode: Union[str, None] = None, dst_mode: Union[str, None] = None
) -> NdarrayOrTensor:
    """
    This function converts the bbox in src_mode to the dst_mode
    Args:
        bbox: source bounding box, Nx4 or Nx6 torch tensor or ndarray
        src_mode: source box mode, choose from SUPPORTED_MODE. If mode is not given, this func will assume mode is STANDARD_MODE
        dst_mode: target box mode, choose from SUPPORTED_MODE. If mode is not given, this func will assume mode is STANDARD_MODE
    Returns:
        bbox_dst: bounding box with target mode, does not share memory with original bbox

    Example:
        bbox = torch.ones(10,6)
        box_convert_mode(bbox=bbox, src_mode="xyzxyz", dst_mode="cccwhd")
    """

    if not check_box_mode(bbox, src_mode):
        raise ValueError("Given bbox has invalid values. The box size must be non-negative.")

    # convert numpy to tensor if needed
    bbox_t, *_ = convert_data_type(bbox, torch.Tensor)

    # check whether the bbox_t and the new mode is valid
    if src_mode is None:
        src_mode = get_standard_mode(int(bbox_t.shape[1] / 2))
    if dst_mode is None:
        dst_mode = get_standard_mode(int(bbox_t.shape[1] / 2))
    src_mode = look_up_option(src_mode, supported=SUPPORTED_MODE)
    dst_mode = look_up_option(dst_mode, supported=SUPPORTED_MODE)

    spatial_dims = get_dimension(bbox=bbox_t, mode=src_mode)
    if len(src_mode) != len(dst_mode):
        raise ValueError("The dimension of the new mode should have the same spatial dimension as the old mode.")

    # if mode not changed, return original box
    if src_mode == dst_mode:
        bbox_t_dst = deepcopy(bbox_t)
    # convert mode for bbox_t
    elif dst_mode in ["xxyy", "xxyyzz"]:
        corners = split_into_corners(bbox_t, src_mode)
        bbox_t_dst = torch.cat(corners, dim=-1)
    else:
        if spatial_dims == 3:
            xmin, xmax, ymin, ymax, zmin, zmax = split_into_corners(bbox_t, src_mode)
            if dst_mode == "xyzxyz":
                bbox_t_dst = torch.cat((xmin, ymin, zmin, xmax, ymax, zmax), dim=-1)
            elif dst_mode == "xyzwhd":
                bbox_t_dst = torch.cat(
                    (xmin, ymin, zmin, xmax - xmin + TO_REMOVE, ymax - ymin + TO_REMOVE, zmax - zmin + TO_REMOVE),
                    dim=-1,
                )
            elif dst_mode == "cccwhd":
                bbox_t_dst = torch.cat(
                    (
                        (xmin + xmax + TO_REMOVE) / 2.0,
                        (ymin + ymax + TO_REMOVE) / 2.0,
                        (zmin + zmax + TO_REMOVE) / 2.0,
                        xmax - xmin + TO_REMOVE,
                        ymax - ymin + TO_REMOVE,
                        zmax - zmin + TO_REMOVE,
                    ),
                    dim=-1,
                )
            else:
                raise ValueError("We support only bbox mode in " + str(SUPPORTED_MODE) + f", got {dst_mode}")
        elif spatial_dims == 2:
            xmin, xmax, ymin, ymax = split_into_corners(bbox_t.clone(), src_mode)
            if dst_mode == "xyxy":
                bbox_t_dst = torch.cat((xmin, ymin, xmax, ymax), dim=-1)
            elif dst_mode == "xywh":
                bbox_t_dst = torch.cat((xmin, ymin, xmax - xmin + TO_REMOVE, ymax - ymin + TO_REMOVE), dim=-1)
            elif dst_mode == "ccwh":
                bbox_t_dst = torch.cat(
                    (
                        (xmin + xmax + TO_REMOVE) / 2.0,
                        (ymin + ymax + TO_REMOVE) / 2.0,
                        xmax - xmin + TO_REMOVE,
                        ymax - ymin + TO_REMOVE,
                    ),
                    dim=-1,
                )
            else:
                raise ValueError("We support only bbox mode in " + str(SUPPORTED_MODE) + f", got {dst_mode}")
        else:
            raise ValueError(f"Images should have 2 or 3 dimensions, got {spatial_dims}")

    # convert tensor back to numpy if needed
    bbox_dst, *_ = convert_to_dst_type(src=bbox_t_dst, dst=bbox)

    return bbox_dst


def box_convert_standard_mode(bbox: NdarrayOrTensor, mode: Union[str, None] = None) -> NdarrayOrTensor:
    """
    Convert given bbox to standard mode
    Args:
        bbox: source bounding box, Nx4 or Nx6 torch tensor or ndarray
        mode: source box mode, choose from SUPPORTED_MODE. If mode is not given, this func will assume mode is STANDARD_MODE
    Returns:
        bbox_standard: bounding box with standard mode, does not share memory with original bbox

    Example:
        bbox = torch.ones(10,6)
        box_convert_standard_mode(bbox=bbox, mode="xxyyzz")
    """
    if mode is None:
        mode = get_standard_mode(int(bbox.shape[1] / 2))
    mode = look_up_option(mode, supported=SUPPORTED_MODE)
    spatial_dims = get_dimension(bbox=bbox, mode=mode)
    mode_standard = get_standard_mode(spatial_dims)
    return box_convert_mode(bbox=bbox, src_mode=mode, dst_mode=mode_standard)
