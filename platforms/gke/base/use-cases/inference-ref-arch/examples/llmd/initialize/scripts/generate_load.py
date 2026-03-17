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

import asyncio
import os
import random
from typing import Any, Dict, List

import aiohttp

# --- Configuration ---
llmd_endpoints_hostname: str = os.environ.get(
    "llmd_endpoints_hostname", "localhost:7860"
)
URL: str = f"https://{llmd_endpoints_hostname}/gradio_api/api/sync_chat"
MODEL: str = os.environ.get("HF_MODEL_ID", "qwen/qwen3-32b")
TOKEN_FILE: str = "token.jwt"

CONCURRENT_USERS: int = 500
TOTAL_REQUESTS: int = 10000
THINK_TIME: float = 2.0
RAMP_UP_DELAY: float = 0.5

# Global counter for tracking total requests across all sessions
request_counter: int = 0

print(f"Preparing to send the requests to the MODEL {MODEL}")


def get_token() -> str:
    """Reads the authentication token from a local file.

    Returns:
        str: The token string if the file exists, otherwise "dummy-token".
    """
    try:
        with open(TOKEN_FILE, "r") as f:
            return f.read().strip()
    except Exception:
        return "dummy-token"


def generate_light_prompt() -> str:
    """Generates a short, simple prompt to keep Time To First Token (TTFT) low.

    Returns:
        str: A randomly selected prompt about a general topic.
    """
    topics: List[str] = [
        "the weather",
        "cooking pasta",
        "how bees fly",
        "the moon",
        "why sky is blue",
    ]
    return f"Tell me a very short fun fact about {random.choice(topics)}."


async def run_user_session(
    session: aiohttp.ClientSession,
    user_id: int,
    semaphore: asyncio.Semaphore,
    headers: Dict[str, str],
) -> None:
    """Simulates a single user's behavior, sending multiple requests over time.

    Args:
        session: The active aiohttp ClientSession to use for requests.
        user_id: A unique integer ID for the simulated user.
        semaphore: An asyncio Semaphore to control concurrent access.
        headers: HTTP headers including authentication and content-type.
    """
    global request_counter

    # Staggered Start: Don't let everyone hit the server at second 0.0
    await asyncio.sleep(user_id * RAMP_UP_DELAY)

    async with semaphore:
        while True:
            # Check if we've reached the total request limit
            if request_counter >= TOTAL_REQUESTS:
                break

            request_counter += 1
            current_message: str = generate_light_prompt()

            # Using empty history ([]) to keep the KV Cache small/fast
            payload: Dict[str, Any] = {"data": [current_message, [], MODEL]}

            try:
                async with session.post(URL, headers=headers, json=payload) as response:
                    # Consume the response body
                    await response.text()
                    print(f"User {user_id:02d} | Status: {response.status}")

            except Exception as e:
                print(f"Connection error for User {user_id}: {e}")

            # "Think Time" - Relax the backend between bursts
            await asyncio.sleep(random.uniform(1, THINK_TIME))


async def main() -> None:
    """Orchestrates the load test by initializing sessions and spawning user tasks."""
    print(f"Starting Load: {CONCURRENT_USERS} concurrent users...")

    token: str = get_token()
    headers: Dict[str, str] = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    # Limit connections at the connector level to match concurrent users
    connector = aiohttp.TCPConnector(limit=CONCURRENT_USERS)
    timeout = aiohttp.ClientTimeout(total=30)
    semaphore = asyncio.Semaphore(CONCURRENT_USERS)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks: List[asyncio.Task] = []
        for i in range(CONCURRENT_USERS):
            task = asyncio.create_task(run_user_session(session, i, semaphore, headers))
            tasks.append(task)

        await asyncio.gather(*tasks)

    print("Test Complete.")


if __name__ == "__main__":
    asyncio.run(main())
