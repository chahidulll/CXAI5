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

from monai.transforms.croppad.array import CenterSpatialCrop
from monai.utils.misc import ensure_tuple
from typing import Any, Callable, Dict, Hashable, Optional, Tuple

import numpy as np
from torch.utils.data.dataloader import DataLoader as TorchDataLoader

from monai.data.dataloader import DataLoader
from monai.data.dataset import Dataset
from monai.data.utils import decollate_batch, pad_list_data_collate
from monai.transforms.inverse_transform import InvertibleTransform
from monai.utils import first

__all__ = ["BatchInverseTransform"]


class _BatchInverseDataset(Dataset):
    def __init__(
        self,
        data: Dict[str, Any],
        transform: InvertibleTransform,
        keys: Optional[Tuple[Hashable, ...]],
        pad_collation_used: bool,
    ) -> None:
        self.data = decollate_batch(data)
        self.invertible_transform = transform
        self.keys = ensure_tuple(keys) if keys else None
        self.pad_collation_used = pad_collation_used

    def __getitem__(self, index: int) -> Dict[Hashable, np.ndarray]:
        data = dict(self.data[index])
        # If pad collation was used, then we need to undo this first
        if self.pad_collation_used:
            keys = self.keys or [key for key in data.keys() if str(key) + "_transforms" in data.keys()]
            for key in keys:
                transform_key = str(key) + "_transforms"
                transform = data[transform_key].pop()
                if transform["class"] != "SpatialPadd":
                    raise RuntimeError("Expected most recent transform to have been SpatialPadd because " +
                                       "pad_list_data_collate was used. Instead, found " + transform["class"])
                data[key] = CenterSpatialCrop(transform["orig_size"])(data[key])

        return self.invertible_transform.inverse(data, self.keys)


class BatchInverseTransform:
    """something"""

    def __init__(
        self, transform: InvertibleTransform, loader: TorchDataLoader, collate_fn: Optional[Callable] = None
    ) -> None:
        """
        Args:
            transform: a callable data transform on input data.
            loader: data loader used to generate the batch of data.
            collate_fn: how to collate data after inverse transformations. Default will use the DataLoader's default
                collation method. If returning images of different sizes, this will likely create an error (since the
                collation will concatenate arrays, requiring them to be the same size). In this case, using
                `collate_fn=lambda x: x` might solve the problem.
        """
        self.transform = transform
        self.batch_size = loader.batch_size
        self.num_workers = loader.num_workers
        self.collate_fn = collate_fn
        self.pad_collation_used = loader.collate_fn == pad_list_data_collate

    def __call__(self, data: Dict[str, Any], keys: Optional[Tuple[Hashable, ...]] = None) -> Dict[Hashable, np.ndarray]:

        inv_ds = _BatchInverseDataset(data, self.transform, keys, self.pad_collation_used)
        inv_loader = DataLoader(
            inv_ds, batch_size=self.batch_size, num_workers=self.num_workers, collate_fn=self.collate_fn
        )
        try:
            # Only need to return first as only 1 batch of data
            return first(inv_loader)  # type: ignore
        except RuntimeError as re:
            re_str = str(re)
            if "stack expects each tensor to be equal size" in re_str:
                re_str += "\nMONAI hint: try creating `BatchInverseTransform` with `collate_fn=lambda x: x`."
            raise RuntimeError(re_str)
