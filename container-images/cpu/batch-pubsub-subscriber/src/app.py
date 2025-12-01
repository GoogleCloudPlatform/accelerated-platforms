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
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from google.api_core import retry
from google.api_core.exceptions import DeadlineExceeded, ServiceUnavailable
from google.cloud import pubsub_v1

# -------------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------------
PROJECT_ID = os.getenv("PROJECT_ID")
SUBSCRIPTION_ID = os.getenv("PUBSUB_SUBSCRIPTION_ID")
DLQ_TOPIC_ID = os.getenv("DLQ_TOPIC_ID")
VLLM_API_ENDPOINT = os.getenv(
    "VLLM_API_ENDPOINT", "http://localhost:8000/v1/chat/completions"
)

# Batch settings
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))

# Retry settings
MAX_RETRIES = 5
BASE_DELAY = 1.0
MAX_DELAY = 30.0

# Initialize Pub/Sub Clients
subscriber = pubsub_v1.SubscriberClient()
publisher = pubsub_v1.PublisherClient()


def validate_config():
    """
    Validates that all necessary environment variables are set.
    Exits the application if critical variables are missing.
    """
    print("\n🔍 Validating Configuration...")

    missing_vars = []

    # 1. Check Critical Variables (Must not be None or Empty)
    if not PROJECT_ID:
        missing_vars.append("PROJECT_ID")
    if not SUBSCRIPTION_ID:
        missing_vars.append("PUBSUB_SUBSCRIPTION_ID")
    if not DLQ_TOPIC_ID:
        missing_vars.append("DLQ_TOPIC_ID")
    if not VLLM_API_ENDPOINT:
        missing_vars.append("VLLM_API_ENDPOINT")

    # 2. Hard Fail if missing
    if missing_vars:
        print(f"❌ FATAL ERROR: The following environment variables are missing:")
        for var in missing_vars:
            print(f"   - {var}")
        print("🛑 Exiting application.")
        sys.exit(1)

    # 3. Print Summary if successful
    print("✅ Configuration OK:")
    print(f"   - Project ID:         {PROJECT_ID}")
    print(f"   - Subscription:       {SUBSCRIPTION_ID}")
    print(f"   - DLQ Topic:          {DLQ_TOPIC_ID}")
    print(f"   - vLLM Endpoint:      {VLLM_API_ENDPOINT}")
    print(f"   - Batch Size:         {BATCH_SIZE}")
    print(f"   - Concurrent Workers: {MAX_CONCURRENT_REQUESTS}")
    print("--------------------------------------------------\n")


def vllm_inference(prompt_text: str) -> str | None:
    """
    Sends the prompt to the vLLM server with Exponential Backoff Retry.
    """
    headers = {"Content-Type": "application/json"}

    try:
        payload = json.loads(prompt_text)
    except json.JSONDecodeError:
        print(f"❌ JSON Error: Prompt invalid. Mark as failed.")
        return None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(
                VLLM_API_ENDPOINT, json=payload, headers=headers, timeout=60
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

        except requests.exceptions.RequestException as e:
            if (
                response is not None
                and 400 <= response.status_code < 500
                and response.status_code != 429
            ):
                print(f"❌ Client Error ({response.status_code}). No retry.")
                return None

            if attempt == MAX_RETRIES:
                print(f"❌ Max vLLM retries reached.")
                return None

            delay = min(MAX_DELAY, BASE_DELAY * (2 ** (attempt - 1)))
            time.sleep(delay + random.uniform(0, 1))

    return None


def send_to_dlq(received_msg, error_reason="Max retries exceeded"):
    """
    Publishes the failed message to the Dead Letter Topic manually.
    """
    try:
        pubsub_msg = received_msg.message
        topic_path = publisher.topic_path(PROJECT_ID, DLQ_TOPIC_ID)

        future = publisher.publish(
            topic_path,
            pubsub_msg.data,
            original_message_id=pubsub_msg.message_id,
            failure_reason=error_reason,
        )
        future.result()
        print(f"💀 Sent {pubsub_msg.message_id} to DLQ.")
        return True
    except Exception as e:
        print(f"CRITICAL: DLQ Publish failed: {e}")
        return False


def process_single_message(received_msg):
    """
    Processes a single ReceivedMessage wrapper.
    """
    ack_id = received_msg.ack_id
    pubsub_msg = received_msg.message
    msg_id = pubsub_msg.message_id

    try:
        prompt_data = pubsub_msg.data.decode("utf-8")
        result = vllm_inference(prompt_data)

        if result:
            print(f"✅ Success {msg_id}")
            return ack_id, True
        else:
            print(f"🛑 Failed {msg_id} -> DLQ")
            if send_to_dlq(received_msg):
                return ack_id, True
            return ack_id, False

    except Exception as e:
        print(f"    Error processing {msg_id}: {e}")
        send_to_dlq(received_msg, error_reason=str(e))
        return ack_id, True


def run_subscriber_sync():
    """
    Main Loop: Synchronous Pull + Parallel Processing
    """
    # Note: validation is done in __main__ now
    subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)
    print(f"🚀 Starting Sync Pull on {subscription_path}")

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
        while True:
            try:
                # 1. Pull Batch
                response = subscriber.pull(
                    request={
                        "subscription": subscription_path,
                        "max_messages": BATCH_SIZE,
                    },
                    timeout=30.0,
                    retry=retry.Retry(deadline=60),
                )

                if not response.received_messages:
                    continue

                print(f"\n📦 Processing batch of {len(response.received_messages)}...")

                # 2. Process in Parallel
                future_to_ack_id = {
                    executor.submit(process_single_message, msg): msg.ack_id
                    for msg in response.received_messages
                }

                # 3. Collect Results
                ack_ids_to_confirm = []
                for future in as_completed(future_to_ack_id):
                    ack_id, should_ack = future.result()
                    if should_ack:
                        ack_ids_to_confirm.append(ack_id)

                # 4. Batch Acknowledge
                if ack_ids_to_confirm:
                    subscriber.acknowledge(
                        request={
                            "subscription": subscription_path,
                            "ack_ids": ack_ids_to_confirm,
                        }
                    )

            except (DeadlineExceeded, ServiceUnavailable):
                continue

            except Exception as e:
                print(f"⚠️ Unexpected error in main loop: {e}")
                time.sleep(5)


if __name__ == "__main__":
    # Perform strict check before anything starts
    validate_config()

    # Run application
    try:
        run_subscriber_sync()
    except KeyboardInterrupt:
        print("\n🛑 Application stopped by user.")
        sys.exit(0)
