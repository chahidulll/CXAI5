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

from monai.utils import exact_version, optional_import


class TestOptionalImport(unittest.TestCase):
    def test_default(self):
        my_module, flag = optional_import("not_a_module")
        self.assertFalse(flag)
        with self.assertRaises(AttributeError):
            my_module.test

        my_module, flag = optional_import("torch.randint")
        with self.assertRaises(AttributeError):
            self.assertFalse(flag)
            print(my_module.test)

    def test_import_valid(self):
        my_module, flag = optional_import("torch")
        self.assertTrue(flag)
        print(my_module.randint(1, 2, (1, 2)))

    def test_import_wrong_number(self):
        my_module, flag = optional_import("torch", "42")
        with self.assertRaisesRegex(AttributeError, "version"):
            my_module.nn
        self.assertFalse(flag)
        with self.assertRaisesRegex(AttributeError, "version"):
            my_module.randint(1, 2, (1, 2))

    def test_import_good_number(self):
        my_module, flag = optional_import("torch", "0")
        my_module.nn
        self.assertTrue(flag)
        print(my_module.randint(1, 2, (1, 2)))

        my_module, flag = optional_import("torch", "0.0.0.1")
        my_module.nn
        self.assertTrue(flag)
        print(my_module.randint(1, 2, (1, 2)))

        my_module, flag = optional_import("torch", "1.1.0")
        my_module.nn
        self.assertTrue(flag)
        print(my_module.randint(1, 2, (1, 2)))

    def test_import_exact(self):
        my_module, flag = optional_import("torch", "0", exact_version)
        with self.assertRaisesRegex(AttributeError, "exact_version"):
            my_module.nn
        self.assertFalse(flag)
        with self.assertRaisesRegex(AttributeError, "exact_version"):
            my_module.randint(1, 2, (1, 2))

    def test_import_method(self):
        nn, flag = optional_import("torch", "1.1", name="nn")
        self.assertTrue(flag)
        print(nn.functional)


if __name__ == "__main__":
    unittest.main()
