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

echo_title "Configure the environment to use an OCI image for Config Sync"

print_and_execute_no_check "mv ${MLP_TYPE_BASE_DIR}/cluster_configmanagement_git.tf ${MLP_TYPE_BASE_DIR}/cluster_configmanagement_git.tf.ignore"
print_and_execute_no_check "mv ${MLP_TYPE_BASE_DIR}/cluster_configmanagement_oci.tf.ignore ${MLP_TYPE_BASE_DIR}/cluster_configmanagement_oci.tf"

print_and_execute_no_check "mv ${MLP_TYPE_BASE_DIR}/configsync_repository_github.tf ${MLP_TYPE_BASE_DIR}/configsync_repository_github.tf.ignore"
print_and_execute_no_check "mv ${MLP_TYPE_BASE_DIR}/configsync_repository_oci.tf.ignore ${MLP_TYPE_BASE_DIR}/configsync_repository_oci.tf"

export GIT_TOKEN_FILE=""
export MLP_GIT_NAMESPACE="n/a"
export MLP_GIT_USER_NAME="n/a"
export MLP_GIT_USER_EMAIL="n/a"

source ${SCRIPTS_DIR}/helpers/git_env.sh
