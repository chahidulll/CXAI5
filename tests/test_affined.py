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
from copy import deepcopy

import numpy as np
import torch
from parameterized import parameterized

from monai.transforms import Affined
from tests.utils import TEST_NDARRAYS_ALL, assert_allclose, test_local_inversion

TESTS = []
for p in TEST_NDARRAYS_ALL:
    for device in [None, "cpu", "cuda"] if torch.cuda.is_available() else [None, "cpu"]:
        TESTS.append(
            [
                dict(keys="img", padding_mode="zeros", spatial_size=(-1, 0), device=device),
                {"img": p(np.arange(9).reshape((1, 3, 3)))},
                p(np.arange(9).reshape(1, 3, 3)),
            ]
        )
        TESTS.append(
            [
                dict(keys="img", padding_mode="zeros", spatial_size=(-1, 0), device=device, dtype=None),
                {"img": p(np.arange(9, dtype=float).reshape((1, 3, 3)))},
                p(np.arange(9).reshape(1, 3, 3)),
            ]
        )
        TESTS.append(
            [
                dict(keys="img", padding_mode="zeros", device=device),
                {"img": p(np.arange(4).reshape((1, 2, 2)))},
                p(np.arange(4).reshape(1, 2, 2)),
            ]
        )
        TESTS.append(
            [
                dict(keys="img", padding_mode="zeros", spatial_size=(4, 4), device=device),
                {"img": p(np.arange(4).reshape((1, 2, 2)))},
                p(np.array([[[0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 2.0, 3.0, 0.0], [0.0, 0.0, 0.0, 0.0]]])),
            ]
        )
        TESTS.append(
            [
                dict(keys="img", rotate_params=[np.pi / 2], padding_mode="zeros", spatial_size=(4, 4), device=device),
                {"img": p(np.arange(4).reshape((1, 2, 2)))},
                p(np.array([[[0.0, 0.0, 0.0, 0.0], [0.0, 2.0, 0.0, 0.0], [0.0, 3.0, 1.0, 0.0], [0.0, 0.0, 0.0, 0.0]]])),
            ]
        )
        TESTS.append(
            [
                dict(
                    keys="img",
                    affine=p(torch.tensor([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])),
                    padding_mode="zeros",
                    spatial_size=(4, 4),
                    device=device,
                ),
                {"img": p(np.arange(4).reshape((1, 2, 2)))},
                p(np.array([[[0.0, 0.0, 0.0, 0.0], [0.0, 2.0, 0.0, 0.0], [0.0, 3.0, 1.0, 0.0], [0.0, 0.0, 0.0, 0.0]]])),
            ]
        )
        TESTS.append(
            [
                dict(keys="img", padding_mode="zeros", spatial_size=(-1, 0, 0), device=device),
                {"img": p(np.arange(27).reshape((1, 3, 3, 3)))},
                p(np.arange(27).reshape(1, 3, 3, 3)),
            ]
        )
        TESTS.append(
            [
                dict(keys="img", padding_mode="zeros", spatial_size=(-1, 0, 0), device=device, align_corners=False),
                {"img": p(np.arange(27).reshape((1, 3, 3, 3)))},
                p(
                    np.array(
                        [
                            [
                                [[0.00, 0.25, 0.25], [0.75, 2.0, 1.25], [0.75, 1.75, 1.00]],
                                [[2.25, 5.00, 2.75], [6.00, 13.0, 7.00], [3.75, 8.0, 4.25]],
                                [[2.25, 4.75, 2.50], [5.25, 11.0, 5.75], [3.00, 6.25, 3.25]],
                            ]
                        ]
                    )
                ),
            ]
        )
        TESTS.append(
            [
                dict(keys="img", padding_mode="zeros", spatial_size=(4, 4, 4), device=device),
                {"img": p(np.arange(8).reshape((1, 2, 2, 2)))},
                p(
                    np.array(
                        [
                            [
                                [
                                    [0.0, 0.0, 0.0, 0.0],
                                    [0.0, 0.0, 0.0, 0.0],
                                    [0.0, 0.0, 0.0, 0.0],
                                    [0.0, 0.0, 0.0, 0.0],
                                ],
                                [
                                    [0.0, 0.0, 0.0, 0.0],
                                    [0.0, 0.0, 1.0, 0.0],
                                    [0.0, 2.0, 3.0, 0.0],
                                    [0.0, 0.0, 0.0, 0.0],
                                ],
                                [
                                    [0.0, 0.0, 0.0, 0.0],
                                    [0.0, 4.0, 5.0, 0.0],
                                    [0.0, 6.0, 7.0, 0.0],
                                    [0.0, 0.0, 0.0, 0.0],
                                ],
                                [
                                    [0.0, 0.0, 0.0, 0.0],
                                    [0.0, 0.0, 0.0, 0.0],
                                    [0.0, 0.0, 0.0, 0.0],
                                    [0.0, 0.0, 0.0, 0.0],
                                ],
                            ]
                        ]
                    )
                ),
            ]
        )
        TESTS.append(
            [
                dict(
                    keys="img", rotate_params=[np.pi / 2], padding_mode="zeros", spatial_size=(4, 4, 4), device=device
                ),
                {"img": p(np.arange(8).reshape((1, 2, 2, 2)))},
                p(
                    np.array(
                        [
                            [
                                [
                                    [0.0, 0.0, 0.0, 0.0],
                                    [0.0, 0.0, 0.0, 0.0],
                                    [0.0, 0.0, 0.0, 0.0],
                                    [0.0, 0.0, 0.0, 0.0],
                                ],
                                [
                                    [0.0, 0.0, 0.0, 0.0],
                                    [0.0, 2.0, 0.0, 0.0],
                                    [0.0, 3.0, 1.0, 0.0],
                                    [0.0, 0.0, 0.0, 0.0],
                                ],
                                [
                                    [0.0, 0.0, 0.0, 0.0],
                                    [0.0, 6.0, 4.0, 0.0],
                                    [0.0, 7.0, 5.0, 0.0],
                                    [0.0, 0.0, 0.0, 0.0],
                                ],
                                [
                                    [0.0, 0.0, 0.0, 0.0],
                                    [0.0, 0.0, 0.0, 0.0],
                                    [0.0, 0.0, 0.0, 0.0],
                                    [0.0, 0.0, 0.0, 0.0],
                                ],
                            ]
                        ]
                    )
                ),
            ]
        )


class TestAffined(unittest.TestCase):
    @parameterized.expand(TESTS)
    def test_affine(self, input_param, input_data, expected_val):
        input_copy = deepcopy(input_data)
        g = Affined(**input_param)
        result = g(input_data)
        test_local_inversion(g, result, input_copy, dict_key="img")
        assert_allclose(result["img"], expected_val, rtol=1e-4, atol=1e-4, type_test="tensor")


if __name__ == "__main__":
    unittest.main()
