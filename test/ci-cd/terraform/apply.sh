#!/bin/env bash

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

MY_PATH="$(
    cd "$(dirname "$0")" >/dev/null 2>&1
    pwd -P
)"

terraservices=("cloudbuild")

cd "${MY_PATH}/initialize" &&
    terraform init &&
    terraform plan -input=false -out=tfplan &&
    terraform apply -input=false tfplan || exit 1
rm tfplan

for terraservice in "${terraservices[@]}"; do
    cd "${MY_PATH}/${terraservice}" &&
        echo "Current directory: $(pwd)" &&
        terraform init &&
        terraform plan -input=false -out=tfplan &&
        terraform apply -input=false tfplan || exit 1
    rm tfplan
done