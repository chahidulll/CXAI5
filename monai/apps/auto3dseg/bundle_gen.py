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

import importlib
import os
import shutil
import subprocess
import sys
from copy import copy, deepcopy
from glob import glob
from tempfile import TemporaryDirectory
from typing import Any, Dict, List, Mapping
from warnings import warn

import torch

from monai.apps import download_and_extract
from monai.apps.utils import get_logger
from monai.auto3dseg.algo_gen import Algo, AlgoGen
from monai.bundle.config_parser import ConfigParser
from monai.utils import ensure_tuple

logger = get_logger(module_name=__name__)

__all__ = ["BundleAlgo", "BundleGen"]


class BundleAlgo(Algo):
    """
    An algorithm represented by a set of bundle configurations and scripts.

    ``BundleAlgo.cfg`` is a ``monai.bundle.ConfigParser`` instance.

    ..code-block:: python

        from monai.apps.auto3dseg import BundleAlgo

        data_stats_yaml = "/workspace/data_stats.yaml"
        algo = BundleAlgo(
            template_configs=../algorithms/templates/segresnet2d/configs,
            scripts_path="../algorithms/templates/segresnet2d/scripts")
        algo.set_data_stats(data_stats_yaml)
        # algo.set_data_src("../data_src.json")
        algo.export_to_disk(".", algo_name="segresnet2d_1")

    This class creates MONAI bundles from a directory of 'bundle template'. Different from the regular MONAI bundle
    format, the bundle template may contain placeholders that must be filled using ``fill_template_config`` during
    ``export_to_disk``.  The output of ``export_to_disk`` takes the following folder structure::

        [algo_name]
        ├── configs
        │   └── algo_config.yaml  # automatically generated yaml from a set of ``template_configs``
        └── scripts
            ├── algo.py
            ├── infer.py
            ├── train.py
            └── validate.py

    """

    def __init__(self, template_configs=None, scripts_path=None, meta_data_filename=None, parser_args=None):
        """
        Create an Algo instance based on a set of bundle configuration templates and scripts.

        Args:
            template_configs: a json/yaml config file, or a folder of json/yaml files.
            scripts_path: a folder to python script files.
            meta_data_filename: optional metadata of a MONAI bundle.
            parser_args: additional input arguments for the build-in ConfigParser ``self.cfg.read_config``.
        """
        if os.path.isdir(template_configs):
            self.template_configs = []
            for ext in ("json", "yaml"):
                self.template_configs += glob(os.path.join(template_configs, f"*.{ext}"))
        else:
            self.template_configs = template_configs
        self.meta_data_filename = meta_data_filename
        self.cfg = ConfigParser(globals=False)  # TODO: define root folder (variable)?
        if self.template_configs is not None:
            self.load_templates(self.template_configs, meta_data_filename, parser_args)

        self.scripts_path = scripts_path
        self.data_stats_files = None
        self.data_list_file = None
        self.output_path = None
        self.name = None
        self.best_metric = None

    def load_templates(self, config_files, metadata_file=None, parser_args=None):
        """
        Read a list of template configuration files

        Args:
            config_file: bundle config files.
            metadata_file: metadata overriding file
            parser_args: argument to parse

        """
        parser_args = parser_args or {}
        self.cfg.read_config(config_files, **parser_args)
        if metadata_file is not None:
            self.cfg.read_meta(metadata_file)

    def set_data_stats(self, data_stats_files: str):  # type: ignore
        """
        Set the data anlysis report (generated by DataAnalyzer).

        Args:
            data_stats_files: path to the datastats yaml file
        """
        self.data_stats_files = data_stats_files

    def set_data_source(self, data_list_file: str):
        """
        Set the data source configuration file

        Args:
            data_list_file: path to a configuration file (yaml) that contains datalist, dataroot, and other params.
        """
        self.data_list_file = data_list_file

    def fill_template_config(self, data_stats_filename, **kwargs):
        """
        The configuration files defined when constructing this Algo instance might not have a complete training
        and validation pipelines. Some configuration components and hyperparameters of the pipelines depend on the
        training data and other factors. This API is provided to allow the creation of fully functioning config files.

        Args:
            data_stats_filename: filename of the data stats report (generated by DataAnalyzer)
        """
        pass

    def export_to_disk(self, output_path: str, algo_name: str, **kwargs):
        """
        Fill the configuration templates, write the bundle (configs + scripts) to folder `output_path/algo_name`.

        Args:
            output_path: Path to export the 'scripts' and 'configs' directories.
            algo_name: the identifier of the algorithm (usually contains the name and extra info like fold ID).
        """
        self.fill_template_config(self.data_stats_files, **kwargs)
        write_path = os.path.join(output_path, algo_name)
        self.cfg["bundle_root"] = write_path
        os.makedirs(write_path, exist_ok=True)
        # handling scripts files
        output_scripts_path = os.path.join(write_path, "scripts")
        if os.path.exists(output_scripts_path):
            # TODO: use future metadata.json to create backups
            shutil.rmtree(output_scripts_path)
        if self.scripts_path is not None and os.path.exists(self.scripts_path):
            shutil.copytree(self.scripts_path, output_scripts_path)
        # handling config files
        output_config_path = os.path.join(write_path, "configs")
        if os.path.exists(output_config_path):
            # TODO: use future metadata.json to create backups
            shutil.rmtree(output_config_path)
        
        # break the config into multiple files and save
        subsections = ['network', 'transforms_infer', 'transforms_train', 'transforms_validate']
        self.save_config_files(output_config_path, subsections)
        logger.info(write_path)
        self.output_path = write_path
        

    def save_config_files(self, output_config_path, subsections):
        """
        Save the auto-generated config files into multiple files. 

        Args:
            output_config_path: path to save the files
            subsections: the subsections that will be picked up and individually saved.

        """
        os.makedirs(output_config_path, exist_ok=True)
        output_config_file = os.path.join(output_config_path, "algo_config.yaml")
        ConfigParser.export_config_file(self.cfg.config, output_config_file, fmt="yaml", default_flow_style=None)
        with open(output_config_file, "r+") as f:
            lines = f.readlines()
            f.seek(0)
            f.write(f"# Generated automatically by `{__name__}`\n")
            f.write("# For more information please visit: https://docs.monai.io/\n\n")
            for item in ensure_tuple(self.template_configs):
                f.write(f"# source file: {item}\n")
            f.write("\n\n")
            f.writelines(lines)


    def train(self, train_params=None):
        """
        Load the run function in the training script of each model. Training parameter is predefined by the
        algo_config.yaml file, which is pre-filled by the fill_template_config function in the same instance.

        Args:
            train_params:  to specify the devices using a list of integers: ``{"CUDA_VISIBLE_DEVICES": [1,2,3]}``.
        """
        if train_params is not None:
            params = deepcopy(train_params)

        train_py = os.path.join(self.output_path, "scripts", "train.py")
        config_yaml = os.path.join(self.output_path, "configs", "algo_config.yaml")
        base_cmd = f"{train_py} run --config_file={config_yaml} "

        if "CUDA_VISIBLE_DEVICES" in params:
            devices = params.pop("CUDA_VISIBLE_DEVICES")
            n_devices, devices_str = len(devices), ",".join([str(x) for x in devices])
        else:
            n_devices, devices_str = torch.cuda.device_count(), ""
        if n_devices > 1:
            cmd = f"torchrun --nnodes={1:d} --nproc_per_node={n_devices:d} "
        else:
            cmd = "python "  # TODO: which system python?
        cmd += base_cmd
        if params and isinstance(params, Mapping):
            for k, v in params.items():
                cmd += f" --{k}={v}"
        try:
            logger.info(f"Launching: {cmd}")
            ps_environ = os.environ.copy()
            if devices_str:
                ps_environ["CUDA_VISIBLE_DEVICES"] = devices_str
            normal_out = subprocess.run(cmd.split(), env=ps_environ, check=True, capture_output=True)
            logger.info(repr(normal_out).replace("\\n", "\n").replace("\\t", "\t"))
        except subprocess.CalledProcessError as e:
            output = repr(e.stdout).replace("\\n", "\n").replace("\\t", "\t")
            errors = repr(e.stderr).replace("\\n", "\n").replace("\\t", "\t")
            raise RuntimeError(f"subprocess call error {e.returncode}: {errors}, {output}") from e
        return normal_out

    def get_score(self, *args, **kwargs):
        """
        Returns validation scores of the model trained by the current Algo.
        """
        config_yaml = os.path.join(self.output_path, "configs", "algo_config.yaml")
        parser = ConfigParser()
        parser.read_config(config_yaml)
        ckpt_path = parser.get_parsed_content("ckpt_path", default=self.output_path)

        dict_file = ConfigParser.load_config_file(os.path.join(ckpt_path, "progress.yaml"))
        return dict_file["best_avg_dice_score"]  # TODO: define the format of best scores' list and progress.yaml

    def get_inferer(self, *args, **kwargs):
        """
        Load the InferClass from the infer.py
        """
        infer_py = os.path.join(self.output_path, "scripts", "infer.py")
        if not os.path.isfile(infer_py):
            raise ValueError(f"{infer_py} is not found, please check the path.")
        config_path = os.path.join(self.output_path, "configs", "algo_config.yaml")
        config_path = config_path if os.path.isfile(config_path) else None
        logger.info(f"in memory or persistent predictions using {config_path}.")
        spec = importlib.util.spec_from_file_location("InferClass", infer_py)
        infer_class = importlib.util.module_from_spec(spec)
        sys.modules["InferClass"] = infer_class
        spec.loader.exec_module(infer_class)
        return infer_class.InferClass(config_path, *args, **kwargs)

    def predict(self, predict_params=None):
        """
        Use the trained model to predict the outputs with a given input image. Path to input image is in the params
        dict in a form of {"files", ["path_to_image_1", "path_to_image_2"]}. If it is not specified, then the pre-
        diction will use the test images predefined in the bundle config.

        Args:
            predict_params: a dict to override the parameters in the bundle config (including the files to predict).

        """
        if predict_params is None:
            params = {}
        else:
            params = deepcopy(predict_params)

        files = params.pop("files", ".")
        inferer = self.get_inferer(**params)
        return [inferer.infer(f) for f in ensure_tuple(files)]


