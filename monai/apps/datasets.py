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
import sys
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

import numpy as np

from monai.apps.utils import download_and_extract, split_dataset
from monai.data import CacheDataset, load_decathlon_datalist, load_decathlon_properties
from monai.transforms import LoadNiftid, LoadPNGd, Randomizable
from monai.utils import ensure_tuple


class MedNISTDataset(Randomizable, CacheDataset):
    """
    The Dataset to automatically download MedNIST data and generate items for training, validation or test.
    It's based on `CacheDataset` to accelerate the training process.

    Args:
        root_dir: target directory to download and load MedNIST dataset.
        section: expected data section, can be: `training`, `validation` or `test`.
        transform: transforms to execute operations on input data. the default transform is `LoadPNGd`,
            which can load data into numpy array with [H, W] shape. for further usage, use `AddChanneld`
            to convert the shape to [C, H, W, D].
        download: whether to download and extract the MedNIST from resource link, default is False.
            if expected file already exists, skip downloading even set it to True.
            user can manually copy `MedNIST.tar.gz` file or `MedNIST` folder to root directory.
        seed: random seed to randomly split training, validation and test datasets, default is 0.
        val_frac: percentage of of validation fraction in the whole dataset, default is 0.1.
        test_frac: percentage of of test fraction in the whole dataset, default is 0.1.
        cache_num: number of items to be cached. Default is `sys.maxsize`.
            will take the minimum of (cache_num, data_length x cache_rate, data_length).
        cache_rate: percentage of cached data in total, default is 1.0 (cache all).
            will take the minimum of (cache_num, data_length x cache_rate, data_length).
        num_workers: the number of worker threads to use.
            if 0 a single thread will be used. Default is 0.

    Raises:
        ValueError: When ``root_dir`` is not a directory.
        RuntimeError: When ``dataset_dir`` doesn't exist and downloading is not selected (``download=False``).

    """

    resource = "https://www.dropbox.com/s/5wwskxctvcxiuea/MedNIST.tar.gz?dl=1"
    md5 = "0bc7306e7427e00ad1c5526a6677552d"
    compressed_file_name = "MedNIST.tar.gz"
    dataset_folder_name = "MedNIST"

    def __init__(
        self,
        root_dir: str,
        section: str,
        transform: Union[Sequence[Callable], Callable] = LoadPNGd("image"),
        download: bool = False,
        seed: int = 0,
        val_frac: float = 0.1,
        test_frac: float = 0.1,
        cache_num: int = sys.maxsize,
        cache_rate: float = 1.0,
        num_workers: int = 0,
    ) -> None:
        if not os.path.isdir(root_dir):
            raise ValueError("Root directory root_dir must be a directory.")
        self.section = section
        self.val_frac = val_frac
        self.test_frac = test_frac
        self.set_random_state(seed=seed)
        tarfile_name = os.path.join(root_dir, self.compressed_file_name)
        dataset_dir = os.path.join(root_dir, self.dataset_folder_name)
        if download:
            download_and_extract(self.resource, tarfile_name, root_dir, self.md5)

        if not os.path.exists(dataset_dir):
            raise RuntimeError(
                f"Cannot find dataset directory: {dataset_dir}, please use download=True to download it."
            )
        data = self._generate_data_list(dataset_dir)
        super().__init__(data, transform, cache_num=cache_num, cache_rate=cache_rate, num_workers=num_workers)

    def randomize(self, data: Optional[Any] = None) -> None:
        self.rann = self.R.random()

    def _generate_data_list(self, dataset_dir: str) -> List[Dict]:
        """
        Raises:
            ValueError: When ``section`` is not one of ["training", "validation", "test"].

        """
        class_names = sorted((x for x in os.listdir(dataset_dir) if os.path.isdir(os.path.join(dataset_dir, x))))
        num_class = len(class_names)
        image_files = [
            [
                os.path.join(dataset_dir, class_names[i], x)
                for x in os.listdir(os.path.join(dataset_dir, class_names[i]))
            ]
            for i in range(num_class)
        ]
        num_each = [len(image_files[i]) for i in range(num_class)]
        image_files_list = []
        image_class = []
        for i in range(num_class):
            image_files_list.extend(image_files[i])
            image_class.extend([i] * num_each[i])
        num_total = len(image_class)

        data = list()

        for i in range(num_total):
            self.randomize()
            if self.section == "training":
                if self.rann < self.val_frac + self.test_frac:
                    continue
            elif self.section == "validation":
                if self.rann >= self.val_frac:
                    continue
            elif self.section == "test":
                if self.rann < self.val_frac or self.rann >= self.val_frac + self.test_frac:
                    continue
            else:
                raise ValueError(
                    f'Unsupported section: {self.section}, available options are ["training", "validation", "test"].'
                )
            data.append({"image": image_files_list[i], "label": image_class[i]})
        return data


