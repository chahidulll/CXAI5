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
"""
A collection of dictionary-based wrappers around the "vanilla" transforms for intensity adjustment
defined in :py:class:`monai.transforms.intensity.array`.

Class names are ended with 'd' to denote dictionary-based transforms.
"""

from typing import Any, Optional, Sequence, Tuple, Union
from collections.abc import Iterable
import numpy as np

from monai.config import KeysCollection
from monai.transforms.compose import MapTransform, Randomizable
from monai.transforms.intensity.array import (
    AdjustContrast,
    GaussianSmooth,
    GaussianSharpen,
    MaskIntensity,
    NormalizeIntensity,
    ScaleIntensity,
    ScaleIntensityRange,
    ScaleIntensityRangePercentiles,
    ShiftIntensity,
    ThresholdIntensity,
)
from monai.utils import ensure_tuple_size


class RandGaussianNoised(Randomizable, MapTransform):
    """
    Dictionary-based version :py:class:`monai.transforms.RandGaussianNoise`.
    Add Gaussian noise to image. This transform assumes all the expected fields have same shape.

    Args:
        keys: keys of the corresponding items to be transformed.
            See also: :py:class:`monai.transforms.compose.MapTransform`
        prob: Probability to add Gaussian noise.
        mean: Mean or “centre” of the distribution.
        std: Standard deviation (spread) of distribution.
    """

    def __init__(
        self, keys: KeysCollection, prob: float = 0.1, mean: Union[Sequence[float], float] = 0.0, std: float = 0.1
    ) -> None:
        super().__init__(keys)
        self.prob = prob
        self.mean = mean
        self.std = std
        self._do_transform = False
        self._noise = None

    def randomize(self, im_shape: Sequence[int]) -> None:
        self._do_transform = self.R.random() < self.prob
        self._noise = self.R.normal(self.mean, self.R.uniform(0, self.std), size=im_shape)

    def __call__(self, data):
        d = dict(data)

        image_shape = d[self.keys[0]].shape  # image shape from the first data key
        self.randomize(image_shape)
        if not self._do_transform:
            return d
        for key in self.keys:
            d[key] = d[key] + self._noise.astype(d[key].dtype)
        return d


class ShiftIntensityd(MapTransform):
    """
    Dictionary-based wrapper of :py:class:`monai.transforms.ShiftIntensity`.
    """

    def __init__(self, keys: KeysCollection, offset: float) -> None:
        """
        Args:
            keys: keys of the corresponding items to be transformed.
                See also: :py:class:`monai.transforms.compose.MapTransform`
            offset: offset value to shift the intensity of image.
        """
        super().__init__(keys)
        self.shifter = ShiftIntensity(offset)

    def __call__(self, data):
        d = dict(data)
        for key in self.keys:
            d[key] = self.shifter(d[key])
        return d


class RandShiftIntensityd(Randomizable, MapTransform):
    """
    Dictionary-based version :py:class:`monai.transforms.RandShiftIntensity`.
    """

    def __init__(self, keys: KeysCollection, offsets: Union[Tuple[float, float], float], prob: float = 0.1) -> None:
        """
        Args:
            keys: keys of the corresponding items to be transformed.
                See also: :py:class:`monai.transforms.compose.MapTransform`
            offsets: offset range to randomly shift.
                if single number, offset value is picked from (-offsets, offsets).
            prob: probability of rotating.
                (Default 0.1, with 10% probability it returns a rotated array.)
        """
        super().__init__(keys)

        if isinstance(offsets, (int, float)):
            self.offsets = (min(-offsets, offsets), max(-offsets, offsets))
        else:
            assert len(offsets) == 2, "offsets should be a number or pair of numbers."
            self.offsets = (min(offsets), max(offsets))

        self.prob = prob
        self._do_transform = False

    def randomize(self, data: Optional[Any] = None) -> None:
        self._offset = self.R.uniform(low=self.offsets[0], high=self.offsets[1])
        self._do_transform = self.R.random() < self.prob

    def __call__(self, data):
        d = dict(data)
        self.randomize()
        if not self._do_transform:
            return d
        shifter = ShiftIntensity(self._offset)
        for key in self.keys:
            d[key] = shifter(d[key])
        return d


