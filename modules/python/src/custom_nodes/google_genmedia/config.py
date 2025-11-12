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

# This is a preview version of Google GenAI custom nodes

import requests

from .logger import get_node_logger

logger = get_node_logger(__name__)


# Fetch GCP project ID and zone required to authenticate with Vertex AI APIs
def get_gcp_metadata(path):
    headers = {"Metadata-Flavor": "Google"}
    try:
        response = requests.get(
            f"http://metadata.google.internal/computeMetadata/v1/{path}",
            headers=headers,
            timeout=5,
        )
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        return response.text.strip()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching metadata from {path}: {e}")
        return None
