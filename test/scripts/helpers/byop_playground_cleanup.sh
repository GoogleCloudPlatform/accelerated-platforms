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

echo_title "Deleting the environment configuration file"
rm -f ${MLP_ENVIRONMENT_FILE}

echo_title "Deleting Terraform GCS bucket"
gsutil -m rm -rf gs://${MLP_STATE_BUCKET}/*
gcloud storage buckets delete gs://${MLP_STATE_BUCKET} --project ${MLP_PROJECT_ID}

echo_title "Restoring configuration files"

echo_title "Cleaning up local repository changes"
rm -rf ${TF_DATA_DIR}

rm -f \
    ${MLP_TYPE_BASE_DIR}/${TF_DATA_DIR} \
    ${MLP_TYPE_BASE_DIR}/.terraform.lock.hcl \
    ${MLP_TYPE_BASE_DIR}/cluster_configmanagement_* \
    ${MLP_TYPE_BASE_DIR}/configsync_repository_*

git restore \
    ${MLP_TYPE_BASE_DIR}/backend.tf \
    ${MLP_TYPE_BASE_DIR}/cluster_configmanagement_* \
    ${MLP_TYPE_BASE_DIR}/configsync_repository_* \
    ${MLP_TYPE_BASE_DIR}/mlp.auto.tfvars
