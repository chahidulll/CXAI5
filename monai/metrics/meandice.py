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

from typing import Callable, Optional, Union

import torch

from monai.metrics.seg_metric_utils import *


class DiceMetric:
    """
    Compute average Dice loss between two tensors. It can support both multi-classes and multi-labels tasks.
    Input logits `y_pred` (BNHW[D] where N is number of classes) is compared with ground truth `y` (BNHW[D]).
    Axis N of `y_preds` is expected to have logit predictions for each class rather than being image channels,
    while the same axis of `y` can be 1 or N (one-hot format). The `include_background` class attribute can be
    set to False for an instance of DiceLoss to exclude the first category (channel index 0) which is by
    convention assumed to be background. If the non-background segmentations are small compared to the total
    image size they can get overwhelmed by the signal from the background so excluding it in such cases helps
    convergence.

    Args:
        include_background: whether to skip Dice computation on the first channel of
            the predicted output. Defaults to True.
        to_onehot_y: whether to convert `y` into the one-hot format. Defaults to False.
        mutually_exclusive: if True, `y_pred` will be converted into a binary matrix using
            a combination of argmax and to_onehot.  Defaults to False.
        sigmoid: whether to add sigmoid function to y_pred before computation. Defaults to False.
        other_act: callable function to replace `sigmoid` as activation layer if needed, Defaults to ``None``.
            for example: `other_act = torch.tanh`.
        logit_thresh: the threshold value used to convert (for example, after sigmoid if `sigmoid=True`)
            `y_pred` into a binary matrix. Defaults to 0.5.
        reduction: {``"none"``, ``"mean"``, ``"sum"``, ``"mean_batch"``, ``"sum_batch"``,
            ``"mean_channel"``, ``"sum_channel"``}
            Define the mode to reduce computation result of 1 batch data. Defaults to ``"mean"``.

    """

    def __init__(
        self,
        include_background: bool = True,
        to_onehot_y: bool = False,
        mutually_exclusive: bool = False,
        sigmoid: bool = False,
        other_act: Optional[Callable] = None,
        logit_thresh: float = 0.5,
        reduction: Union[MetricReduction, str] = MetricReduction.MEAN,
    ) -> None:
        super().__init__()
        self.include_background = include_background
        self.to_onehot_y = to_onehot_y
        self.mutually_exclusive = mutually_exclusive
        self.sigmoid = sigmoid
        self.other_act = other_act
        self.logit_thresh = logit_thresh
        self.reduction = reduction

        self.not_nans: Optional[torch.Tensor] = None  # keep track for valid elements in the batch

    def __call__(self, y_pred: torch.Tensor, y: torch.Tensor):
        """
        Args:
            y_pred: input data to compute, typical segmentation model output.
                it must be one-hot format and first dim is batch.
            y: ground truth to compute mean dice metric, the first dim is batch.

        """

        # compute dice (BxC) for each channel for each batch
        f = compute_meandice(
            y_pred=y_pred,
            y=y,
            include_background=self.include_background,
            to_onehot_y=self.to_onehot_y,
            mutually_exclusive=self.mutually_exclusive,
            sigmoid=self.sigmoid,
            other_act=self.other_act,
            logit_thresh=self.logit_thresh,
        )

        # do metric reduction
        f, not_nans = do_metric_reduction(f, self.reduction)

        # save not_nans since we may need it later to know how many elements were valid
        self.not_nans = not_nans
        return f


def compute_meandice(
    y_pred: torch.Tensor,
    y: torch.Tensor,
    include_background: bool = True,
    to_onehot_y: bool = False,
    mutually_exclusive: bool = False,
    sigmoid: bool = False,
    other_act: Optional[Callable] = None,
    logit_thresh: float = 0.5,
) -> torch.Tensor:
    """Computes Dice score metric from full size Tensor and collects average.

    Args:
        y_pred: input data to compute, typical segmentation model output.
            it must be one-hot format and first dim is batch, example shape: [16, 3, 32, 32].
        y: ground truth to compute mean dice metric, the first dim is batch.
            example shape: [16, 1, 32, 32] will be converted into [16, 3, 32, 32].
            alternative shape: [16, 3, 32, 32] and set `to_onehot_y=False` to use 3-class labels directly.
        include_background: whether to skip Dice computation on the first channel of
            the predicted output. Defaults to True.
        to_onehot_y: whether to convert `y` into the one-hot format. Defaults to False.
        mutually_exclusive: if True, `y_pred` will be converted into a binary matrix using
            a combination of argmax and to_onehot.  Defaults to False.
        sigmoid: whether to add sigmoid function to y_pred before computation. Defaults to False.
        other_act: callable function to replace `sigmoid` as activation layer if needed, Defaults to ``None``.
            for example: `other_act = torch.tanh`.
        logit_thresh: the threshold value used to convert (for example, after sigmoid if `sigmoid=True`)
            `y_pred` into a binary matrix. Defaults to 0.5.

    Raises:
        ValueError: When ``sigmoid=True`` and ``other_act is not None``. Incompatible values.
        TypeError: When ``other_act`` is not an ``Optional[Callable]``.
        ValueError: When ``sigmoid=True`` and ``mutually_exclusive=True``. Incompatible values.

    Returns:
        Dice scores per batch and per class, (shape [batch_size, n_classes]).

    Note:
        This method provides two options to convert `y_pred` into a binary matrix
            (1) when `mutually_exclusive` is True, it uses a combination of ``argmax`` and ``to_onehot``,
            (2) when `mutually_exclusive` is False, it uses a threshold ``logit_thresh``
                (optionally with a ``sigmoid`` function before thresholding).

    """

    bin_mode = "mutually_exclusive" if mutually_exclusive else "threshold"
    if sigmoid and other_act is not None:
        raise ValueError("Incompatible values: sigmoid=True and other_act is not None.")
    if other_act is not None:
        if not callable(other_act):
            raise TypeError(f"other_act must be None or callable but is {type(other_act).__name__}.")
    if sigmoid and mutually_exclusive:
        raise ValueError("Incompatible values: sigmoid=True and mutually_exclusive=True.")

    activation = "sigmoid" if sigmoid else other_act

    y_pred, y = preprocess_input(
        y_pred=y_pred,
        y=y,
        to_onehot_y=to_onehot_y,
        activation=activation,
        bin_mode=bin_mode,
        bin_threshold=logit_thresh,
        include_background=include_background,
    )

    # reducing only spatial dimensions (not batch nor channels)
    n_len = len(y_pred.shape)
    reduce_axis = list(range(2, n_len))
    intersection = torch.sum(y * y_pred, dim=reduce_axis)

    y_o = torch.sum(y, reduce_axis)
    y_pred_o = torch.sum(y_pred, dim=reduce_axis)
    denominator = y_o + y_pred_o

    f = torch.where(y_o > 0, (2.0 * intersection) / denominator, torch.tensor(float("nan"), device=y_o.device))
    return f  # returns array of Dice with shape: [batch, n_classes]
