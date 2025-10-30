#!/usr/bin/env bash

# Copyright 2025 Google LLC
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

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"
ACP_REPO_DIR="$(realpath ${MY_PATH}/../../../../../../../../../)"

source "${MY_PATH}/../../config/huggingface.sh"

hf_models_found=($(grep -hr -E 'export HF_MODEL_ID="[[:alnum:]]+' "${ACP_REPO_DIR}/" | sed 's/[[:space:]]*//' | tr -d '"' | awk -F= '{print $2}' | sort -u))
hf_models_found_sorted=$(printf "%s\n" "${hf_models_found[@]}" | sort)

hf_models_sorted=$(printf "%s\n" "${hf_models[@]}" | sort)

echo "Comparing:"
echo -n "hf_models_found: "
echo ${hf_models_found_sorted}
echo -n "hf_models:       "
echo ${hf_models_sorted}
echo

diff1=$(comm -13 <(printf "%s\n" "${hf_models_found_sorted[@]}") <(printf "%s\n" "${hf_models_sorted[@]}"))
diff2=$(comm -23 <(printf "%s\n" "${hf_models_found_sorted[@]}") <(printf "%s\n" "${hf_models_sorted[@]}"))

if [[ "${hf_models_found_sorted[*]}" != "${hf_models_sorted[*]}" ]]; then
  echo -e "Discrepancies found!"
  if [[ "${diff1[*]}" != "" ]]; then
    echo "The following value(s) are in 'hf_models' but were not found in the repo:"
    echo "${diff1[@]}"
  fi
  if [[ "${diff2[*]}" != "" ]]; then
    echo "The following value(s) were found in the repo but not in 'hf_models':"
    echo "${diff2[@]}"
  fi
  exit 1
else
  echo "No discrepancies found."
fi

exit 0
