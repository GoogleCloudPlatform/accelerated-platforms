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
from unittest.mock import patch, MagicMock
import torch
import sys
from unittest.mock import MagicMock

sys.modules["folder_paths"] = MagicMock()
from src.custom_nodes.google_genmedia.virtual_try_on import VirtualTryOn


class TestVirtualTryOn(unittest.TestCase):
    @patch("src.custom_nodes.google_genmedia.virtual_try_on.get_gcp_metadata")
    @patch("src.custom_nodes.google_genmedia.virtual_try_on.aiplatform")
    def setUp(self, mock_aiplatform, mock_get_gcp_metadata):
        mock_get_gcp_metadata.side_effect = ["test-project", "us-central1"]
        self.mock_client = MagicMock()
        mock_aiplatform.gapic.PredictionServiceClient.return_value = self.mock_client
        self.node = VirtualTryOn()

    @patch(
        "src.custom_nodes.google_genmedia.virtual_try_on.VirtualTryOn.__init__",
        lambda *args, **kwargs: None,
    )
    @patch(
        "src.custom_nodes.google_genmedia.virtual_try_on.utils.tensor_to_pil_to_base64"
    )
    @patch(
        "src.custom_nodes.google_genmedia.virtual_try_on.utils.base64_to_pil_to_tensor"
    )
    def test_generate_and_return_image_success(
        self, mock_base64_to_tensor, mock_tensor_to_base64
    ):
        # Arrange
        person_image = torch.rand(1, 512, 512, 3)
        product_image = torch.rand(1, 512, 512, 3)

        mock_tensor_to_base64.side_effect = [
            "person_base64_string",
            "product_base64_string",
        ]

        mock_prediction = MagicMock()
        mock_prediction.__getitem__.return_value = "generated_base64_string"
        mock_response = MagicMock()
        mock_response.predictions = [mock_prediction]
        self.node.client = MagicMock()
        self.node.client.predict.return_value = mock_response

        mock_generated_tensor = torch.rand(1, 512, 512, 4)
        mock_base64_to_tensor.return_value = mock_generated_tensor

        # Act
        (result_tensor,) = self.node.generate_and_return_image(
            person_image=person_image,
            product_image=product_image,
            base_steps=32,
            person_generation="ALLOW_ADULT",
            number_of_images=1,
        )

        # Assert
        self.assertIsInstance(result_tensor, torch.Tensor)
        self.assertEqual(result_tensor.shape, (1, 512, 512, 4))
        self.node.client.predict.assert_called_once()
        self.assertEqual(mock_tensor_to_base64.call_count, 2)
        mock_base64_to_tensor.assert_called_once_with("generated_base64_string")

    @patch(
        "src.custom_nodes.google_genmedia.virtual_try_on.VirtualTryOn.__init__",
        lambda *args, **kwargs: None,
    )
    def test_generate_and_return_image_no_input_image(self):
        with self.assertRaises(ValueError):
            self.node.generate_and_return_image(
                person_image=torch.empty(0),
                product_image=torch.rand(1, 512, 512, 3),
                base_steps=32,
                person_generation="ALLOW_ADULT",
                number_of_images=1,
            )

    @patch(
        "src.custom_nodes.google_genmedia.virtual_try_on.VirtualTryOn.__init__",
        lambda *args, **kwargs: None,
    )
    @patch(
        "src.custom_nodes.google_genmedia.virtual_try_on.utils.tensor_to_pil_to_base64",
        side_effect=RuntimeError("Conversion failed"),
    )
    def test_generate_and_return_image_base64_conversion_failure(
        self, mock_tensor_to_base64
    ):
        # Arrange
        person_image = torch.rand(1, 512, 512, 3)
        product_image = torch.rand(1, 512, 512, 3)

        # Act & Assert
        with self.assertRaisesRegex(RuntimeError, "Conversion failed"):
            self.node.generate_and_return_image(
                person_image=person_image,
                product_image=product_image,
                base_steps=32,
                person_generation="ALLOW_ADULT",
                number_of_images=1,
            )

    @patch(
        "src.custom_nodes.google_genmedia.virtual_try_on.VirtualTryOn.__init__",
        lambda *args, **kwargs: None,
    )
    @patch(
        "src.custom_nodes.google_genmedia.virtual_try_on.utils.tensor_to_pil_to_base64"
    )
    def test_generate_and_return_image_predict_failure(self, mock_tensor_to_base64):
        # Arrange
        person_image = torch.rand(1, 512, 512, 3)
        product_image = torch.rand(1, 512, 512, 3)

        mock_tensor_to_base64.side_effect = [
            "person_base64_string",
            "product_base64_string",
        ]

        self.node.client = MagicMock()
        self.node.client.predict.side_effect = Exception("Prediction failed")

        # Act & Assert
        with self.assertRaises(RuntimeError):
            self.node.generate_and_return_image(
                person_image=person_image,
                product_image=product_image,
                base_steps=32,
                person_generation="ALLOW_ADULT",
                number_of_images=1,
            )


if __name__ == "__main__":
    unittest.main()
