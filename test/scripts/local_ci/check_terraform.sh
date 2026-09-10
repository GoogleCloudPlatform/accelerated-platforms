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
SUCCESS="\033[1;32m[SUCCESS]\033[0m"
ERROR="\033[1;31m[ERROR]\033[0m"

echo -e "${INFO} Checking Terraform formatting (terraform fmt -check)..."
if terraform fmt -check -recursive platforms/gke; then
    echo -e "${SUCCESS} Terraform formatting is correct."
else
    echo -e "${ERROR} Terraform formatting issues found! Run 'terraform fmt -recursive platforms/gke' to fix."
    if [ "${AUTO_FIX}" == "true" ]; then
        echo -e "${INFO} AUTO_FIX is enabled. Fixing..."
        terraform fmt -recursive platforms/gke
    else
        exit 1
    fi
fi

# To speed up local testing, we don't run `terraform validate` on every single module locally
# unless the user explicitly opts in, because `terraform init -backend=false` on 50+ modules
# takes several minutes.
# However, if RUN_TF_VALIDATE=true is set, we will run it!
if [ "${RUN_TF_VALIDATE:-false}" == "true" ]; then
    echo -e "${INFO} Validating Terraform syntax across all modules..."
    modules=$(find platforms/gke -name "*.tf" -exec dirname {} \; | sort -u)
    
    for mod in $modules; do
        echo -e "   Validating: ${mod}"
        terraform -chdir="${mod}" init -backend=false -quiet
        if ! terraform -chdir="${mod}" validate -json > /dev/null; then
            echo -e "${ERROR} terraform validate failed in ${mod}."
            # Run without -json to show output
            terraform -chdir="${mod}" validate
            exit 1
        fi
    done
    echo -e "${SUCCESS} All modules validated successfully."
else
    echo -e "${INFO} Skipping exhaustive terraform validate (Set RUN_TF_VALIDATE=true to enable)."
fi

exit 0
