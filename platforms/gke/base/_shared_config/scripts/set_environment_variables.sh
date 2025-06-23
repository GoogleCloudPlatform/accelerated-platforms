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

if [[ ! -v SHARED_CONFIG_PATHS ]]; then
  SHARED_CONFIG_PATHS=("${@}")
fi

for SHARED_CONFIG_PATH in "${SHARED_CONFIG_PATHS[@]}"; do
  echo "Loading shared configuration(${SHARED_CONFIG_PATH})"
  echo "-------------------------------------------------------------------------"
  terraform -chdir="${SHARED_CONFIG_PATH}" init >/dev/null
  terraform -chdir="${SHARED_CONFIG_PATH}" apply -auto-approve -input=false >/dev/null
  terraform -chdir="${SHARED_CONFIG_PATH}" output
  echo -e "-------------------------------------------------------------------------\n"
  eval "$(terraform -chdir="${SHARED_CONFIG_PATH}" output | sed -r 's/(\".*\")|\s*/\1/g')"
done
