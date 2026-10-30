#!/usr/bin/env bash

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

start_runtime "terraform_apply"

echo_title "Running terraform apply"

print_and_execute "cd ${MLP_TYPE_BASE_DIR} && \
terraform init && \
terraform plan -input=false -out=tfplan && \
terraform apply -input=false tfplan"

rm -f tfplan

if [ ${local_error} -ne 0 ] && [ "${MLP_TYPE:-}" == "playground" ] && [ "${MLP_REGION:-us-central1}" == "us-central1" ]; then
    fallback_region="${MLP_FALLBACK_REGION:-us-east4}"
    echo_warning "Terraform apply failed in '${MLP_REGION:-us-central1}'. Cleaning up partial resources and falling back to '${fallback_region}'..."
    print_and_execute_no_check "cd ${MLP_TYPE_BASE_DIR} && terraform destroy -auto-approve"
    local_error=0
    export MLP_REGION="${fallback_region}"
    if [ -f /workspace/build.env ]; then
        if grep -q "MLP_REGION=" /workspace/build.env; then
            sed -i "s|^\(export[[:blank:]]\+\)\?MLP_REGION=.*|export MLP_REGION=\"${fallback_region}\"|" /workspace/build.env
        else
            echo "export MLP_REGION=\"${fallback_region}\"" >> /workspace/build.env
        fi
    fi
    source ${SCRIPTS_DIR}/helpers/${MLP_TYPE}_config.sh
    print_and_execute "cd ${MLP_TYPE_BASE_DIR} && \
terraform init && \
terraform plan -input=false -out=tfplan && \
terraform apply -input=false tfplan"
    rm -f tfplan
fi

total_runtime "terraform_apply"

check_local_error_exit_on_error
