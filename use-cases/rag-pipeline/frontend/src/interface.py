# Copyright 2024 Google LLC
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

import gradio as gr
import re
import requests
import os

# BACKEND_SERVICE_URL = os.environ["BACKEND_SERVICE_URL"]
BACKEND_SERVICE_URL = "http://0.0.0.0:8000/generate_product_recommendations"


# Function to validate GCS URI
def validate_gcs_uri(uri):
    """
    Validates if the provided URI is a valid GCS URI.

    Args:
      uri: The URI string to validate.

    Returns:
      True if the URI is valid, False otherwise.
    """
    pattern = (
        r"^gs://[a-z0-9][a-z0-9._-]{1,253}/[a-zA-Z0-9_.!@#$%^&*()/-]+[a-zA-Z0-9]+$"
    )
    return bool(re.match(pattern, uri))


# Function to validate text input
def validate_text(text):
    """
    Validates if the provided text is not empty.

    Args:
      text: The text string to validate.

    Returns:
      True if the text is valid, False otherwise.
    """
    return bool(text.strip())


# Function to process the input and send to backend
def process_input(text=None, image_uri=None):
    """
    Processes the input (text, image_uri or both) and sends a POST request to the backend.

    Args:
      text: The input text(optional).
      image_uri: The GCS URI of the image (optional).

    Returns:
      The response from the backend.
    """
    if text and not validate_text(text):
        return "Invalid text input provided."

    if image_uri and not validate_gcs_uri(image_uri):
        return "Invalid GCS URI provided."

    data = {}
    if text:
        data["text"] = text
    if image_uri:
        data["image_uri"] = image_uri

    if not data:  # Check if data is empty
        return "Please provide either text or image URI."

    response = requests.post(BACKEND_SERVICE_URL, json=data)
    response.raise_for_status()  # Raise an exception for bad status codes
    return response.json()


# Create the Gradio interface
with gr.Blocks() as demo:
    gr.Markdown("## Retail Shopping Assistant")

    with gr.Tab("Text"):
        text_input = gr.Textbox(lines=5, label="Enter your prompt")
        text_output = gr.Textbox(label="Response")
        text_button = gr.Button("Generate Response")
        text_button.click(
            fn=lambda text: process_input(text=text),
            inputs=text_input,
            outputs=text_output,
        )

    with gr.Tab("Text + Image"):
        text_input_2 = gr.Textbox(lines=5, label="Enter your prompt")
        image_uri_input = gr.Textbox(label="Enter GCS image URI for the product")
        text_image_output = gr.Textbox(label="Response")
        text_image_button = gr.Button("Generate Response")
        text_image_button.click(
            fn=process_input,
            inputs=[text_input_2, image_uri_input],
            outputs=text_image_output,
        )

    with gr.Tab("Image"):
        image_uri_input_2 = gr.Textbox(label="Enter GCS image URI for the product")
        image_output = gr.Textbox(label="Response")
        image_button = gr.Button("Generate Response")
        image_button.click(
            fn=process_input,
            inputs=image_uri_input_2,
            outputs=image_output,
        )

# Launch the demo
if __name__ == "__main__":
    demo.launch(share=True, server_name="0.0.0.0")