class ScaleIntensityd(MapTransform):
    """
    Dictionary-based wrapper of :py:class:`monai.transforms.ScaleIntensity`.
    Scale the intensity of input image to the given value range (minv, maxv).
    If `minv` and `maxv` not provided, use `factor` to scale image by ``v = v * (1 + factor)``.
    """

    def __init__(
        self, keys: KeysCollection, minv: float = 0.0, maxv: float = 1.0, factor: Optional[float] = None
    ) -> None:
        """
        Args:
            keys: keys of the corresponding items to be transformed.
                See also: :py:class:`monai.transforms.compose.MapTransform`
            minv: minimum value of output data.
            maxv: maximum value of output data.
            factor: factor scale by ``v = v * (1 + factor)``.

        """
        super().__init__(keys)
        self.scaler = ScaleIntensity(minv, maxv, factor)

    def __call__(self, data):
        d = dict(data)
        for key in self.keys:
            d[key] = self.scaler(d[key])
        return d


class RandScaleIntensityd(Randomizable, MapTransform):
    """
    Dictionary-based version :py:class:`monai.transforms.RandScaleIntensity`.
    """

    def __init__(self, keys: KeysCollection, factors: Union[Tuple[float, float], float], prob: float = 0.1) -> None:
        """
        Args:
            keys: keys of the corresponding items to be transformed.
                See also: :py:class:`monai.transforms.compose.MapTransform`
            factors: factor range to randomly scale by ``v = v * (1 + factor)``.
                if single number, factor value is picked from (-factors, factors).
            prob: probability of rotating.
                (Default 0.1, with 10% probability it returns a rotated array.)

        """
        super().__init__(keys)

        if isinstance(factors, (int, float)):
            self.factors = (min(-factors, factors), max(-factors, factors))
        else:
            assert len(factors) == 2, "factors should be a number or pair of numbers."
            self.factors = (min(factors), max(factors))

        self.prob = prob
        self._do_transform = False

    def randomize(self, data: Optional[Any] = None) -> None:
        self.factor = self.R.uniform(low=self.factors[0], high=self.factors[1])
        self._do_transform = self.R.random() < self.prob

    def __call__(self, data):
        d = dict(data)
        self.randomize()
        if not self._do_transform:
            return d
        scaler = ScaleIntensity(minv=None, maxv=None, factor=self.factor)
        for key in self.keys:
            d[key] = scaler(d[key])
        return d


class NormalizeIntensityd(MapTransform):
    """
    Dictionary-based wrapper of :py:class:`monai.transforms.NormalizeIntensity`.
    This transform can normalize only non-zero values or entire image, and can also calculate
    mean and std on each channel separately.

    Args:
        keys: keys of the corresponding items to be transformed.
            See also: monai.transforms.MapTransform
        subtrahend: the amount to subtract by (usually the mean)
        divisor: the amount to divide by (usually the standard deviation)
        nonzero: whether only normalize non-zero values.
        channel_wise: if using calculated mean and std, calculate on each channel separately
            or calculate on the entire image directly.
    """

    def __init__(
        self,
        keys: KeysCollection,
        subtrahend: Optional[np.ndarray] = None,
        divisor: Optional[np.ndarray] = None,
        nonzero: bool = False,
        channel_wise: bool = False,
    ) -> None:
        super().__init__(keys)
        self.normalizer = NormalizeIntensity(subtrahend, divisor, nonzero, channel_wise)

    def __call__(self, data):
        d = dict(data)
        for key in self.keys:
            d[key] = self.normalizer(d[key])
        return d


class ThresholdIntensityd(MapTransform):
    """
    Dictionary-based wrapper of :py:class:`monai.transforms.ThresholdIntensity`.

    Args:
        keys: keys of the corresponding items to be transformed.
            See also: monai.transforms.MapTransform
        threshold: the threshold to filter intensity values.
        above: filter values above the threshold or below the threshold, default is True.
        cval: value to fill the remaining parts of the image, default is 0.
    """

    def __init__(self, keys: KeysCollection, threshold: float, above: bool = True, cval: float = 0.0) -> None:
        super().__init__(keys)
        self.filter = ThresholdIntensity(threshold, above, cval)

    def __call__(self, data):
        d = dict(data)
        for key in self.keys:
            d[key] = self.filter(d[key])
        return d


class ScaleIntensityRanged(MapTransform):
    """
    Dictionary-based wrapper of :py:class:`monai.transforms.ScaleIntensityRange`.

    Args:
        keys: keys of the corresponding items to be transformed.
            See also: monai.transforms.MapTransform
        a_min: intensity original range min.
        a_max: intensity original range max.
        b_min: intensity target range min.
        b_max: intensity target range max.
        clip: whether to perform clip after scaling.
    """

    def __init__(
        self, keys: KeysCollection, a_min: float, a_max: float, b_min: float, b_max: float, clip: bool = False
    ) -> None:
        super().__init__(keys)
        self.scaler = ScaleIntensityRange(a_min, a_max, b_min, b_max, clip)

    def __call__(self, data):
        d = dict(data)
        for key in self.keys:
            d[key] = self.scaler(d[key])
        return d


