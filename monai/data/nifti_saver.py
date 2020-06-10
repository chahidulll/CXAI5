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

from typing import Optional, Union

import numpy as np
import torch

from monai.data.nifti_writer import write_nifti

from .utils import create_file_basename


class NiftiSaver:
    """
    Save the data as NIfTI file, it can support single data content or a batch of data.
    Typically, the data can be segmentation predictions, call `save` for single data
    or call `save_batch` to save a batch of data together. If no meta data provided,
    use index from 0 as the filename prefix.
    """

    def __init__(
        self,
        output_dir: str = "./",
        output_postfix: str = "seg",
        output_ext: str = ".nii.gz",
        resample: bool = True,
        interp_order: str = "bilinear",
        mode: str = "border",
        dtype: Optional[np.dtype] = None,
    ):
        """
        Args:
            output_dir (str): output image directory.
            output_postfix (str): a string appended to all output file names.
            output_ext (str): output file extension name.
            resample (bool): whether to resample before saving the data array.
            interp_order (`nearest|bilinear`): the interpolation mode, default is "bilinear".
                See also: https://pytorch.org/docs/stable/nn.functional.html#grid-sample
                This option is used when `resample = True`.
            mode (`zeros|border|reflection`):
                The mode parameter determines how the input array is extended beyond its boundaries.
                Defaults to "border". This option is used when `resample = True`.
            dtype (np.dtype, optional): convert the image data to save to this data type.
                If None, keep the original type of data.
        """
        self.output_dir = output_dir
        self.output_postfix = output_postfix
        self.output_ext = output_ext
        self.resample = resample
        self.interp_order = interp_order
        self.mode = mode
        self.dtype = dtype
        self._data_index = 0

    def save(self, data: Union[torch.Tensor, np.ndarray], meta_data=None):
        """
        Save data into a Nifti file.
        The metadata could optionally have the following keys:

            - ``'filename_or_obj'`` -- for output file name creation, corresponding to filename or object.
            - ``'original_affine'`` -- for data orientation handling, defaulting to an identity matrix.
            - ``'affine'`` -- for data output affine, defaulting to an identity matrix.
            - ``'spatial_shape'`` -- for data output shape.

        If meta_data is None, use the default index from 0 to save data instead.

        args:
            data (Tensor or ndarray): target data content that to be saved as a NIfTI format file.
                Assuming the data shape starts with a channel dimension and followed by spatial dimensions.
            meta_data (dict): the meta data information corresponding to the data.

        See Also
            :py:meth:`monai.data.nifti_writer.write_nifti`
        """
        filename = meta_data["filename_or_obj"] if meta_data else str(self._data_index)
        self._data_index += 1
        original_affine = meta_data.get("original_affine", None) if meta_data else None
        affine = meta_data.get("affine", None) if meta_data else None
        spatial_shape = meta_data.get("spatial_shape", None) if meta_data else None

        if torch.is_tensor(data):
            data = data.detach().cpu().numpy()
        filename = create_file_basename(self.output_postfix, filename, self.output_dir)
        filename = f"{filename}{self.output_ext}"
        # change data shape to be (channel, h, w, d)
        while len(data.shape) < 4:
            data = np.expand_dims(data, -1)
        # change data to "channel last" format and write to nifti format file
        data = np.moveaxis(data, 0, -1)
        write_nifti(
            data,
            file_name=filename,
            affine=affine,
            target_affine=original_affine,
            resample=self.resample,
            output_shape=spatial_shape,
            interp_order=self.interp_order,
            mode=self.mode,
            dtype=self.dtype or data.dtype,
        )

    def save_batch(self, batch_data: Union[torch.Tensor, np.ndarray], meta_data=None):
        """
        Save a batch of data into Nifti format files.

        Spatially it supports up to three dimensions, that is, H, HW, HWD for
        1D, 2D, 3D respectively (with resampling supports for 2D and 3D only).

        When saving multiple time steps or multiple channels `batch_data`,
        time and/or modality axes should be appended after the batch dimensions.
        For example, the shape of a batch of 2D eight-class
        segmentation probabilities to be saved could be `(batch, 8, 64, 64)`;
        in this case each item in the batch will be saved as (64, 64, 1, 8)
        NIfTI file (the third dimension is reserved as a spatial dimension).

        args:
            batch_data (Tensor or ndarray): target batch data content that save into NIfTI format.
            meta_data (dict): every key-value in the meta_data is corresponding to a batch of data.
        """
        for i, data in enumerate(batch_data):  # save a batch of files
            self.save(data, {k: meta_data[k][i] for k in meta_data} if meta_data else None)
