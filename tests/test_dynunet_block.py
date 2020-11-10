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

import unittest

import torch
from parameterized import parameterized

from monai.networks.blocks.dynunet_block import UnetBasicBlock, UnetResBlock, UnetUpBlock, get_padding

TEST_CASE_RES_BASIC_BLOCK = []
for spatial_dims in range(2, 4):
    for kernel_size in [1, 3]:
        for stride in [1, 2]:
            for norm_name in ["group", "batch", "instance"]:
                for in_size in [15, 16]:
                    padding = get_padding(kernel_size, stride)
                    if not isinstance(padding, int):
                        padding = padding[0]
                    out_size = int((in_size + 2 * padding - kernel_size) / stride) + 1
                    test_case = [
                        {
                            "spatial_dims": spatial_dims,
                            "in_channels": 16,
                            "out_channels": 16,
                            "kernel_size": kernel_size,
                            "norm_name": norm_name,
                            "stride": stride,
                        },
                        (1, 16, *([in_size] * spatial_dims)),
                        (1, 16, *([out_size] * spatial_dims)),
                    ]
                    TEST_CASE_RES_BASIC_BLOCK.append(test_case)

TEST_UP_BLOCK = []
in_channels, out_channels = 4, 2
for spatial_dims in range(2, 4):
    for kernel_size in [1, 3]:
        for stride in [1, 2]:
            for norm_name in ["batch", "instance"]:
                for in_size in [15, 16]:
                    out_size = in_size * stride
                    test_case = [
                        {
                            "spatial_dims": spatial_dims,
                            "in_channels": in_channels,
                            "out_channels": out_channels,
                            "kernel_size": kernel_size,
                            "norm_name": norm_name,
                            "stride": stride,
                            "upsample_kernel_size": stride,
                        },
                        (1, in_channels, *([in_size] * spatial_dims)),
                        (1, out_channels, *([out_size] * spatial_dims)),
                        (1, out_channels, *([in_size * stride] * spatial_dims)),
                    ]
                    TEST_UP_BLOCK.append(test_case)


class TestResBasicBlock(unittest.TestCase):
    @parameterized.expand(TEST_CASE_RES_BASIC_BLOCK)
    def test_shape(self, input_param, input_shape, expected_shape):
        for net in [UnetResBlock(**input_param), UnetBasicBlock(**input_param)]:
            net.eval()
            with torch.no_grad():
                result = net(torch.randn(input_shape))
                self.assertEqual(result.shape, expected_shape)

    def test_ill_arg(self):
        with self.assertRaises(ValueError):
            UnetBasicBlock(3, 4, 2, kernel_size=3, stride=1, norm_name="norm")
        with self.assertRaises(AssertionError):
            UnetResBlock(3, 4, 2, kernel_size=1, stride=4, norm_name="batch")


class TestUpBlock(unittest.TestCase):
    @parameterized.expand(TEST_UP_BLOCK)
    def test_shape(self, input_param, input_shape, expected_shape, skip_shape):
        net = UnetUpBlock(**input_param)
        net.eval()
        with torch.no_grad():
            result = net(torch.randn(input_shape), torch.randn(skip_shape))
            self.assertEqual(result.shape, expected_shape)


if __name__ == "__main__":
    unittest.main()