class AdjustContrastd(MapTransform):
    """
    Dictionary-based wrapper of :py:class:`monai.transforms.AdjustContrast`.
    Changes image intensity by gamma. Each pixel/voxel intensity is updated as:

        `x = ((x - min) / intensity_range) ^ gamma * intensity_range + min`

    Args:
        keys: keys of the corresponding items to be transformed.
            See also: monai.transforms.MapTransform
        gamma: gamma value to adjust the contrast as function.
    """

    def __init__(self, keys: KeysCollection, gamma: float) -> None:
        super().__init__(keys)
        self.adjuster = AdjustContrast(gamma)

    def __call__(self, data):
        d = dict(data)
        for key in self.keys:
            d[key] = self.adjuster(d[key])
        return d


class RandAdjustContrastd(Randomizable, MapTransform):
    """
    Dictionary-based version :py:class:`monai.transforms.RandAdjustContrast`.
    Randomly changes image intensity by gamma. Each pixel/voxel intensity is updated as:

        `x = ((x - min) / intensity_range) ^ gamma * intensity_range + min`

    Args:
        keys: keys of the corresponding items to be transformed.
            See also: monai.transforms.MapTransform
        prob: Probability of adjustment.
        gamma: Range of gamma values.
            If single number, value is picked from (0.5, gamma), default is (0.5, 4.5).
    """

    def __init__(
        self, keys: KeysCollection, prob: float = 0.1, gamma: Union[Tuple[float, float], float] = (0.5, 4.5)
    ) -> None:
        super().__init__(keys)
        self.prob: float = prob

        if isinstance(gamma, (int, float)):
            assert gamma > 0.5, "if gamma is single number, must greater than 0.5 and value is picked from (0.5, gamma)"
            self.gamma = (0.5, gamma)
        else:
            assert len(gamma) == 2, "gamma should be a number or pair of numbers."
            self.gamma = (min(gamma), max(gamma))

        self._do_transform = False
        self.gamma_value = None

    def randomize(self, data: Optional[Any] = None) -> None:
        self._do_transform = self.R.random_sample() < self.prob
        self.gamma_value = self.R.uniform(low=self.gamma[0], high=self.gamma[1])

    def __call__(self, data):
        d = dict(data)
        self.randomize()
        if not self._do_transform:
            return d
        adjuster = AdjustContrast(self.gamma_value)
        for key in self.keys:
            d[key] = adjuster(d[key])
        return d


class ScaleIntensityRangePercentilesd(MapTransform):
    """
    Dictionary-based wrapper of :py:class:`monai.transforms.ScaleIntensityRangePercentiles`.

    Args:
        keys: keys of the corresponding items to be transformed.
            See also: monai.transforms.MapTransform
        lower: lower percentile.
        upper: upper percentile.
        b_min: intensity target range min.
        b_max: intensity target range max.
        clip: whether to perform clip after scaling.
        relative: whether to scale to the corresponding percentiles of [b_min, b_max]
    """

    def __init__(
        self,
        keys: KeysCollection,
        lower: float,
        upper: float,
        b_min: float,
        b_max: float,
        clip: bool = False,
        relative: bool = False,
    ) -> None:
        super().__init__(keys)
        self.scaler = ScaleIntensityRangePercentiles(lower, upper, b_min, b_max, clip, relative)

    def __call__(self, data):
        d = dict(data)
        for key in self.keys:
            d[key] = self.scaler(d[key])
        return d


class MaskIntensityd(MapTransform):
    """
    Dictionary-based wrapper of :py:class:`monai.transforms.MaskIntensity`.

    Args:
        keys: keys of the corresponding items to be transformed.
            See also: :py:class:`monai.transforms.compose.MapTransform`
        mask_data: if mask data is single channel, apply to evey channel
            of input image. if multiple channels, the channel number must
            match input data. mask_data will be converted to `bool` values
            by `mask_data > 0` before applying transform to input image.

    """

    def __init__(self, keys: KeysCollection, mask_data: np.ndarray):
        super().__init__(keys)
        self.converter = MaskIntensity(mask_data)

    def __call__(self, data):
        d = dict(data)
        for key in self.keys:
            d[key] = self.converter(d[key])
        return d


