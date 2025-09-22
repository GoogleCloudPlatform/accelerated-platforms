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

"""Unit tests for virtual_try_on.py"""

import unittest
from unittest.mock import patch, MagicMock
import torch

from src.custom_nodes.google_genmedia.virtual_try_on import VirtualTryOn
from src.custom_nodes.google_genmedia import exceptions


class TestVirtualTryOn(unittest.TestCase):
    """Test cases for VirtualTryOn class."""

    @patch("src.custom_nodes.google_genmedia.virtual_try_on.get_gcp_metadata")
    @patch("src.custom_nodes.google_genmedia.virtual_try_on.aiplatform.init")
    @patch(
        "src.custom_nodes.google_genmedia.virtual_try_on.aiplatform.gapic.PredictionServiceClient"
    )
    def setUp(
        self,
        mock_prediction_service_client,
        mock_aiplatform_init,
        mock_get_gcp_metadata,
    ):
        """Set up test fixtures."""
        mock_get_gcp_metadata.side_effect = [
            "test-project",
            "us-central1-a",
        ]
        self.node = VirtualTryOn()
        self.node.client = mock_prediction_service_client

    def test_initialization(self):
        """Test that the node can be initialized."""
        self.assertIsNotNone(self.node)

    @patch("src.custom_nodes.google_genmedia.virtual_try_on.get_gcp_metadata")
    @patch(
        "src.custom_nodes.google_genmedia.utils.tensor_to_pil_to_base64",
        return_value="base64_string",
    )
    @patch("src.custom_nodes.google_genmedia.utils.base64_to_pil_to_tensor")
    def test_generate_and_return_image_success(
        self, mock_base64_to_tensor, mock_tensor_to_base64, mock_get_gcp_metadata
    ):
        """Test a successful run of generate_and_return_image."""
        mock_get_gcp_metadata.side_effect = [
            "test-project",
            "us-central1-a",
        ]
        mock_response = MagicMock()
        mock_prediction = MagicMock()
        mock_prediction.__getitem__.return_value = "base64_image_string"
        mock_response.predictions = [mock_prediction]
        self.node._predict = MagicMock(return_value=mock_response)
        mock_base64_to_tensor.return_value = torch.zeros(1, 64, 64, 3)

        person_image = torch.zeros(1, 64, 64, 3)
        product_image = torch.zeros(1, 64, 64, 3)
        result = self.node.generate_and_return_image(
            person_image=person_image,
            product_image=product_image,
            base_steps=32,
            person_generation="ALLOW_ADULT",
            number_of_images=1,
        )
        self.assertIsInstance(result, tuple)
        self.assertIsInstance(result[0], torch.Tensor)

    @patch(
        "src.custom_nodes.google_genmedia.virtual_try_on.VirtualTryOn.__init__",
        side_effect=exceptions.APIInitializationError("Test Error"),
    )
    def test_generate_and_return_image_reinitialization_error(self, mock_init):
        """Test generate_and_return_image with a re-initialization error."""
        person_image = torch.zeros(1, 64, 64, 3)
        product_image = torch.zeros(1, 64, 64, 3)
        with self.assertRaisesRegex(RuntimeError, "Error re-initializing client"):
            self.node.generate_and_return_image(
                person_image=person_image,
                product_image=product_image,
                base_steps=32,
                person_generation="ALLOW_ADULT",
                number_of_images=1,
                gcp_project_id="new_project",
            )

    @patch("src.custom_nodes.google_genmedia.virtual_try_on.get_gcp_metadata")
    def test_generate_and_return_image_empty_person_image(self, mock_get_gcp_metadata):
        """Test generate_and_return_image with an empty person image."""
        mock_get_gcp_metadata.side_effect = [
            "test-project",
            "us-central1-a",
        ]
        person_image = torch.zeros(0)
        product_image = torch.zeros(1, 64, 64, 3)
        with self.assertRaises(exceptions.ConfigurationError):
            self.node.generate_and_return_image(
                person_image=person_image,
                product_image=product_image,
                base_steps=32,
                person_generation="ALLOW_ADULT",
                number_of_images=1,
            )

    @patch("src.custom_nodes.google_genmedia.virtual_try_on.get_gcp_metadata")
    def test_generate_and_return_image_empty_product_image(self, mock_get_gcp_metadata):
        """Test generate_and_return_image with an empty product image."""
        mock_get_gcp_metadata.side_effect = [
            "test-project",
            "us-central1-a",
        ]
        person_image = torch.zeros(1, 64, 64, 3)
        product_image = torch.zeros(0)
        with self.assertRaises(exceptions.ConfigurationError):
            self.node.generate_and_return_image(
                person_image=person_image,
                product_image=product_image,
                base_steps=32,
                person_generation="ALLOW_ADULT",
                number_of_images=1,
            )

    @patch("src.custom_nodes.google_genmedia.virtual_try_on.get_gcp_metadata")
    def test_generate_and_return_image_seed_with_watermark(self, mock_get_gcp_metadata):
        """Test generate_and_return_image with seed and watermark."""
        mock_get_gcp_metadata.side_effect = [
            "test-project",
            "us-central1-a",
        ]
        person_image = torch.zeros(1, 64, 64, 3)
        product_image = torch.zeros(1, 64, 64, 3)
        with self.assertRaises(ValueError):
            self.node.generate_and_return_image(
                person_image=person_image,
                product_image=product_image,
                base_steps=32,
                person_generation="ALLOW_ADULT",
                number_of_images=1,
                seed=123,
                add_watermark=True,
            )

    @patch("src.custom_nodes.google_genmedia.virtual_try_on.get_gcp_metadata")
    @patch(
        "src.custom_nodes.google_genmedia.utils.tensor_to_pil_to_base64",
        return_value="base64_string",
    )
    def test_generate_and_return_image_api_error(
        self, mock_tensor_to_base64, mock_get_gcp_metadata
    ):
        """Test generate_and_return_image with an API call error."""
        mock_get_gcp_metadata.side_effect = [
            "test-project",
            "us-central1-a",
        ]
        self.node._predict = MagicMock(side_effect=exceptions.APICallError("API Error"))
        person_image = torch.zeros(1, 64, 64, 3)
        product_image = torch.zeros(1, 64, 64, 3)
        with self.assertRaises(exceptions.APICallError):
            self.node.generate_and_return_image(
                person_image=person_image,
                product_image=product_image,
                base_steps=32,
                person_generation="ALLOW_ADULT",
                number_of_images=1,
            )

    @patch("src.custom_nodes.google_genmedia.virtual_try_on.get_gcp_metadata")
    @patch(
        "src.custom_nodes.google_genmedia.utils.tensor_to_pil_to_base64",
        return_value="base64_string",
    )
    def test_generate_and_return_image_no_predictions(
        self, mock_tensor_to_base64, mock_get_gcp_metadata
    ):
        """Test generate_and_return_image with no predictions."""
        mock_get_gcp_metadata.side_effect = [
            "test-project",
            "us-central1-a",
        ]
        mock_response = MagicMock()
        mock_response.predictions = []
        self.node._predict = MagicMock(return_value=mock_response)
        person_image = torch.zeros(1, 64, 64, 3)
        product_image = torch.zeros(1, 64, 64, 3)
        with self.assertRaises(exceptions.APICallError):
            self.node.generate_and_return_image(
                person_image=person_image,
                product_image=product_image,
                base_steps=32,
                person_generation="ALLOW_ADULT",
                number_of_images=1,
            )


if __name__ == "__main__":
    unittest.main()
