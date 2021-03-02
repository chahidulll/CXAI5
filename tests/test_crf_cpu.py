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

import numpy as np
import torch
from parameterized import parameterized

from monai.networks.blocks import CRF
from tests.utils import skip_if_no_cpp_extention

TEST_CASES = [
    [
        # Case Description
        "2 batche(s), 1 dimension(s), 2 classe(s), 1 channel(s)",
        # Parameters
        [
            3.0, # bilateral_weight
            1.0, # gaussian_weight
            5.0, # bilateral_spatial_sigma
            0.5, # bilateral_color_sigma
            5.0, # gaussian_spatial_sigma
            1, # compatability_kernel_range
            5, # iterations
        ],
        # Input
        [
            # Batch 0
            [
                # Class 0
                [0.8, 0.9, 0.6, 0.2, 0.3],

                # Class 1
                [0.1, 0.3, 0.5, 0.8, 0.7]
            ],
            # Batch 1
            [
                # Class 0
                [0.8, 0.9, 0.6, 0.2, 0.3],

                # Class 1
                [0.1, 0.3, 0.5, 0.8, 0.7]
            ],
        ],
        # Features
        [
            # Batch 0
            [
                # Channel 0
                [1, 1, 1, 0.5, 0],
            ],
            # Batch 1
            [
                # Channel 0
                [1, 1, 0.5, 0, 0],
            ],
        ],
        # Expected
        [
            # Batch 0
            [
                # Class 0
                [0.911299, 0.901745, 0.828803, 0.644988, 0.627997],

                # Class 1
                [0.088701, 0.098255, 0.171197, 0.355012, 0.372003],
            ],
            # Batch 1
            [
                # Class 0
                [0.902577, 0.870105, 0.725821, 0.465292, 0.466282],
                
                # Class 1
                [0.097423, 0.129895, 0.274179, 0.534708, 0.533718]
            ],
        ],
    ],
    [
        # Case Description
        "1 batche(s), 2 dimension(s), 3 classe(s), 2 channel(s)",
        # Parameters
        [
            3.0, # bilateral_weight
            1.0, # gaussian_weight
            5.0, # bilateral_spatial_sigma
            0.5, # bilateral_color_sigma
            5.0, # gaussian_spatial_sigma
            1, # compatability_kernel_range
            5, # iterations
        ],
        # Input
        [
            # Batch 0
            [
                # Class 0
                [
                    [0.0, 0.0, 0.0, 0.0, 0.0],
                    [0.0, 0.0, 0.0, 0.0, 0.0],
                    [0.0, 0.0, 0.0, 0.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0, 1.0],
                    [0.0, 0.0, 0.0, 1.0, 1.0],
                ],

                # Class 1
                [
                    [1.0, 1.0, 0.0, 0.0, 0.0],
                    [1.0, 1.0, 0.0, 0.0, 0.0],
                    [0.0, 0.0, 0.0, 0.0, 0.0],
                    [0.0, 0.0, 0.0, 0.0, 0.0],
                    [0.0, 0.0, 0.0, 0.0, 0.0],
                ],
                
                # Class 2
                [
                    [0.0, 0.0, 0.0, 1.0, 1.0],
                    [0.0, 0.0, 1.0, 1.0, 1.0],
                    [0.0, 1.0, 1.0, 1.0, 0.0],
                    [1.0, 1.0, 1.0, 0.0, 0.0],
                    [1.0, 1.0, 0.0, 0.0, 0.0],
                ],
            ],
        ],
        # Features
        [
            # Batch 0
            [
                # Channel 0
                [
                    [1.0, 1.0, 0.0, 0.0, 0.0],
                    [1.0, 1.0, 0.0, 0.0, 0.0],
                    [0.0, 0.0, 0.0, 0.0, 0.0],
                    [0.0, 0.0, 0.0, 0.0, 0.0],
                    [0.0, 0.0, 0.0, 0.0, 0.0],
                ],

                # Channel 1
                [
                    [0.0, 0.0, 0.0, 0.0, 0.0],
                    [0.0, 0.0, 0.0, 0.0, 0.0],
                    [0.0, 0.0, 0.0, 0.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0, 1.0],
                    [0.0, 0.0, 0.0, 1.0, 1.0],
                ],
            ],
        ],
        # Expected
        [
            # Batch 0
            [
                # Class 0
                [
                    [0.000124, 0.000124, 0.000124, 0.000045, 0.000045],
                    [0.000124, 0.000124, 0.000046, 0.000045, 0.000045],
                    [0.000124, 0.000046, 0.000046, 0.000046, 0.000124],
                    [0.000046, 0.000046, 0.000046, 0.000336, 0.000337],
                    [0.000046, 0.000046, 0.000124, 0.000337, 0.000337]
                ],

                # Class 1
                [
                    [0.000337, 0.000337, 0.000124, 0.000046, 0.000046],
                    [0.000337, 0.000337, 0.000046, 0.000046, 0.000046],
                    [0.000124, 0.000046, 0.000046, 0.000046, 0.000124],
                    [0.000046, 0.000046, 0.000046, 0.000124, 0.000124],
                    [0.000046, 0.000046, 0.000124, 0.000124, 0.000124]
                ],
                
                # Class 2
                [
                    [0.999539, 0.999539, 0.999752, 0.999909, 0.999909],
                    [0.999539, 0.999540, 0.999909, 0.999909, 0.999909],
                    [0.999752, 0.999909, 0.999909, 0.999909, 0.999753],
                    [0.999909, 0.999909, 0.999909, 0.999540, 0.999540],
                    [0.999909, 0.999909, 0.999753, 0.999540, 0.999539]
                ],
            ],
        ],
    ],
    [
        # Case Description
        "1 batche(s), 3 dimension(s), 2 classe(s), 1 channel(s)",
        # Parameters
        [
            8.0, # bilateral_weight
            1.0, # gaussian_weight
            5.0, # bilateral_spatial_sigma
            0.1, # bilateral_color_sigma
            5.0, # gaussian_spatial_sigma
            1, # compatability_kernel_range
            2, # iterations
        ],
        # Input
        [
            # Batch 0
            [
                # Class 0
                [
                    # Slice 0
                    [
                        [1.0, 1.0, 0.0, 0.0, 0.0],
                        [1.0, 1.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                    ],
                    # Slice 1
                    [
                        [1.0, 1.0, 0.0, 0.0, 0.0],
                        [1.0, 1.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                    ],
                    # Slice 2
                    [
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                    ],
                    # Slice 3
                    [
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                    ],
                    # Slice 4
                    [
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                    ],
                ],

                # Class 1
                [
                    # Slice 0
                    [
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                    ],
                    # Slice 1
                    [
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                    ],
                    # Slice 2
                    [
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                    ],
                    # Slice 3
                    [
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 1.0, 1.0],
                        [0.0, 0.0, 0.0, 1.0, 1.0],
                    ],
                    # Slice 4
                    [
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 1.0, 1.0],
                        [0.0, 0.0, 0.0, 1.0, 1.0],
                    ],
                ],
            ],
        ],
        # Features
        [
            # Batch 0
            [
                # Channel 0
                [
                    # Slice 0
                    [
                        [0.5, 0.5, 0.5, 0.0, 0.0],
                        [0.5, 0.5, 0.5, 0.0, 0.0],
                        [0.5, 0.5, 0.5, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                    ],
                    # Slice 1
                    [
                        [0.5, 0.5, 0.5, 0.0, 0.0],
                        [0.5, 0.5, 0.5, 0.0, 0.0],
                        [0.5, 0.5, 0.5, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                    ],
                    # Slice 2
                    [
                        [0.5, 0.5, 0.5, 0.0, 0.0],
                        [0.5, 0.5, 0.5, 0.0, 0.0],
                        [0.5, 0.5, 0.8, 1.0, 1.0],
                        [0.0, 0.0, 1.0, 1.0, 1.0],
                        [0.0, 0.0, 1.0, 1.0, 1.0],
                    ],
                    # Slice 3
                    [
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 1.0, 1.0, 1.0],
                        [0.0, 0.0, 1.0, 1.0, 1.0],
                        [0.0, 0.0, 1.0, 1.0, 1.0],
                    ],
                    # Slice 4
                    [
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.0, 1.0, 1.0, 1.0],
                        [0.0, 0.0, 1.0, 1.0, 1.0],
                        [0.0, 0.0, 1.0, 1.0, 1.0],
                    ],
                ],
            ],
        ],
        # Expected
        [
            # Batch 0
            [
                # Class 0
                [
                    # Slice 0
                    [
                        [1.000000, 1.000000, 0.999999, 0.999049, 0.623107],
                        [1.000000, 1.000000, 0.999998, 0.998911, 0.586533],
                        [0.999999, 0.999998, 0.999866, 0.988961, 0.531648],
                        [0.999001, 0.998872, 0.988757, 0.897140, 0.478895],
                        [0.607341, 0.574104, 0.523379, 0.475603, 0.444802]
                    ],
                    # Slice 1
                    [
                        [1.000000, 1.000000, 0.999998, 0.998867, 0.575748],
                        [1.000000, 1.000000, 0.999987, 0.982081, 0.125020],
                        [0.999998, 0.999987, 0.995514, 0.395557, 0.014057],
                        [0.998802, 0.981356, 0.390734, 0.007831, 0.001451],
                        [0.557932, 0.118905, 0.013556, 0.001430, 0.001305]
                    ],
                    # Slice 2
                    [
                        [0.999998, 0.999998, 0.999852, 0.987882, 0.509607],
                        [0.999998, 0.999986, 0.995232, 0.382256, 0.013357],
                        [0.999845, 0.995113, 0.379344, 0.001853, 0.000170],
                        [0.987122, 0.372275, 0.001819, 0.000006, 0.000002],
                        [0.490950, 0.012637, 0.000164, 0.000002, 0.000002]
                    ],
                    # Slice 3
                    [
                        [0.998755, 0.998626, 0.986658, 0.884026, 0.452782],
                        [0.998602, 0.978651, 0.362107, 0.007108, 0.001340],
                        [0.986097, 0.356834, 0.001720, 0.000005, 0.000002],
                        [0.878055, 0.006855, 0.000005, 0.000000, 0.000000],
                        [0.436683, 0.001282, 0.000002, 0.000000, 0.000000]
                    ],
                    # Slice 4
                    [
                        [0.532362, 0.506320, 0.466688, 0.436673, 0.419582],
                        [0.501712, 0.099573, 0.011501, 0.001265, 0.001190],
                        [0.456888, 0.011278, 0.000150, 0.000002, 0.000002],
                        [0.423857, 0.001228, 0.000002, 0.000000, 0.000000],
                        [0.405660, 0.001153, 0.000002, 0.000000, 0.000000]
                    ],
                ],

                # Class 1
                [
                    # Slice 0
                    [
                        [0.000000, 0.000000, 0.000001, 0.000951, 0.376893],
                        [0.000000, 0.000000, 0.000002, 0.001089, 0.413467],
                        [0.000001, 0.000002, 0.000134, 0.011039, 0.468352],
                        [0.000999, 0.001128, 0.011243, 0.102860, 0.521105],
                        [0.392659, 0.425896, 0.476621, 0.524397, 0.555198]
                    ],
                    # Slice 1
                    [
                        [0.000000, 0.000000, 0.000002, 0.001133, 0.424252],
                        [0.000000, 0.000000, 0.000013, 0.017919, 0.874980],
                        [0.000002, 0.000013, 0.004486, 0.604443, 0.985943],
                        [0.001198, 0.018644, 0.609266, 0.992169, 0.998549],
                        [0.442068, 0.881095, 0.986444, 0.998570, 0.998695]
                    ],
                    # Slice 2
                    [
                        [0.000002, 0.000002, 0.000148, 0.012118, 0.490393],
                        [0.000002, 0.000014, 0.004769, 0.617744, 0.986643],
                        [0.000155, 0.004887, 0.620656, 0.998147, 0.999830],
                        [0.012878, 0.627725, 0.998181, 0.999994, 0.999998],
                        [0.509050, 0.987363, 0.999836, 0.999998, 0.999998]
                    ],
                    # Slice 3
                    [
                        [0.001245, 0.001374, 0.013342, 0.115974, 0.547218],
                        [0.001398, 0.021349, 0.637893, 0.992892, 0.998660],
                        [0.013903, 0.643166, 0.998280, 0.999995, 0.999998],
                        [0.121945, 0.993145, 0.999995, 1.000000, 1.000000],
                        [0.563317, 0.998718, 0.999998, 1.000000, 1.000000]
                    ],
                    # Slice 4
                    [
                        [0.467638, 0.493680, 0.533312, 0.563327, 0.580418],
                        [0.498288, 0.900427, 0.988499, 0.998735, 0.998810],
                        [0.543112, 0.988722, 0.999850, 0.999998, 0.999998],
                        [0.576143, 0.998772, 0.999998, 1.000000, 1.000000],
                        [0.594340, 0.998847, 0.999998, 1.000000, 1.000000]
                    ],
                ],
            ],
        ],
    ],
]


@skip_if_no_cpp_extention
class CRFTestCaseCpu(unittest.TestCase):
    
    @parameterized.expand(TEST_CASES)
    def test(self, test_case_description, params, input, features, expected):

        # Create input tensors
        input_tensor = torch.from_numpy(np.array(input)).to(dtype=torch.float, device=torch.device("cpu"))
        feature_tensor = torch.from_numpy(np.array(features)).to(dtype=torch.float, device=torch.device("cpu"))

        # apply filter
        crf = CRF(*params)
        output = crf(input_tensor, feature_tensor).cpu().numpy()

        # Ensure result are as expected
        np.testing.assert_allclose(output, expected, atol=1e-4)
        


if __name__ == "__main__":
    unittest.main()
