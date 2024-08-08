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

from __future__ import annotations

import unittest

import torch
from parameterized import parameterized

from monai.transforms.utils import convert_points_to_disc, sample_points_from_label

TESTS_SAMPLE_POINTS_FROM_LABEL = []
for use_center in [True, False]:
    labels = torch.zeros(1, 1, 32, 32, 32)
    labels[0, 0, 5:10, 5:10, 5:10] = 1
    labels[0, 0, 10:15, 10:15, 10:15] = 3
    labels[0, 0, 20:25, 20:25, 20:25] = 5
    TESTS_SAMPLE_POINTS_FROM_LABEL.append(
        [{"labels": labels, "label_set": (1, 3, 5), "use_center": use_center}, (3, 1, 3), (3, 1)]
    )

TEST_CONVERT_POINTS_TO_DISC = []
for radius in [1, 2]:
    for disc in [True, False]:
        image_size = (32, 32, 32)
        point = torch.randn(3, 1, 3)
        point_label = torch.randint(0, 4, (3, 1))
        expected_shape = (point.shape[0], 2, *image_size)
        TEST_CONVERT_POINTS_TO_DISC.append(
            [
                {"image_size": image_size, "point": point, "point_label": point_label, "radius": radius, "disc": disc},
                expected_shape,
            ]
        )


class TestSamplePointsFromLabel(unittest.TestCase):

    @parameterized.expand(TESTS_SAMPLE_POINTS_FROM_LABEL)
    def test_shape(self, input_data, expected_point_shape, expected_point_label_shape):
        point, point_label = sample_points_from_label(**input_data)
        self.assertEqual(point.shape, expected_point_shape)
        self.assertEqual(point_label.shape, expected_point_label_shape)


class TestConvertPointsToDisc(unittest.TestCase):

    @parameterized.expand(TEST_CONVERT_POINTS_TO_DISC)
    def test_shape(self, input_data, expected_shape):
        result = convert_points_to_disc(**input_data)
        self.assertEqual(result.shape, expected_shape)


if __name__ == "__main__":
    unittest.main()