class GaussianSmoothd(MapTransform):
    """
    Dictionary-based wrapper of :py:class:`monai.transforms.GaussianSmooth`.

    Args:
        keys: keys of the corresponding items to be transformed.
            See also: :py:class:`monai.transforms.compose.MapTransform`
        sigma: if a list of values, must match the count of spatial dimensions of input data,
            and apply every value in the list to 1 spatial dimension. if only 1 value provided,
            use it for all spatial dimensions.

    """

    def __init__(self, keys: KeysCollection, sigma: Union[Sequence[float], float]):
        super().__init__(keys)
        self.converter = GaussianSmooth(sigma)

    def __call__(self, data):
        d = dict(data)
        for key in self.keys:
            d[key] = self.converter(d[key])
        return d


class RandGaussianSmoothd(Randomizable, MapTransform):
    """
    Dictionary-based wrapper of :py:class:`monai.transforms.GaussianSmooth`.

    Args:
        keys: keys of the corresponding items to be transformed.
            See also: :py:class:`monai.transforms.compose.MapTransform`
        sigma_x: randomly select sigma value for the first spatial dimension.
        sigma_y: randomly select sigma value for the second spatial dimension if have.
        sigma_z: randomly select sigma value for the third spatial dimension if have.
        prob: probability of Gaussian smooth.

    """

    def __init__(
        self,
        keys: KeysCollection,
        sigma_x: Tuple[float] = (0.25, 1.5),
        sigma_y: Tuple[float] = (0.25, 1.5),
        sigma_z: Tuple[float] = (0.25, 1.5),
        prob: float = 0.1,
    ):
        super().__init__(keys)
        self.sigma_x = sigma_x
        self.sigma_y = sigma_y
        self.sigma_z = sigma_z
        self.prob = prob
        self._do_transform = False

    def randomize(self, data: Optional[Any] = None) -> None:
        self._do_transform = self.R.random_sample() < self.prob
        self.x = self.R.uniform(low=self.sigma_x[0], high=self.sigma_x[1])
        self.y = self.R.uniform(low=self.sigma_y[0], high=self.sigma_y[1])
        self.z = self.R.uniform(low=self.sigma_z[0], high=self.sigma_z[1])

    def __call__(self, data):
        d = dict(data)
        self.randomize()
        if not self._do_transform:
            return d
        for key in self.keys:
            sigma = ensure_tuple_size(tup=(self.x, self.y, self.z), dim=d[key].ndim - 1)
            d[key] = GaussianSmooth(sigma=sigma)(d[key])
        return d


class GaussianSharpend(MapTransform):
    """
    Dictionary-based wrapper of :py:class:`monai.transforms.GaussianSharpen`.

    Args:
        keys: keys of the corresponding items to be transformed.
            See also: :py:class:`monai.transforms.compose.MapTransform`
        sigma1: sigma parameter for the first gaussian kernel. if a list of values, must match the count
            of spatial dimensions of input data, and apply every value in the list to 1 spatial dimension.
            if only 1 value provided, use it for all spatial dimensions.
        sigma2: sigma parameter for the second gaussian kernel. if a list of values, must match the count
            of spatial dimensions of input data, and apply every value in the list to 1 spatial dimension.
            if only 1 value provided, use it for all spatial dimensions.
        alpha: weight parameter to compute the final result.

    """

    def __init__(
        self,
        keys: KeysCollection,
        sigma1: Union[Sequence[float], float] = 3.0,
        sigma2: Union[Sequence[float], float] = 1.0,
        alpha: float = 30.0,
    ):
        super().__init__(keys)
        self.converter = GaussianSharpen(sigma1, sigma2, alpha)

    def __call__(self, data):
        d = dict(data)
        for key in self.keys:
            d[key] = self.converter(d[key])
        return d


