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
import unittest

import numpy as np
import torch
from parameterized import parameterized

from monai.losses import DiceLoss
from monai.losses.multi_scale import MultiScaleLoss

dice_loss = DiceLoss(include_background=True, sigmoid=True, smooth_nr=1e-5, smooth_dr=1e-5)

TEST_CASES = [
    [
        {"loss": dice_loss, "scales": None, "kernel": "gaussian"},
        {"y_pred": torch.tensor([[[[1.0, -1.0], [-1.0, 1.0]]]]), "y_true": torch.tensor([[[[1.0, 0.0], [1.0, 1.0]]]])},
        0.307576,
    ],
    [
        {"loss": dice_loss, "scales": [0, 1], "kernel": "gaussian"},
        {"y_pred": torch.tensor([[[[1.0, -1.0], [-1.0, 1.0]]]]), "y_true": torch.tensor([[[[1.0, 0.0], [1.0, 1.0]]]])},
        0.463116,
    ],
    [
        {"loss": dice_loss, "scales": [0, 1, 2], "kernel": "cauchy"},
        {
            "y_pred": torch.tensor([[[[[1.0, -1.0], [-1.0, 1.0]]]]]),
            "y_true": torch.tensor([[[[[1.0, 0.0], [1.0, 1.0]]]]]),
        },
        0.715228,
    ],
]


class TestMultiScale(unittest.TestCase):
    @parameterized.expand(TEST_CASES)
    def test_shape(self, input_param, input_data, expected_val):
        result = MultiScaleLoss(**input_param).forward(**input_data)
        np.testing.assert_allclose(result.detach().cpu().numpy(), expected_val, rtol=1e-5)

    def test_ill_opts(self):
        with self.assertRaisesRegex(ValueError, ""):
            MultiScaleLoss(loss=dice_loss, kernel="none")
        with self.assertRaisesRegex(ValueError, ""):
            MultiScaleLoss(loss=dice_loss, scales=[-1])(torch.ones((1, 1, 3)), torch.ones((1, 1, 3)))
        with self.assertRaisesRegex(ValueError, ""):
            MultiScaleLoss(loss=dice_loss, scales=[-1], reduction="none")(torch.ones((1, 1, 3)), torch.ones((1, 1, 3)))


if __name__ == "__main__":
    unittest.main()