class DecathlonDataset(Randomizable, CacheDataset):
    """
    The Dataset to automatically download the data of Medical Segmentation Decathlon challenge
    (http://medicaldecathlon.com/) and generate items for training, validation or test.
    It will also load these properties from the JSON config file of dataset. user can call `get_properties()`
    to get specified properties or all the properties loaded.
    It's based on :py:class:`monai.data.CacheDataset` to accelerate the training process.

    Args:
        root_dir: user's local directory for caching and loading the MSD datasets.
        task: which task to download and execute: one of list ("Task01_BrainTumour", "Task02_Heart",
            "Task03_Liver", "Task04_Hippocampus", "Task05_Prostate", "Task06_Lung", "Task07_Pancreas",
            "Task08_HepaticVessel", "Task09_Spleen", "Task10_Colon").
        section: expected data section, can be: `training`, `validation` or `test`.
        transform: transforms to execute operations on input data. the default transform is `LoadNiftid`,
            which can load Nifti format data into numpy array with [H, W, D] or [H, W, D, C] shape.
            for further usage, use `AddChanneld` or `AsChannelFirstd` to convert the shape to [C, H, W, D].
        download: whether to download and extract the Decathlon from resource link, default is False.
            if expected file already exists, skip downloading even set it to True.
            user can manually copy tar file or dataset folder to the root directory.
        seed: random seed to randomly split `training`, `validation` and `test` datasets, default is 0.
        nsplits: number of folds, split the training data into N folds. each fold is then used once as a
            validation while the N - 1 remaining folds form the training set.
            Decathlon data only contains `training` section with labels and `test` section without labels,
            so randomly select fraction from the `training` section as the `validation` section.
            if set `nsplits = 1`, will not split 
        fold: index of fold for training and validation, default is 0.
        cache_num: number of items to be cached. Default is `sys.maxsize`.
            will take the minimum of (cache_num, data_length x cache_rate, data_length).
        cache_rate: percentage of cached data in total, default is 1.0 (cache all).
            will take the minimum of (cache_num, data_length x cache_rate, data_length).
        num_workers: the number of worker threads to use.
            if 0 a single thread will be used. Default is 0.

    Raises:
        ValueError: When ``root_dir`` is not a directory.
        ValueError: When ``task`` is not one of ["Task01_BrainTumour", "Task02_Heart",
            "Task03_Liver", "Task04_Hippocampus", "Task05_Prostate", "Task06_Lung", "Task07_Pancreas",
            "Task08_HepaticVessel", "Task09_Spleen", "Task10_Colon"].
        RuntimeError: When ``dataset_dir`` doesn't exist and downloading is not selected (``download=False``).

    Example::

        transform = Compose(
            [
                LoadNiftid(keys=["image", "label"]),
                AddChanneld(keys=["image", "label"]),
                ScaleIntensityd(keys="image"),
                ToTensord(keys=["image", "label"]),
            ]
        )

        data = DecathlonDataset(
            root_dir="./", task="Task09_Spleen", transform=transform, section="validation", download=True
        )

        print(data[0]["image"], data[0]["label"])

    """

    resource = {
        "Task01_BrainTumour": "https://msd-for-monai.s3-us-west-2.amazonaws.com/Task01_BrainTumour.tar",
        "Task02_Heart": "https://msd-for-monai.s3-us-west-2.amazonaws.com/Task02_Heart.tar",
        "Task03_Liver": "https://msd-for-monai.s3-us-west-2.amazonaws.com/Task03_Liver.tar",
        "Task04_Hippocampus": "https://msd-for-monai.s3-us-west-2.amazonaws.com/Task04_Hippocampus.tar",
        "Task05_Prostate": "https://msd-for-monai.s3-us-west-2.amazonaws.com/Task05_Prostate.tar",
        "Task06_Lung": "https://msd-for-monai.s3-us-west-2.amazonaws.com/Task06_Lung.tar",
        "Task07_Pancreas": "https://msd-for-monai.s3-us-west-2.amazonaws.com/Task07_Pancreas.tar",
        "Task08_HepaticVessel": "https://msd-for-monai.s3-us-west-2.amazonaws.com/Task08_HepaticVessel.tar",
        "Task09_Spleen": "https://msd-for-monai.s3-us-west-2.amazonaws.com/Task09_Spleen.tar",
        "Task10_Colon": "https://msd-for-monai.s3-us-west-2.amazonaws.com/Task10_Colon.tar",
    }
    md5 = {
        "Task01_BrainTumour": "240a19d752f0d9e9101544901065d872",
        "Task02_Heart": "06ee59366e1e5124267b774dbd654057",
        "Task03_Liver": "a90ec6c4aa7f6a3d087205e23d4e6397",
        "Task04_Hippocampus": "9d24dba78a72977dbd1d2e110310f31b",
        "Task05_Prostate": "35138f08b1efaef89d7424d2bcc928db",
        "Task06_Lung": "8afd997733c7fc0432f71255ba4e52dc",
        "Task07_Pancreas": "4f7080cfca169fa8066d17ce6eb061e4",
        "Task08_HepaticVessel": "641d79e80ec66453921d997fbf12a29c",
        "Task09_Spleen": "410d4a301da4e5b2f6f86ec3ddba524e",
        "Task10_Colon": "bad7a188931dc2f6acf72b08eb6202d0",
    }

    def __init__(
        self,
        root_dir: str,
        task: str,
        section: str,
        transform: Union[Sequence[Callable], Callable] = LoadNiftid(["image", "label"]),
        download: bool = False,
        seed: int = 0,
        nsplits: int = 5,
        fold: int = 0,
        cache_num: int = sys.maxsize,
        cache_rate: float = 1.0,
        num_workers: int = 0,
    ) -> None:
        if not os.path.isdir(root_dir):
            raise ValueError("Root directory root_dir must be a directory.")
        self.section = section
        self.nsplits = nsplits
        if fold > nsplits - 1:
            raise ValueError("fold index should be in [0, nsplit - 1].")
        self.fold = fold
        self.set_random_state(seed=seed)
        if task not in self.resource:
            raise ValueError(f"Unsupported task: {task}, available options are: {list(self.resource.keys())}.")
        dataset_dir = os.path.join(root_dir, task)
        tarfile_name = f"{dataset_dir}.tar"
        if download:
            download_and_extract(self.resource[task], tarfile_name, root_dir, self.md5[task])

        if not os.path.exists(dataset_dir):
            raise RuntimeError(
                f"Cannot find dataset directory: {dataset_dir}, please use download=True to download it."
            )
        data = self._generate_data_list(dataset_dir)
        # as `release` key has typo in Task04 config file, ignore it.
        property_keys = [
            "name",
            "description",
            "reference",
            "licence",
            "tensorImageSize",
            "modality",
            "labels",
            "numTraining",
            "numTest",
        ]
        self._properties = load_decathlon_properties(os.path.join(dataset_dir, "dataset.json"), property_keys)
        super().__init__(data, transform, cache_num=cache_num, cache_rate=cache_rate, num_workers=num_workers)

    def randomize(self, data: List[int]) -> None:
        self.R.shuffle(data)

    def get_properties(self, keys: Optional[Union[Sequence[str], str]] = None):
        """
        Get the loaded properties of dataset with specified keys.
        If no keys specified, return all the loaded properties.

        """
        if keys is None:
            return self._properties
        elif self._properties is not None:
            return {key: self._properties[key] for key in ensure_tuple(keys)}
        else:
            return {}

    def _generate_data_list(self, dataset_dir: str) -> List[Dict]:
        section = "training" if self.section in ["training", "validation"] else "test"
        datalist = load_decathlon_datalist(os.path.join(dataset_dir, "dataset.json"), True, section)
        return self._split_datalist(datalist)

    def _split_datalist(self, datalist: List[Dict]) -> List[Dict]:
        if self.section == "test":
            return datalist
        else:
            length = len(datalist)
            indices = np.arange(length)
            self.randomize(indices)
            if self.nsplits > 1:
                fold_indices = split_dataset(self.nsplits, length)
                if self.section == "training":
                    indices = np.delete(indices, np.s_[fold_indices[self.fold][0] : fold_indices[self.fold][1]], axis=None)
                else:
                    indices = indices[fold_indices[self.fold][0] : fold_indices[self.fold][1]]
            else:
                if self.section == "validation":
                    raise ValueError("if nplits is 1, will not generate datalist for validation.")
            return [datalist[i] for i in indices]
