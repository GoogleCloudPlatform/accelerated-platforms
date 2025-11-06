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

import logging


def get_node_logger(name: str) -> logging.Logger:
    """
    Initializes and returns a logger instance for an individual custom node module.

    It sets the logger's level to match the parent package logger's effective level,
    ensuring compliance with the centralized logging.conf setting.
    """
    node_logger = logging.getLogger(name)
    package_name = name.split(".")[0]
    package_logger = logging.getLogger(package_name)

    # This automatically sets the level based on logging.conf (read in __init__.py)
    node_logger.setLevel(package_logger.getEffectiveLevel())

    return node_logger
