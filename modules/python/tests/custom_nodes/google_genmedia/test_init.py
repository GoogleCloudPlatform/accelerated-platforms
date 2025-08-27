# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
from unittest.mock import MagicMock
import sys

sys.modules["folder_paths"] = MagicMock()

from src.custom_nodes.google_genmedia import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
    IMAGEN3_NODE_CLASS_MAPPINGS,
    IMAGEN3_NODE_DISPLAY_NAME_MAPPINGS,
    IMAGEN4_NODE_CLASS_MAPPINGS,
    IMAGEN4_NODE_DISPLAY_NAME_MAPPINGS,
    VEO2_NODE_CLASS_MAPPINGS,
    VEO2_NODE_DISPLAY_NAME_MAPPINGS,
    VEO3_NODE_CLASS_MAPPINGS,
    VEO3_NODE_DISPLAY_NAME_MAPPINGS,
    GEMINI_NODE_CLASS_MAPPINGS,
    GEMINI_NODE_DISPLAY_NAME_MAPPINGS,
    HELPER_NODE_CLASS_MAPPINGS,
    HELPER_NODE_DISPLAY_NAME_MAPPINGS,
    VTO_NODE_CLASS_MAPPINGS,
    VTO_NODE_DISPLAY_NAME_MAPPINGS,
)


class TestInit(unittest.TestCase):

    def test_node_class_mappings_combination(self):
        """
        Tests that NODE_CLASS_MAPPINGS contains all individual mappings.
        """
        all_mappings = [
            IMAGEN3_NODE_CLASS_MAPPINGS,
            IMAGEN4_NODE_CLASS_MAPPINGS,
            VEO2_NODE_CLASS_MAPPINGS,
            VEO3_NODE_CLASS_MAPPINGS,
            GEMINI_NODE_CLASS_MAPPINGS,
            HELPER_NODE_CLASS_MAPPINGS,
            VTO_NODE_CLASS_MAPPINGS,
        ]
        for mapping in all_mappings:
            for key in mapping:
                self.assertIn(key, NODE_CLASS_MAPPINGS)
                self.assertEqual(NODE_CLASS_MAPPINGS[key], mapping[key])

    def test_node_display_name_mappings_combination(self):
        """
        Tests that NODE_DISPLAY_NAME_MAPPINGS contains all individual mappings.
        """
        all_mappings = [
            IMAGEN3_NODE_DISPLAY_NAME_MAPPINGS,
            IMAGEN4_NODE_DISPLAY_NAME_MAPPINGS,
            VEO2_NODE_DISPLAY_NAME_MAPPINGS,
            VEO3_NODE_DISPLAY_NAME_MAPPINGS,
            GEMINI_NODE_DISPLAY_NAME_MAPPINGS,
            HELPER_NODE_DISPLAY_NAME_MAPPINGS,
            VTO_NODE_DISPLAY_NAME_MAPPINGS,
        ]
        for mapping in all_mappings:
            for key in mapping:
                self.assertIn(key, NODE_DISPLAY_NAME_MAPPINGS)
                self.assertEqual(NODE_DISPLAY_NAME_MAPPINGS[key], mapping[key])


if __name__ == "__main__":
    unittest.main()
