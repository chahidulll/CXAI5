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
import os
import shutil
import tempfile

from monai.application import MedNISTDataset
from tests.utils import NumpyImageTestCase2D
from monai.transforms import LoadPNGd, AddChanneld, ScaleIntensityd, ToTensord, Compose


class TestMedNISTDataset(unittest.TestCase):
    def test_values(self):
        tempdir = tempfile.mkdtemp()
        transform = Compose([
            LoadPNGd(keys="image"),
            AddChanneld(keys="image"),
            ScaleIntensityd(keys="image"),
            ToTensord(keys=["image", "label"])
        ])
        dataset = MedNISTDataset(root=tempdir, transform=transform, section="test", download=True)
        self.assertEqual(len(dataset), 5986)
        self.assertTrue("image" in dataset[0])
        self.assertTrue("label" in dataset[0])
        self.assertTrue("image_meta_dict" in dataset[0])
        self.assertTupleEqual(dataset[0]["image"].shape, (1, 64, 64))
        shutil.rmtree(tempdir)


if __name__ == "__main__":
    unittest.main()
