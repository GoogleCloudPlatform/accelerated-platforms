#!/bin/sh
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

# Default accelerator name
ACCELERATOR="${ACCELERATOR_NAME:-accelerator-not-set}"

# Find the script name from the arguments
SCRIPT_PATH=""
for arg in "$@"; do
  case "$arg" in
  *.js)
    SCRIPT_PATH="$arg"
    ;;
  esac
done

if [ -n "${SCRIPT_PATH:-}" ]; then
  SCRIPT_NAME=$(basename "$SCRIPT_PATH" .js)
else
  SCRIPT_NAME="unknown-script"
fi

TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
FILENAME="${SCRIPT_NAME}-${ACCELERATOR}-${TIMESTAMP}.jsonl"
OUTPUT_FILE_PATH="/output/${FILENAME}"
echo "Configured metrics output file: ${OUTPUT_FILE_PATH}"

if [ "$*" = "--help" ]; then
  k6 --help
else
  k6 run \
    --out "json=${OUTPUT_FILE_PATH}" \
    "$@"
fi
