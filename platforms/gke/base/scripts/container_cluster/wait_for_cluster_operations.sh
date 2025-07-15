#!/usr/bin/env bash

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
set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

JSON_INPUT=$(</dev/stdin)
eval "$(jq -n "${JSON_INPUT}" | jq -r 'to_entries[] | "\(.key | ascii_upcase)=\(.value | @sh)"')"

wait_time=5

retries=1
if [ "${TIMEOUT}" -gt 5 ]; then
  retries=$((TIMEOUT / wait_time))
fi

while true; do
  if ((retries < 0)); then
    exit 1
  fi

  output=$(echo "${JSON_INPUT}" | "${MY_PATH}/list_cluster_operations.sh")
  if [ "${output}" == "[]" ]; then
    break
  fi

  echo "Waiting for the cluster operation(s) to complete..." >&2
  retries=$((retries - 1))
  sleep "${wait_time}"s
done

echo "${output}" | jq .[0]
