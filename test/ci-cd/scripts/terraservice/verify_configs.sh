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
set -o nounset
set -o pipefail

source /workspace/build.env
if [ "${DEBUG,,}" == "true" ]; then
  set -o xtrace
fi

SHARED_CONFIG_FOLDER="${1}"

exit_handler() {
  exit_code=$?

  if [ ${exit_code} -ne 0 ]; then
    echo "Configuration mismatch in '${SHARED_CONFIG_FOLDER}'" >>/workspace/build-failed.lock
  fi

  exit 0
}
trap exit_handler EXIT

errors=0
configs=$(ls ${SHARED_CONFIG_FOLDER}/*.auto.tfvars | sed 's|.*/||' | sed -e 's|\(.auto.tfvars\)*$||')
for config in ${configs}; do
  echo "Checking '${config}'..."
  variables=$(grep -e '^variable "' ${SHARED_CONFIG_FOLDER}/${config}_variables.tf | sed 's|^[^"]*"\([^"]*\)".*|\1|' | sort)
  tfvars=$(grep '^[[:alnum:]]' ${SHARED_CONFIG_FOLDER}/${config}.auto.tfvars | sed -E 's/^([a-zA-Z_][a-zA-Z0-9_]*)\s*=.*$/\1/g' | sort)
  diff <(echo "$variables") <(echo "$tfvars")

  if [ $? == 0 ]; then
    echo -e "[MATCH]\n"
  else
    errors=$((errors + 1))
    echo -e "[MISMATCH]\n"
  fi
done

exit ${errors}
