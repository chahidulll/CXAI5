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

import json
from typing import Dict, List, Tuple, Union

import numpy as np

from monai.apps.pathology.utils import PathologyProbNMS
from monai.data.image_reader import WSIReader
from monai.metrics import compute_fp_tp_probs, compute_froc_curve_data, compute_froc_score
from monai.utils import optional_import

measure, _ = optional_import("skimage.measure")
ndimage, _ = optional_import("scipy.ndimage")


class EvaluateTumorFROC:
    """
    Evaluate with Free Response Operating Characteristic (FROC) score.

    Args:
        data: either the list of dictionaries containg probability maps (inference result) and
            tumor mask (ground truth), as below, or the path to a json file containing such list.
            `{
            "prob_map": "path/to/prob_map_1.npy",
            "tumor_mask": "path/to/ground_truth_1.tiff",
            "level": 6,
            "pixel_spacing": 0.243
            }`
        grow_distance: Euclidean distance (in micrometer) by which to grow the label the ground truth's tumors.
            Defaults to 75, which is the equivalent size of 5 tumor cells.
        itc_diameter: the maximum diameter of a region (in micrometer) to be considered as an isolated tumor cell.
            Defaults to 200.
        eval_thresholds: the false positive rates for calculating the average sensitivity.
            Defaults to (0.25, 0.5, 1, 2, 4, 8) which is the same as the CAMELYON 16 Challenge.
        image_reader_name: the name of library to be used for loading whole slide imaging, either CuCIM or OpenSlide.
            Defaults to CuCIM.

    """

    def __init__(
        self,
        data: Union[List[Dict], str],
        grow_distance: int = 75,
        itc_diameter: int = 200,
        eval_thresholds: Tuple = (0.25, 0.5, 1, 2, 4, 8),
        image_reader_name: str = "cuCIM",
    ) -> None:

        if isinstance(data, str):
            self.data = self._load_data(data)
        else:
            self.data = data
        self.grow_distance = grow_distance
        self.itc_diameter = itc_diameter
        self.eval_thresholds = eval_thresholds
        self.image_reader = WSIReader(image_reader_name)
        self.nms = PathologyProbNMS(
            sigma=0.0,
            prob_threshold=0.5,
            box_size=48,
        )

    def _load_data(self, file_path):
        with open(file_path, "r") as f:
            data = json.load(f)
        return data

    def prepare_inference_result(self, sample):
        """
        Prepare the probability map for detection evaluation.

        """
        # load the probability map (the result of model inference)
        prob_map = np.load(sample["prob_map"])

        # apply non-maximal suppression
        nms_outputs = self.nms(probs_map=prob_map, resolution_level=sample["level"])

        # separate nms outputs
        if nms_outputs:
            probs, x_coord, y_coord = zip(*nms_outputs)
        else:
            probs, x_coord, y_coord = [], [], []

        return np.array(probs), np.array(x_coord), np.array(y_coord)

    def prepare_ground_truth(self, sample):
        """
        Prapare the ground truth for evalution based on the binary tumor mask

        """
        # load binary tumor masks
        img_obj = self.image_reader.read(sample["tumor_mask"])
        tumor_mask = self.image_reader.get_data(img_obj, level=sample["level"])[0][0]

        # calcualte pixel spacing at the mask level
        mask_pixel_spacing = sample["pixel_spacing"] * pow(2, sample["level"])

        # compute multi-instance mask from a binary mask
        grow_pixel_threshold = self.grow_distance / (mask_pixel_spacing * 2)
        tumor_mask = self.compute_multi_instance_mask(mask=tumor_mask, threshold=grow_pixel_threshold)

        # identify isolated tumor cells
        itc_threshold = (self.itc_diameter + self.grow_distance) / mask_pixel_spacing
        itc_labels = self.compute_isolated_tumor_cells(tumor_mask=tumor_mask, threshold=itc_threshold)

        return tumor_mask, itc_labels

    def compute_fp_tp(self):
        """
        Compute false positive and true positive probabilities for tumor detection,
        by comparing the model outputs with the prepared ground truths for all samples

        """
        total_fp_probs, total_tp_probs = [], []
        total_num_targets = 0
        num_images = len(self.data)

        for sample in self.data:
            probs, y_coord, x_coord = self.prepare_inference_result(sample)
            ground_truth, itc_labels = self.prepare_ground_truth(sample)
            # compute FP and TP probabilities for a pair of an image and an ground truth mask
            fp_probs, tp_probs, num_targets = compute_fp_tp_probs(
                probs=probs,
                y_coord=y_coord,
                x_coord=x_coord,
                evaluation_mask=ground_truth,
                labels_to_exclude=itc_labels,
                resolution_level=sample["level"],
            )
            total_fp_probs.extend(fp_probs)
            total_tp_probs.extend(tp_probs)
            total_num_targets += num_targets

        return (
            np.array(total_fp_probs),
            np.array(total_tp_probs),
            total_num_targets,
            num_images,
        )

    def evaluate(self):
        """
        Evalaute the detection performance of a model based on the model probability map output,
        the ground truth tumor mask, and their associated metadata (e.g., pixel_spacing, level)
        """
        # compute false positive (FP) and true positive (TP) probabilities for all images
        fp_probs, tp_probs, num_targets, num_images = self.compute_fp_tp()

        # compute FROC curve given the evaluation of all images
        fps_per_image, total_sensitivity = compute_froc_curve_data(
            fp_probs=fp_probs,
            tp_probs=tp_probs,
            num_targets=num_targets,
            num_images=num_images,
        )

        # compute FROC score give specific evaluation threshold
        froc_score = compute_froc_score(
            fps_per_image=fps_per_image,
            total_sensitivity=total_sensitivity,
            eval_thresholds=self.eval_thresholds,
        )

        return froc_score

    def compute_multi_instance_mask(self, mask: np.ndarray, threshold: float):
        """
        This method computes the segmentation mask according to the binary tumor mask.

        Args:
            mask: the binary mask array
            threshold: the threashold to fill holes
        """
        # make sure it is between 0 and 1
        assert 0 <= mask.max() <= 1, "The input mask should be a binary mask!"
        neg = 255 - mask * 255
        distance = ndimage.morphology.distance_transform_edt(neg)
        binary = distance < threshold

        filled_image = ndimage.morphology.binary_fill_holes(binary)
        multi_instance_mask = measure.label(filled_image, connectivity=2)

        return multi_instance_mask

    def compute_isolated_tumor_cells(self, tumor_mask: np.ndarray, threshold: float) -> List[int]:
        """
        This method computes identifies Isolated Tumor Cells (ITC) and return their labels.

        Args:
            tumor_mask: the tumor mask.
            threshold: the threshold (at the mask level) to define an isolated tumor cell (ITC).
                A region with the longest diameter less than this threshold is considered as an ITC.
        """
        max_label = np.amax(tumor_mask)
        properties = measure.regionprops(tumor_mask, coordinates="rc")
        itc_list = []
        for i in range(max_label):  # type: ignore
            if properties[i].major_axis_length < threshold:
                itc_list.append(i + 1)

        return itc_list
