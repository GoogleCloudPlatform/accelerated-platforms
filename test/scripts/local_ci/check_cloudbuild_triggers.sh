#!/usr/bin/env bash

# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -o errexit
set -o nounset
set -o pipefail

INFO="\033[1;34m[INFO]\033[0m"
WARNING="\033[1;33m[WARNING]\033[0m"

echo -e "${INFO} Simulating Cloud Build Triggers locally..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/cloudbuild_trigger_runner.py"

# Check if python3 is installed
if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${WARNING} python3 is not installed. Skipping Cloud Build trigger simulation."
    exit 0
fi

# Check if python-hcl2 is already available globally
if python3 -c "import hcl2" 2>/dev/null; then
    # We have it globally, just run the script
    python3 "${PYTHON_SCRIPT}" "$@"
else
    # Try creating a venv
    VENV_DIR="/tmp/tf-ci-venv"
    if [ ! -f "${VENV_DIR}/bin/activate" ]; then
        echo -e "${INFO} Creating temporary Python virtual environment at ${VENV_DIR}..."
        if ! python3 -m venv "${VENV_DIR}"; then
            echo -e "${WARNING} Failed to create python3 venv (missing python3-venv?). Skipping Cloud Build trigger simulation."
            echo -e "${WARNING} To fix this, run 'apt install python3-venv' or 'pip install python-hcl2'."
            exit 0
        fi
    fi

    source "${VENV_DIR}/bin/activate"

    if ! python3 -c "import hcl2" 2>/dev/null; then
        echo -e "${INFO} Installing python-hcl2..."
        pip install -q python-hcl2
    fi

    python3 "${PYTHON_SCRIPT}" "$@"
fi
