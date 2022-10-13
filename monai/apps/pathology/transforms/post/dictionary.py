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

from typing import Optional

from monai.config import KeysCollection
from monai.config.type_definitions import DtypeLike
from monai.transforms.transform import MapTransform
from monai.utils import optional_import

from .array import GenerateSuccinctContour, GenerateInstanceContour, GenerateInstanceCentroid, GenerateInstanceType

find_contours, _ = optional_import("skimage.measure", name="find_contours")
moments, _ = optional_import("skimage.measure", name="moments")

__all__ = [
    "GenerateSuccinctContourDict",
    "GenerateSuccinctContourD",
    "GenerateSuccinctContourd",
    "GenerateInstanceContourDict",
    "GenerateInstanceContourD",
    "GenerateInstanceContourd",
    "GenerateInstanceCentroidDict",
    "GenerateInstanceCentroidD",
    "GenerateInstanceCentroidd",
    "GenerateInstanceTypeDict",
    "GenerateInstanceTypeD",
    "GenerateInstanceTyped",
]


class GenerateSuccinctContourd(MapTransform):
    """
    Dictionary-based wrapper of :py:class:`monai.apps.pathology.transforms.post.array.GenerateSuccinctContour`.
    Converts Scipy-style contours(generated by skimage.measure.find_contours) to a more succinct version which 
    only includes the pixels to which lines need to be drawn (i.e. not the intervening pixels along each line).
    
    Args:
        keys: keys of the corresponding items to be transformed.
        height: height of bounding box, used to detect direction of line segment.
        width: width of bounding box, used to detect direction of line segment.
        allow_missing_keys: don't raise exception if key is missing.

    """

    backend = GenerateSuccinctContour.backend

    def __init__(self, keys: KeysCollection, height: int, width: int, allow_missing_keys: bool = False) -> None:
        super().__init__(keys, allow_missing_keys)
        self.converter = GenerateSuccinctContour(height=height, width=width)

    def __call__(self, data):
        d = dict(data)
        for key in self.key_iterator(d):
            d[key] = self.converter(d[key])

        return d


class GenerateInstanceContourd(MapTransform):
    """
    Dictionary-based wrapper of :py:class:`monai.apps.pathology.transforms.post.array.GenerateInstanceContour`.
    Generate contour for each instance in a 2D array. Use `GenerateSuccinctContour` to only include the pixels
    to which lines need to be drawn
   
    Args:
        keys: keys of the corresponding items to be transformed.
        contour_key_postfix: the output contour coordinates will be written to the value of 
            `{key}_{contour_key_postfix}`.
        offset_key: keys of offset used in `GenerateInstanceContour`.
        points_num: assumed that the created contour does not form a contour if it does not contain more points
            than the specified value. Defaults to 3.
        level: optional. Value along which to find contours in the array. By default, the level is set
            to (max(image) + min(image)) / 2.
        allow_missing_keys: don't raise exception if key is missing.

    """

    backend = GenerateInstanceContour.backend

    def __init__(
        self, 
        keys: KeysCollection,
        contour_key_postfix: str = "contour",
        offset_key: Optional[str] = None,
        points_num: int = 3, 
        level: Optional[float] = None, 
        allow_missing_keys: bool = False
    ) -> None:
        super().__init__(keys, allow_missing_keys)
        self.converter = GenerateInstanceContour(points_num=points_num, level=level)
        self.contour_key_postfix = contour_key_postfix
        self.offset_key = offset_key

    def __call__(self, data):
        d = dict(data)
        for key in self.key_iterator(d):
            offset = d[self.offset_key] if self.offset_key else None
            contour = self.converter(d[key], offset)
            key_to_add = f"{key}_{self.contour_key_postfix}"
            if key_to_add in d:
                raise KeyError(f"Contour with key {key_to_add} already exists.")
            d[key_to_add] = contour
        return d


class GenerateInstanceCentroidd(MapTransform):
    """
    Dictionary-based wrapper of :py:class:`monai.apps.pathology.transforms.post.array.GenerateInstanceCentroid`.
    Generate instance centroid using `skimage.measure.centroid`.

    Args:
        keys: keys of the corresponding items to be transformed.
        centroid_key_postfix: the output centroid coordinates will be written to the value of 
            `{key}_{centroid_key_postfix}`.
        offset_key: keys of offset used in `GenerateInstanceCentroid`.
        dtype: the data type of output centroid.
        allow_missing_keys: don't raise exception if key is missing.

    """

    backend = GenerateInstanceCentroid.backend

    def __init__(
        self, 
        keys: KeysCollection,
        centroid_key_postfix: str = "centroid",
        offset_key: Optional[str] = None,
        dtype: Optional[DtypeLike] = None,
        allow_missing_keys: bool = False
    ) -> None:
        super().__init__(keys, allow_missing_keys)
        self.converter = GenerateInstanceCentroid(dtype=dtype)
        self.centroid_key_postfix = centroid_key_postfix
        self.offset_key = offset_key

    def __call__(self, data):
        d = dict(data)
        for key in self.key_iterator(d):
            offset = d[self.offset_key] if self.offset_key else None
            centroid = self.converter(d[key], offset)
            key_to_add = f"{key}_{self.centroid_key_postfix}"
            if key_to_add in d:
                raise KeyError(f"Centroid with key {key_to_add} already exists.")
            d[key_to_add] = centroid
        return d


class GenerateInstanceTyped(MapTransform):
    """
    Dictionary-based wrapper of :py:class:`monai.apps.pathology.transforms.post.array.GenerateInstanceType`.
    Generate instance type and probability for each instance.

    Args:
        keys: keys of the corresponding items to be transformed.
        type_info_key: the output instance type and probability will be written to the value of 
            `{type_info_key}`.
        bbox_key: keys of bounding box.
        seg_pred_key: keys of segmentation prediction map.
        instance_id_key: keys of instance id.
        allow_missing_keys: don't raise exception if key is missing.

    """

    backend = GenerateInstanceType.backend

    def __init__(
        self, 
        keys: KeysCollection,
        type_info_key: str = "type_info",
        bbox_key: str = "bbox",
        seg_pred_key: str = "seg",
        instance_id_key: str = "id",
        allow_missing_keys: bool = False
    ) -> None:
        super().__init__(keys, allow_missing_keys)
        self.converter = GenerateInstanceType()
        self.type_info_key = type_info_key
        self.bbox_key = bbox_key
        self.seg_pred_key = seg_pred_key
        self.instance_id_key = instance_id_key

    def __call__(self, data):
        d = dict(data)
        for key in self.key_iterator(d):
            seg = d[self.seg_pred_key]
            bbox = d[self.bbox_key]
            id = d[self.instance_id_key]
            instance_type, type_prob = self.converter(d[key], seg, bbox, id)
            key_to_add = f"{self.type_info_key}"
            if key_to_add in d:
                raise KeyError(f"Type information with key {key_to_add} already exists.")
            d[key_to_add] = {'inst_type': instance_type, 'type_prob': type_prob}
        return d



GenerateSuccinctContourDict = GenerateSuccinctContourD = GenerateSuccinctContourd
GenerateInstanceContourDict = GenerateInstanceContourD = GenerateInstanceContourd
GenerateInstanceCentroidDict = GenerateInstanceCentroidD = GenerateInstanceCentroidd
GenerateInstanceTypeDict = GenerateInstanceTypeD = GenerateInstanceTyped
