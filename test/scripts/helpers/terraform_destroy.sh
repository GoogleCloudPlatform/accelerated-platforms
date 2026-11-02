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

start_runtime "terraform_destroy"

echo_title "Running terraform destroy"

print_and_execute "cd ${MLP_TYPE_BASE_DIR} && terraform init"

for attempt in {1..3}; do
  if [ "${attempt}" -lt 3 ]; then
    if print_and_execute_no_check "cd ${MLP_TYPE_BASE_DIR} && terraform destroy -auto-approve"; then
      break
    fi
    echo_warning "terraform destroy failed (attempt ${attempt}/3), retrying in 30s..."
    sleep 30
  else
    print_and_execute "cd ${MLP_TYPE_BASE_DIR} && terraform destroy -auto-approve"
  fi
done

total_runtime "terraform_destroy"

check_local_error_exit_on_error