class RandGaussianSharpend(Randomizable, MapTransform):
    """
    Dictionary-based wrapper of :py:class:`monai.transforms.GaussianSharpen`.

    Args:
        keys: keys of the corresponding items to be transformed.
            See also: :py:class:`monai.transforms.compose.MapTransform`
        sigma1_x: randomly select sigma value for the first spatial dimension of first gaussian kernel.
        sigma1_y: randomly select sigma value for the second spatial dimension(if have) of first gaussian kernel.
        sigma1_z: randomly select sigma value for the third spatial dimension(if have) of first gaussian kernel.
        sigma2_x: randomly select sigma value for the first spatial dimension of second gaussian kernel.
            if only 1 value `X` provided, it must be smaller than `sigma1_x` and randomly select from [X, sigma1_x].
        sigma2_y: randomly select sigma value for the second spatial dimension(if have) of second gaussian kernel.
            if only 1 value `Y` provided, it must be smaller than `sigma1_y` and randomly select from [Y, sigma1_y].
        sigma2_z: randomly select sigma value for the third spatial dimension(if have) of second gaussian kernel.
            if only 1 value `Z` provided, it must be smaller than `sigma1_z` and randomly select from [Z, sigma1_z].
        alpha: randomly select weight parameter to compute the final result.
        prob: probability of Gaussian sharpen.

    """

    def __init__(
        self,
        keys: KeysCollection,
        sigma1_x: Tuple[float] = (0.5, 1.0),
        sigma1_y: Tuple[float] = (0.5, 1.0),
        sigma1_z: Tuple[float] = (0.5, 1.0),
        sigma2_x: Union[Tuple[float], float] = 0.5,
        sigma2_y: Union[Tuple[float], float] = 0.5,
        sigma2_z: Union[Tuple[float], float] = 0.5,
        alpha: Tuple[float] = (10.0, 30.0),
        prob: float = 0.1,
    ):
        super().__init__(keys)
        self.sigma1_x = sigma1_x
        self.sigma1_y = sigma1_y
        self.sigma1_z = sigma1_z
        self.sigma2_x = sigma2_x
        self.sigma2_y = sigma2_y
        self.sigma2_z = sigma2_z
        self.alpha = alpha
        self.prob = prob
        self._do_transform = False

    def randomize(self, data: Optional[Any] = None) -> None:
        self._do_transform = self.R.random_sample() < self.prob
        self.x1 = self.R.uniform(low=self.sigma1_x[0], high=self.sigma1_x[1])
        self.y1 = self.R.uniform(low=self.sigma1_y[0], high=self.sigma1_y[1])
        self.z1 = self.R.uniform(low=self.sigma1_z[0], high=self.sigma1_z[1])
        if not isinstance(self.sigma2_x, Iterable):
            self.sigma2_x = (self.sigma2_x, self.x1)
        if not isinstance(self.sigma2_y, Iterable):
            self.sigma2_y = (self.sigma2_y, self.y1)
        if not isinstance(self.sigma2_z, Iterable):
            self.sigma2_z = (self.sigma2_z, self.z1)
        self.x2 = self.R.uniform(low=self.sigma2_x[0], high=self.sigma2_x[1])
        self.y2 = self.R.uniform(low=self.sigma2_y[0], high=self.sigma2_y[1])
        self.z2 = self.R.uniform(low=self.sigma2_z[0], high=self.sigma2_z[1])
        self.a = self.R.uniform(low=self.alpha[0], high=self.alpha[1])

    def __call__(self, data):
        d = dict(data)
        self.randomize()
        if not self._do_transform:
            return d
        for key in self.keys:
            sigma1 = ensure_tuple_size(tup=(self.x1, self.y1, self.z1), dim=d[key].ndim - 1)
            sigma2 = ensure_tuple_size(tup=(self.x2, self.y2, self.z2), dim=d[key].ndim - 1)
            d[key] = GaussianSharpen(sigma1=sigma1, sigma2=sigma2, alpha=self.a)(d[key])
        return d


RandGaussianNoiseD = RandGaussianNoiseDict = RandGaussianNoised
ShiftIntensityD = ShiftIntensityDict = ShiftIntensityd
RandShiftIntensityD = RandShiftIntensityDict = RandShiftIntensityd
ScaleIntensityD = ScaleIntensityDict = ScaleIntensityd
RandScaleIntensityD = RandScaleIntensityDict = RandScaleIntensityd
NormalizeIntensityD = NormalizeIntensityDict = NormalizeIntensityd
ThresholdIntensityD = ThresholdIntensityDict = ThresholdIntensityd
ScaleIntensityRangeD = ScaleIntensityRangeDict = ScaleIntensityRanged
AdjustContrastD = AdjustContrastDict = AdjustContrastd
RandAdjustContrastD = RandAdjustContrastDict = RandAdjustContrastd
ScaleIntensityRangePercentilesD = ScaleIntensityRangePercentilesDict = ScaleIntensityRangePercentilesd
MaskIntensityD = MaskIntensityDict = MaskIntensityd
GaussianSmoothD = GaussianSmoothDict = GaussianSmoothd
RandGaussianSmoothD = RandGaussianSmoothDict = RandGaussianSmoothd
GaussianSharpenD = GaussianSharpenDict = GaussianSharpend
RandGaussianSharpenD = RandGaussianSharpenDict = RandGaussianSharpend
