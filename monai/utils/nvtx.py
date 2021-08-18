# Copyright 2020 - 2021 MONAI Consortium
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Decorators for NVIDIA Tools Extension to profile MONAI components
"""

from functools import wraps
from typing import TYPE_CHECKING, Callable, Optional, Tuple, Union

import torch.nn as nn

from monai.utils import optional_import

_nvtx, _ = optional_import("torch._C._nvtx", descriptor="NVTX is not installed. Are you sure you have a CUDA build?")

__all__ = ["Range"]


class Range:
    """
    Enclose a callable (e.g. Transforms) or Modules (e.g. Network, Loss, etc.) with NVTX (NVIDIA Tools Extension) range
    to enable profiling of those components using some profilers like NVIDIA Nsight Systems.

    Args:
        name: the name to be associated to the range
        method: the method to be wrapped by NVTX range. If not provided (None), the method will be inferred
            based on the object's class for Callable objects (like Transforms), nn.Module objects
            (like Networks, Losses, etc.), and Dataloaders. Method resolve order is:
            - __call__()
            - forward()
            - __next__()

    """

    no_name_counter = 0

    def __init__(self, name: str = None, method: str = None) -> None:
        self.name = name
        self.method = method

    def __call__(self, obj: Union[Callable, nn.Module]):
        # Define the name to be associated to the range if not provided
        if self.name is None:
            self.name = type(obj).__name__

        # Define the method to be wrapped if not provided
        if self.method is None:
            method_list = [
                "__call__",  # Callable
                "forward",  # nn.Module
                "__next__",  # Dataloader
            ]
            for method in method_list:
                if hasattr(obj, method):
                    self.method = method
                    break
            if self.method is None:
                raise ValueError(
                    f"The method to be wrapped for this object [{type(obj)}] is not recognized."
                    "The name of the method should be provied or it should have one of following methods:"
                    "{method_list}"
                )

        # Get the method to be wrapped
        _temp_func = getattr(obj, self.method)

        # Wrap the method with NVTX range (range push/pop)
        @wraps(_temp_func)
        def range_wrapper(*args, **kwargs):
            _nvtx.rangePushA(self.name)
            output = _temp_func(*args, **kwargs)
            _nvtx.rangePop()
            return output

        # Replace the method with the wrapped version
        setattr(obj, self.method, range_wrapper)

        return obj

    def __enter__(self):
        if self.name is None:
            self.name = "Range_" + str(self.no_name_counter)
            self.no_name_counter += 1

        _nvtx.rangePushA(self.name)

    def __exit__(self, type, value, traceback):
        _nvtx.rangePop()
