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


TEXT_EMBEDDING_ENDPOINT = os.environ["TEXT_EMBEDDING_ENDPOINT"]
MULTIMODAL_EMBEDDING_ENDPOINT = os.environ["MULTIMODAL_EMBEDDING_ENDPOINT"]


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


# Function to process text input
def process_text(text):
    """
    Processes the text input (prompt) to generate embeddings.

    Args:
      text: The input prompt.

    Returns:
      Embeddings as a list of floats.
    """
    # Replace this with your actual embedding generation logic
    # This is a placeholder example
    # embeddings = [0.1, 0.2, 0.3, 0.4, 0.5]
    embeddings = []

    response = requests.post(
        TEXT_EMBEDDING_ENDPOINT,
        json={"text": text},
        headers={"Content-Type": "application/json"},
        timeout=1000,
    )
    response.raise_for_status()
    embeddings = response.json()["text_embeds"]

    return embeddings


# Function to process text and image URI input
def process_text_image(text, image_uri):
    """
    Processes the text prompt and image URI to generate embeddings.

    Args:
      text: The input prompt.
      image_uri: The GCS URI of the image.

    Returns:
      Embeddings as a list of floats.
    """
    if not validate_gcs_uri(image_uri):  # Validate the URI
        return "Invalid GCS URI provided."  # Return an error message

    # Replace this with your actual embedding generation logic
    # This is a placeholder example
    # embeddings = [0.6, 0.7, 0.8, 0.9, 1.0]
    embeddings = []

    response = requests.post(
        MULTIMODAL_EMBEDDING_ENDPOINT,
        json={"text": text, "image_uri": image_uri},
        headers={"Content-Type": "application/json"},
        timeout=1000,
    )
    response.raise_for_status()
    embeddings = response.json()["multimodal_embeds"]

    return embeddings


# Create the Gradio interface
with gr.Blocks() as demo:
    gr.Markdown("## Retail Chatbot with Embeddings")

    with gr.Tab("Text Prompt"):
        text_input = gr.Textbox(lines=5, label="Enter your prompt")
        text_output = gr.Textbox(label="Embeddings")
        text_button = gr.Button("Generate Embeddings")
        text_button.click(fn=process_text, inputs=text_input, outputs=text_output)

    with gr.Tab("Text Prompt + Image"):
        text_input_2 = gr.Textbox(lines=5, label="Enter your prompt")
        image_uri_input = gr.Textbox(label="Enter GCS image URI")
        image_uri_output = gr.Textbox(label="Embeddings")
        image_uri_button = gr.Button("Generate Embeddings")
        image_uri_button.click(
            fn=process_text_image,
            inputs=[text_input_2, image_uri_input],
            outputs=image_uri_output,
        )

# Launch the demo
if __name__ == "__main__":
    demo.launch(share=True, server_name="0.0.0.0")