# path to download the algo_templates
algo_zip = "https://github.com/Project-MONAI/MONAI-extra-test-data/releases/download/0.8.1/algo_templates.tar.gz"

md5 = "c671dcd525a736f083ac1ca3d23a86dc"

# default algorithms
default_algos = {
    "unet": dict(
        _target_="unet.scripts.algo.UnetAlgo",
        template_configs="algo_templates/unet/configs",
        scripts_path="algo_templates/unet/scripts",
    ),
    "segresnet2d": dict(
        _target_="segresnet2d.scripts.algo.Segresnet2DAlgo",
        template_configs="algo_templates/segresnet2d/configs",
        scripts_path="algo_templates/segresnet2d/scripts",
    ),
    "dints": dict(
        _target_="dints.scripts.algo.DintsAlgo",
        template_configs="algo_templates/dints/configs",
        scripts_path="algo_templates/dints/scripts",
    ),
    "SwinUNETR": dict(
        _target_="SwinUNETR.scripts.algo.SwinUNETRAlgo",
        template_configs="algo_templates/SwinUNETR/configs",
        scripts_path="algo_templates/SwinUNETR/scripts",
    ),
    "segresnet": dict(
        _target_="segresnet.scripts.algo.SegresnetAlgo",
        template_configs="algo_templates/segresnet/configs",
        scripts_path="algo_templates/segresnet/scripts",
    ),
}


