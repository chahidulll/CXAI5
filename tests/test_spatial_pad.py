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

import unittest
from typing import List

import numpy as np
import torch
from parameterized import parameterized

from monai.data.meta_tensor import MetaTensor
from monai.transforms import SpatialPad
from monai.utils.enums import NumpyPadMode, PytorchPadMode
from tests.utils import TEST_NDARRAYS, assert_allclose

TESTS = []

MODES = []

# Test modes
NP_MODES: List = [
    "constant",
    "edge",
    # `reflect` mode is not supported in some PyTorch versions, skip the test
    # "reflect",
    "wrap",
    "median",
]
MODES += NP_MODES
MODES += [NumpyPadMode(i) for i in NP_MODES]

PT_MODES: list = [
    "constant",
    "replicate",
    "circular",
    # `reflect` mode is not supported in some PyTorch versions, skip the test
    # "reflect",
]
MODES += PT_MODES
MODES += [PytorchPadMode(i) for i in PT_MODES]

for mode in MODES:
    TESTS.append([{"spatial_size": [3, 4], "method": "end", "mode": mode}, (1, 2, 3), (1, 3, 4)])

    TESTS.append([{"spatial_size": [15, 4, -1], "method": "symmetric", "mode": mode}, (3, 8, 8, 4), (3, 15, 8, 4)])


class TestSpatialPad(unittest.TestCase):
    @staticmethod
    def get_arr(shape):
        return np.random.randint(100, size=shape).astype(float)

    @parameterized.expand(TESTS)
    def test_pad_shape(self, input_param, input_shape, expected_shape):
        base_comparison = None
        input_data = self.get_arr(input_shape)
        padder = SpatialPad(**input_param)
        # check result is the same regardless of input type
        for p in TEST_NDARRAYS:
            r1 = padder(p(input_data))
            r2 = padder(p(input_data), mode=input_param["mode"])
            # check shape
            np.testing.assert_allclose(r1.shape, expected_shape)
            np.testing.assert_allclose(r2.shape, expected_shape)
            # check results are same regardless of input type
            if base_comparison is None:
                base_comparison = r1
            torch.testing.assert_allclose(r1, base_comparison, atol=0, rtol=1e-5)
            torch.testing.assert_allclose(r2, base_comparison, atol=0, rtol=1e-5)
            # test inverse
            for r in (r1, r2):
                if isinstance(r, MetaTensor):
                    r = padder.inverse(r)
                    self.assertIsInstance(r, MetaTensor)
                    assert_allclose(r, input_data, type_test=False)
                    self.assertEqual(r.applied_operations, [])

    def test_pad_kwargs(self):
        for p in TEST_NDARRAYS:
            im = p(np.zeros((3, 8, 4)))
            kwargs = {"value": 2} if isinstance(im, torch.Tensor) else {"constant_values": ((0, 0), (1, 1), (2, 2))}
            padder = SpatialPad(spatial_size=[15, 8], method="end", mode="constant", **kwargs)
            result = padder(im)
            if isinstance(result, torch.Tensor):
                result = result.cpu()
            # central section should remain unchanged
            assert_allclose(result[:, :8, :4], im, type_test=False)
            expected_vals = [0, 2] if isinstance(im, torch.Tensor) else [0, 1, 2]
            assert_allclose(np.unique(result), expected_vals, type_test=False)
            # check inverse
            if isinstance(result, MetaTensor):
                inv = padder.inverse(result)
                assert_allclose(im, inv, type_test=False)
                self.assertEqual(inv.applied_operations, [])


if __name__ == "__main__":
    unittest.main()
