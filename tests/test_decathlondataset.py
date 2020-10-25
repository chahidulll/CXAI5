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

import os
import shutil
import unittest
from urllib.error import ContentTooShortError, HTTPError

from monai.apps import DecathlonDataset
from monai.transforms import AddChanneld, Compose, LoadNiftid, ScaleIntensityd, ToTensord
from tests.utils import skip_if_quick


class TestDecathlonDataset(unittest.TestCase):
    @skip_if_quick
    def test_values(self):
        testing_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "testing_data")
        transform = Compose(
            [
                LoadNiftid(keys=["image", "label"]),
                AddChanneld(keys=["image", "label"]),
                ScaleIntensityd(keys="image"),
                ToTensord(keys=["image", "label"]),
            ]
        )

        def _test_dataset(dataset):
            self.assertEqual(len(dataset), 52)
            self.assertTrue("image" in dataset[0])
            self.assertTrue("label" in dataset[0])
            self.assertTrue("image_meta_dict" in dataset[0])
            self.assertTupleEqual(dataset[0]["image"].shape, (1, 36, 47, 44))

        try:  # will start downloading if testing_dir doesn't have the Decathlon files
            data = DecathlonDataset(
                root_dir=testing_dir,
                task="Task04_Hippocampus",
                transform=transform,
                section="validation",
                download=True,
            )
        except (ContentTooShortError, HTTPError, RuntimeError) as e:
            print(str(e))
            if isinstance(e, RuntimeError):
                # FIXME: skip MD5 check as current downloading method may fail
                self.assertTrue(str(e).startswith("md5 check"))
            return  # skipping this test due the network connection errors

        _test_dataset(data)
        data = DecathlonDataset(
            root_dir=testing_dir, task="Task04_Hippocampus", transform=transform, section="validation", download=False
        )
        _test_dataset(data)
        # test validation without transforms
        data = DecathlonDataset(root_dir=testing_dir, task="Task04_Hippocampus", section="validation", download=False)
        self.assertTupleEqual(data[0]["image"].shape, (36, 47, 44))
        self.assertEqual(len(data), 52)
        data = DecathlonDataset(root_dir=testing_dir, task="Task04_Hippocampus", section="training", download=False)
        self.assertTupleEqual(data[0]["image"].shape, (34, 56, 31))
        self.assertEqual(len(data), 208)

        # test dataset properties
        data = DecathlonDataset(
            root_dir=testing_dir,
            task="Task04_Hippocampus",
            section="validation",
            download=False,
        )
        properties = data.get_properties(keys="labels")
        self.assertDictEqual(properties["labels"], {"0": "background", "1": "Anterior", "2": "Posterior"})

        shutil.rmtree(os.path.join(testing_dir, "Task04_Hippocampus"))
        try:
            data = DecathlonDataset(
                root_dir=testing_dir,
                task="Task04_Hippocampus",
                transform=transform,
                section="validation",
                download=False,
            )
        except RuntimeError as e:
            print(str(e))
            self.assertTrue(str(e).startswith("Cannot find dataset directory"))


if __name__ == "__main__":
    unittest.main()