class BundleGen(AlgoGen):
    """
    This class generates a set of bundles according to the cross-validation folds, each of them can run independently.

    Args:
        algo: a dictionary that outlines the algorithm to use.
        algo_path: the directory path to save the algorithm templates. Default is the current working dir.
        data_stats_filename: the path to the data stats file (generated by DataAnalyzer)
        data_src_cfg_name: the path to the data source file, which contains the data list

    .. code-block:: bash

        python -m monai.apps.auto3dseg BundleGen generate --data_stats_filename="../algorithms/data_stats.yaml"
    """

    def __init__(self, algo_path: str = ".", algos=None, data_stats_filename=None, data_src_cfg_name=None):
        self.algos: Any = []

        if algos is None:
            # trigger the download process
            zip_download_dir = TemporaryDirectory()
            algo_compressed_file = os.path.join(zip_download_dir.name, "algo_templates.tar.gz")
            download_and_extract(algo_zip, algo_compressed_file, algo_path, md5)
            zip_download_dir.cleanup()
            sys.path.insert(0, os.path.join(algo_path, "algo_templates"))
            algos = copy(default_algos)
            for name in algos:
                algos[name]["template_configs"] = os.path.join(algo_path, default_algos[name]["template_configs"])
                algos[name]["scripts_path"] = os.path.join(algo_path, default_algos[name]["scripts_path"])

        if isinstance(algos, dict):
            for algo_name, algo_params in algos.items():
                self.algos.append(ConfigParser(algo_params).get_parsed_content())
                self.algos[-1].name = algo_name
        else:
            self.algos = ensure_tuple(algos)

        self.data_stats_filename = data_stats_filename
        self.data_src_cfg_filename = data_src_cfg_name
        self.history: List[Dict] = []

    def set_data_stats(self, data_stats_filename: str):  # type: ignore
        """
        Set the data stats filename

        Args:
            data_stats_filename: filename of datastats
        """
        self.data_stats_filename = data_stats_filename

    def get_data_stats(self):
        """Get the filename of the data stats"""
        return self.data_stats_filename

    def set_data_src(self, data_src_cfg_filename):
        """
        Set the data source filename

        Args:
            data_src_cfg_filename: filename of data_source file
        """
        self.data_src_cfg_filename = data_src_cfg_filename

    def get_data_src(self, fold_idx=0):
        """Get the data source filename"""
        return self.data_src_cfg_filename

    def get_history(self, *args, **kwargs) -> List:
        """get the history of the bundleAlgo object with their names/identifiers"""
        return self.history

    def generate(self, output_folder=".", num_fold: int = 5):
        """
        Generate the bundle scripts/configs for each bundleAlgo

        Args:
            output_folder: the output folder to save each algorithm.
            fold_idx: an index to append to the name of the algorithm to
        """
        fold_idx = list(range(num_fold))
        for algo in self.algos:
            for f_id in ensure_tuple(fold_idx):
                data_stats = self.get_data_stats()
                data_src_cfg = self.get_data_src(fold_idx)
                gen_algo = deepcopy(algo)
                gen_algo.set_data_stats(data_stats)
                gen_algo.set_data_source(data_src_cfg)
                name = f"{gen_algo.name}_{f_id}"
                gen_algo.export_to_disk(output_folder, name, fold=f_id)
                self.history.append({name: gen_algo})  # track the previous, may create a persistent history
