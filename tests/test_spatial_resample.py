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

import itertools
import unittest

import numpy as np
from parameterized import parameterized

from monai.config import USE_COMPILED
from monai.transforms import SpatialResample
from tests.utils import TEST_NDARRAYS, assert_allclose

TESTS = []

for ind, dst in enumerate(
    [
        np.asarray([[1.0, 0.0, 0.0], [0.0, -1.0, 1.0], [0.0, 0.0, 1.0]]),  # flip the second
        np.asarray([[-1.0, 0.0, 1.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]),  # flip the first
    ]
):
    for p in TEST_NDARRAYS:
        for p_src in TEST_NDARRAYS:
            for dtype in (np.float32, np.float64):
                for align in (False, True):
                    for interp_mode in ("nearest", "bilinear"):
                        for padding_mode in ("zeros", "border", "reflection"):
                            TESTS.append(
                                [
                                    {},  # default no params
                                    np.arange(4).reshape((1, 2, 2)) + 1.0,  # data
                                    {
                                        "src": p_src(np.eye(3)),
                                        "dst": p(dst),
                                        "dtype": dtype,
                                        "align_corners": align,
                                        "mode": interp_mode,
                                        "padding_mode": padding_mode,
                                    },
                                    np.array([[[2.0, 1.0], [4.0, 3.0]]])
                                    if ind == 0
                                    else np.array([[[3.0, 4.0], [1.0, 2.0]]]),
                                ]
                            )

for ind, dst in enumerate(
    [
        np.asarray([[1.0, 0.0, 0.0, 0.0], [0.0, -1.0, 0.0, 1.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]),
        np.asarray([[-1.0, 0.0, 0.0, 1.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]),
    ]
):
    for p in TEST_NDARRAYS:
        for p_src in TEST_NDARRAYS:
            for dtype in (np.float32, np.float64):
                for align in (True, False):
                    interp = ("nearest", "bilinear")
                    if align and USE_COMPILED:
                        interp = interp + (0, 1)  # type: ignore
                    for interp_mode in interp:
                        for padding_mode in ("zeros", "border", "reflection"):
                            TESTS.append(
                                [
                                    {},  # default no params
                                    np.arange(12).reshape((1, 2, 2, 3)) + 1.0,  # data
                                    {
                                        "src": p_src(np.eye(4)),
                                        "dst": p(dst),
                                        "dtype": dtype,
                                        "align_corners": align,
                                        "mode": interp_mode,
                                        "padding_mode": padding_mode,
                                    },
                                    np.array(
                                        [[[[4.0, 5.0, 6.0], [1.0, 2.0, 3.0]], [[10.0, 11.0, 12.0], [7.0, 8.0, 9.0]]]]
                                    )
                                    if ind == 0
                                    else np.array(
                                        [[[[7.0, 8.0, 9.0], [10.0, 11.0, 12.0]], [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]]]
                                    ),
                                ]
                            )


class TestSpatialResample(unittest.TestCase):
    @parameterized.expand(itertools.product(TEST_NDARRAYS, TESTS))
    def test_flips(self, p_type, args):
        init_param, img, data_param, expected_output = args
        _img = p(img)
        _expected_output = p(expected_output)
        output_data, output_dst = SpatialResample(**init_param)(img=_img, **data_param)
        assert_allclose(output_data, _expected_output)
        expected_dst = data_param.get("dst") if data_param.get("dst") is not None else data_param.get("src")
        assert_allclose(output_dst, expected_dst, type_test=False)

    @parameterized.expand(itertools.product([True, False], TEST_NDARRAYS))
    def test_4d_5d(self, is_5d, p_type):
        new_shape = (1, 2, 2, 3, 1, 1) if is_5d else (1, 2, 2, 3, 1)
        img = np.arange(12).reshape(new_shape)
        img = np.tile(img, (1, 1, 1, 1, 2, 2) if is_5d else (1, 1, 1, 1, 2))
        _img = p_type(img)
        dst = np.asarray([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, -1.0, 1.5], [0.0, 0.0, 0.0, 1.0]])
        output_data, output_dst = SpatialResample(dtype=np.float32)(img=_img, src=p(np.eye(4)), dst=dst)
        expected_data = (
            np.asarray(
                [
                    [
                        [[[0.0, 0.0], [0.0, 1.0]], [[0.5, 0.0], [1.5, 1.0]], [[1.0, 2.0], [2.0, 2.0]]],
                        [[[3.0, 3.0], [3.0, 4.0]], [[3.5, 3.0], [4.5, 4.0]], [[4.0, 5.0], [5.0, 5.0]]],
                    ],
                    [
                        [[[6.0, 6.0], [6.0, 7.0]], [[6.5, 6.0], [7.5, 7.0]], [[7.0, 8.0], [8.0, 8.0]]],
                        [[[9.0, 9.0], [9.0, 10.0]], [[9.5, 9.0], [10.5, 10.0]], [[10.0, 11.0], [11.0, 11.0]]],
                    ],
                ],
                dtype=np.float32,
            )
            if is_5d
            else np.asarray(
                [
                    [[[0.5, 0.0], [0.0, 2.0], [1.5, 1.0]], [[3.5, 3.0], [3.0, 5.0], [4.5, 4.0]]],
                    [[[6.5, 6.0], [6.0, 8.0], [7.5, 7.0]], [[9.5, 9.0], [9.0, 11.0], [10.5, 10.0]]],
                ],
                dtype=np.float32,
            )
        )
        assert_allclose(output_data, p_type(expected_data[None]))
        assert_allclose(output_dst, dst, type_test=False)

    def test_ill_affine(self):
        img = np.arange(12).reshape(1, 2, 2, 3)
        ill_affine = np.asarray(
            [[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0], [0.0, 0.0, -1.0, 1.5], [0.0, 0.0, 0.0, 1.0]]
        )
        with self.assertRaises(ValueError):
            SpatialResample()(img=img, src=np.eye(4), dst=ill_affine)
        with self.assertRaises(ValueError):
            SpatialResample()(img=img, src=ill_affine, dst=np.eye(3))


if __name__ == "__main__":
    unittest.main()
