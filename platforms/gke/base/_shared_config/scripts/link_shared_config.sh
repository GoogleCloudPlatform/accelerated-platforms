#!/bin/bash
#
# Copyright 2024 Google LLC
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

SHARED_CONFIG_DIRECTORY=${1}
SHARED_CONFIG_NAME=${2}

if [[ ${SHARED_CONFIG_DIRECTORY} != \.* ]]; then
  echo "The shared config directory path must be a relative path!"
  exit 1
fi

if test ! -d "${SHARED_CONFIG_DIRECTORY}"; then
  echo "Shared config directory '${SHARED_CONFIG_DIRECTORY}' does not exist!"
  exit 2
fi

if test ! -f "${SHARED_CONFIG_DIRECTORY}/${SHARED_CONFIG_NAME}_variables.tf"; then
  echo "Shared config '${SHARED_CONFIG_NAME}' does not exist in '${SHARED_CONFIG_DIRECTORY}'!"
  exit 3
fi

ln -s ${SHARED_CONFIG_DIRECTORY}/${SHARED_CONFIG_NAME}_variables.tf _${SHARED_CONFIG_NAME}_variables.tf
ln -s ${SHARED_CONFIG_DIRECTORY}/${SHARED_CONFIG_NAME}.auto.tfvars _${SHARED_CONFIG_NAME}.auto.tfvars

echo "Successfully linked shared config '${SHARED_CONFIG_NAME}' from '${SHARED_CONFIG_DIRECTORY}'."
