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

import os
import time
import random
import json
import threading
import sys
from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.types import BatchSettings, PublisherOptions
from google.api_core import exceptions as google_exceptions

# --- CONFIGURATION ---
PROJECT_ID = os.getenv("PROJECT_ID") 
MODEL_NAME = os.getenv("MODEL_NAME")
TOPIC_ID = os.getenv("TOPIC_ID", "prompt-messages-topic")
TOTAL_MESSAGES = int(os.getenv("TOTAL_MESSAGES", "1000000"))
PRINT_EVERY = int(os.getenv("PRINT_EVERY", "10000"))

# --- JSON PAYLOAD GENERATOR ---
class MistralPayloadGenerator:
    """
    Generates JSON payloads specific to vLLM/Mistral formatting.
    """
    def __init__(self):
        self.model_name = MODEL_NAME
        
        self.system_roles = [
            "You are a helpful AI assistant.",
            "You are a cynical senior software engineer.",
            "You are an expert in medieval history.",
            "You are a creative writing tutor.",
            "You are a Python code optimizer."
        ]
        
        self.tasks = [
            "Explain the significance of", "Write a function to solve", 
            "Summarize the benefits of", "Critique the logic of", 
            "Translate this phrase to Spanish:", "Generate a haiku about"
        ]
        
        self.topics = [
            "asynchronous I/O", "Kubernetes sidecars", "Roman aqueducts",
            "quantum entanglement", "garbage collection in Java", "Rust ownership model",
            "Docker multistage builds", "SQL indexing strategies"
        ]

    def generate_payload(self):
        # Randomize content to simulate real traffic
        sys_role = random.choice(self.system_roles)
        user_content = f"{random.choice(self.tasks)} {random.choice(self.topics)}."

        # Construct the dictionary based on user requirements
        message_dict = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": sys_role},
                {"role": "user", "content": user_content}
            ],
            "max_tokens": 128,
            "temperature": 0.7
        }
        
        # Return as JSON string encoded to bytes (required for Pub/Sub)
        return json.dumps(message_dict).encode("utf-8")

# --- PUBLISHING LOGIC ---

class PublishStats:
    def __init__(self):
        self.published = 0
        self.success = 0
        self.errors = 0
        self.start_time = time.time()
        self.lock = threading.Lock()

    def callback(self, future):
        try:
            future.result() # Raises exception if publish failed
            with self.lock:
                self.success += 1
        except Exception as e:
            with self.lock:
                self.errors += 1
            # Optional: print(f"Error: {e}")

def verify_access(publisher, topic_path, generator):
    """
    Sends a single message and WAITS for the result to ensure
    credentials and topic existence are valid.
    """
    print(f"Performing pre-flight check on: {topic_path}...")
    try:
        # Generate a dummy payload
        data = generator.generate_payload()
        # Publish and force a synchronous wait for the result
        future = publisher.publish(topic_path, data)
        future.result(timeout=10) # Block until success or exception
        print("✅ Access verified. Starting bulk generation.\n")
        return True
    except google_exceptions.PermissionDenied:
        print(f"❌ ERROR: Permission Denied on topic '{topic_path}'.")
        print("   Ensure the Service Account has 'Pub/Sub Publisher' role.")
        return False
    except google_exceptions.NotFound:
        print(f"❌ ERROR: Topic '{topic_path}' does not exist.")
        return False
    except Exception as e:
        print(f"❌ ERROR: Pre-flight check failed: {e}")
        return False

def main():
    # 1. Batch Settings (Optimize Network)
    # Group messages to reduce HTTP requests
    batch_settings = BatchSettings(
        max_messages=1000,              # Publish 1000 messages per batch
        max_bytes=1 * 1024 * 1024,      # Or 1 MB per batch
        max_latency=0.05,               # Wait 50ms max to fill batch
    )

    # 2. Flow Control (Optimize Memory)
    # Prevent the loop from creating 1M objects in RAM instantly.
    # If buffer has 5000 messages or 100MB, the loop will pause (Block).
    publisher_options = PublisherOptions(
        enable_message_ordering=False,
        flow_control=pubsub_v1.types.PublishFlowControl(
            message_limit=5000, 
            byte_limit=100 * 1024 * 1024,
            limit_exceeded_behavior=pubsub_v1.types.LimitExceededBehavior.BLOCK,
        ),
    )

    # 3. Initialize Publisher
    publisher = pubsub_v1.PublisherClient(
        batch_settings=batch_settings, 
        publisher_options=publisher_options
    )
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
    
    generator = MistralPayloadGenerator()
    stats = PublishStats()

    # 4. Verify permissions before looping
    # If this fails, we exit before generating 1M messages.
    if not verify_access(publisher, topic_path, generator):
        sys.exit(1)

    print(f"Starting generation of {TOTAL_MESSAGES} JSON payloads...")
    print(f"Target: {topic_path}")

    try:
        for i in range(TOTAL_MESSAGES):
            # Generate JSON bytes
            data = generator.generate_payload()
            
            # Publish (returns a Future)
            # Note: Because of 'flow_control', this line will BLOCK if the 
            # upload queue is full, keeping RAM usage low.
            future = publisher.publish(topic_path, data)
            
            # Attach callback
            future.add_done_callback(stats.callback)
            
            stats.published += 1

            if stats.published % PRINT_EVERY == 0:
                elapsed = time.time() - stats.start_time
                rate = stats.published / elapsed
                print(f"Sent to Buffer: {stats.published} | Avg Rate: {rate:.0f} msg/s")

        print("Generation complete. Waiting for pending batches to clear...")
        
        # Wait for the 'success' + 'errors' count to match 'published'
        while stats.success + stats.errors < TOTAL_MESSAGES:
            time.sleep(1)
            remaining = TOTAL_MESSAGES - (stats.success + stats.errors)
            print(f"Remaining in queue: {remaining}...")

    except KeyboardInterrupt:
        print("\nStopped by user.")
    
    elapsed = time.time() - stats.start_time
    print(f"\n--- Summary ---")
    print(f"Total Generated: {stats.published}")
    print(f"Acked (Success): {stats.success}")
    print(f"Failed:          {stats.errors}")
    print(f"Time Elapsed:    {elapsed:.2f}s")

if __name__ == "__main__":
    main()
