# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
from concurrent.futures import TimeoutError

import requests
from google.cloud import pubsub_v1

# --- Configuration ---
PROJECT_ID = os.getenv("PROJECT_ID")
SUBSCRIPTION_ID = os.getenv("PUBSUB_SUBSCRIPTION_ID", "prompt-messages-subscription")
VLLM_API_ENDPOINT = os.getenv(
    "VLLM_API_ENDPOINT", "http://localhost:8000/v1/chat/completions"
)
VLLM_MODEL_NAME = os.getenv("VLLM_MODEL_NAME")


def vllm_inference(prompt_text: str) -> str | None:
    """
    Sends the prompt to the vLLM server and returns the generated text.

    Args:
        prompt_text: The text prompt received from Pub/Sub.

    Returns:
        The generated text from the LLM, or None on failure.
    """

    # Standard header for the OpenAI-compatible API exposed by vLLM
    headers = {"Content-Type": "application/json"}

    print(f"📡 Sending request to vLLM server: {VLLM_API_ENDPOINT}")

    try:
        response = requests.post(
            VLLM_API_ENDPOINT, json=json.loads(prompt_text), headers=headers, timeout=30
        )
        # Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status()

        # Parse the JSON response
        data = response.json()

        # Extract the completion text
        completion_text = data["choices"][0]["message"]["content"].strip()

        print(f"✅ LLM Response (Snippet): {completion_text[:50]}...")
        return completion_text

    except requests.exceptions.RequestException as e:
        print(f"❌ Error calling vLLM server: {e}")
        # Return None to signal failure for non-acknowledgment in the callback
        return None


def callback(message: pubsub_v1.subscriber.message.Message):
    """
    This function is executed every time a new message is pulled from Pub/Sub.
    """
    try:
        # Decode the message data from bytes to a UTF-8 string (the prompt)
        prompt_data = message.data.decode("utf-8")
        print(f"\n--- New Message ---")
        print(f"📥 Received Pub/Sub message ID: {message.message_id}")
        print(f"    Prompt Data: {prompt_data}")

        # 1. Call the vLLM server for inference
        llm_response = vllm_inference(prompt_data)

        # 2. Acknowledge the message ONLY if the vLLM call was successful
        if llm_response:
            message.ack()
            print(
                f"✨ Message ID {message.message_id} successfully processed and acknowledged."
            )
        else:
            # If the vLLM call failed (e.g., connection error, 500 status),
            # we do NOT acknowledge the message. Pub/Sub will redeliver it
            # after the acknowledgment deadline expires.
            print(
                f"⚠️ LLM processing failed. Message ID {message.message_id} not acknowledged, will be redelivered."
            )

    except Exception as e:
        print(f"An unexpected error occurred during message processing: {e}")
        # The message will eventually be redelivered by Pub/Sub


def run_subscriber():
    """
    Initializes and runs the streaming Pub/Sub subscriber client.
    """
    if (
        PROJECT_ID == "your-gcp-project-id"
        or SUBSCRIPTION_ID == "your-pubsub-subscription-id"
    ):
        print("FATAL: Please update PROJECT_ID and SUBSCRIPTION_ID placeholders.")
        return

    # Create a new subscriber client
    subscriber = pubsub_v1.SubscriberClient()
    # Format the fully qualified subscription path
    subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)

    print(f"🚀 Starting listener on {subscription_path}...")

    # Start the streaming pull: this method blocks the main thread with a Future
    # that manages the background thread(s) for pulling messages.
    streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)

    # Keep the main thread alive to allow the background thread(s) to run
    try:
        # The .result() method will block indefinitely unless an exception occurs
        streaming_pull_future.result()
    except TimeoutError:
        # Graceful shutdown on timeout (optional, but good practice)
        streaming_pull_future.cancel()
        streaming_pull_future.result()
    except KeyboardInterrupt:
        # Handle Ctrl+C
        print("\n🛑 Received interrupt, shutting down subscriber...")
        streaming_pull_future.cancel()
        streaming_pull_future.result()
    except Exception as e:
        print(f"\nAn unhandled exception occurred in the subscriber loop: {e}")
        streaming_pull_future.cancel()

    finally:
        # Close the client connection cleanly
        subscriber.close()
        print("Subscriber client closed.")


if __name__ == "__main__":
    run_subscriber()
