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

import warnings
from typing import TYPE_CHECKING, Callable, Optional, Sequence, Union

from torch.utils.data import DataLoader as TorchDataLoader

from monai.data import BatchInverseTransform
from monai.data.utils import no_collation
from monai.engines.utils import CommonKeys, IterationEvents
from monai.transforms import InvertibleTransform, ToTensor, allow_missing_keys_mode, convert_inverse_interp_mode
from monai.utils import InverseKeys, ensure_tuple, ensure_tuple_rep, exact_version, optional_import

Events, _ = optional_import("ignite.engine", "0.4.4", exact_version, "Events")
if TYPE_CHECKING:
    from ignite.engine import Engine
else:
    Engine, _ = optional_import("ignite.engine", "0.4.4", exact_version, "Engine")


class TransformInverter:
    """
    Ignite handler to automatically invert all the pre-transforms that support `inverse`.
    It takes `engine.state.output` as the input data and uses the transforms infomation from `engine.state.batch`.

    """

    def __init__(
        self,
        transform: InvertibleTransform,
        loader: TorchDataLoader,
        output_keys: Union[str, Sequence[str]] = CommonKeys.PRED,
        batch_keys: Union[str, Sequence[str]] = CommonKeys.IMAGE,
        collate_fn: Optional[Callable] = no_collation,
        postfix: str = "inverted",
        nearest_interp: Union[bool, Sequence[bool]] = True,
    ) -> None:
        """
        Args:
            transform: a callable data transform on input data.
            loader: data loader used to generate the batch of data.
            collate_fn: how to collate data after inverse transformations.
                default won't do any collation, so the output will be a list of size batch size.
            output_keys: the key of expected data in `ignite.engine.output`, invert transforms on it.
                it also can be a list of keys, will invert transform for each of them. default to "pred".
            batch_keys: the key of input data in `ignite.engine.batch`. will get the applied transforms
                for this input data, then invert them for the expected data with `output_keys`.
                it also can be a list of keys, each matches to the `output_keys` data. default to "image".
            postfix: will save the inverted result into `ignite.engine.output` with key `{ouput_key}_{postfix}`.
            nearest_interp: whether to use `nearest` interpolation mode when inverting spatial transforms,
                default to `True`. if `False`, use the same interpolation mode as the original transform.
                it also can be a list of bool, each matches to the `output_keys` data.

        """
        self.transform = transform
        self.inverter = BatchInverseTransform(transform=transform, loader=loader, collate_fn=collate_fn)
        self.output_keys = ensure_tuple(output_keys)
        self.batch_keys = ensure_tuple_rep(batch_keys, len(self.output_keys))
        self.postfix = postfix
        self.nearest_interp = ensure_tuple_rep(nearest_interp, len(self.output_keys))
        self._totensor = ToTensor()

    def attach(self, engine: Engine) -> None:
        """
        Args:
            engine: Ignite Engine, it can be a trainer, validator or evaluator.
        """
        engine.add_event_handler(IterationEvents.MODEL_COMPLETED, self)

    def __call__(self, engine: Engine) -> None:
        """
        Args:
            engine: Ignite Engine, it can be a trainer, validator or evaluator.
        """
        for output_key, batch_key, nearest_interp in zip(self.output_keys, self.batch_keys, self.nearest_interp):
            transform_key = batch_key + InverseKeys.KEY_SUFFIX
            if transform_key not in engine.state.batch:
                warnings.warn(f"all the pre-transforms on `{batch_key}` are not InvertibleTransform.")
                continue

            transform_info = engine.state.batch[transform_key]
            if nearest_interp:
                convert_inverse_interp_mode(trans_info=transform_info, mode="nearest", align_corners=None)

            segs_dict = {
                batch_key: engine.state.output[output_key].detach().cpu(),
                transform_key: transform_info,
            }

            with allow_missing_keys_mode(self.transform):  # type: ignore
                inverted_key = f"{output_key}_{self.postfix}"
                engine.state.output[inverted_key] = [self._totensor(i[batch_key]) for i in self.inverter(segs_dict)]
