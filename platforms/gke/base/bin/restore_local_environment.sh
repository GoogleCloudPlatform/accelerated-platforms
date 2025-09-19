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

ACP_REPO_DIR="$(realpath ${MY_PATH}/../../../../)"

if [[ ! -v TF_VAR_terraform_bucket_name ]]; then
  echo "TF_VAR_terraform_bucket_name environment variable must be set, exiting!"
  exit 1
fi

echo
echo "The following TF_VAR_ environment variables are set"
echo "--------------------------------------------------------------------------------"
env | grep TF_VAR_ | sort
echo "--------------------------------------------------------------------------------"
echo "  Important variables to verify:"
echo "   - TF_VAR_platform_default_project_id"
echo "   - TF_VAR_platform_default_region, otherwise the default is 'us-central1'"
echo "   - TF_VAR_platform_name, otherwise the default is 'dev'"
echo "   - TF_VAR_resource_name_prefix, otherwise the default is 'acp'"
echo
echo
echo "Are the above values correct?"
select yn in "Yes" "No"; do
    case $yn in
        Yes ) break;;
        No ) exit;;
    esac
done

echo
echo
echo

echo "Restoring shared configuration .auto.tfvars files..."
cd "${ACP_REPO_DIR}/platforms/gke/base/_shared_config"
git restore *.auto.tfvars

echo
echo "Reconfiguring the repository..."
cd "${ACP_REPO_DIR}/platforms/gke/base/core/initialize"
rm -rf .terraform backend.tf
git restore backend.tf.bucket
sed -i "s/^\([[:blank:]]*bucket[[:blank:]]*=\).*$/\1 \"${TF_VAR_terraform_bucket_name}\"/" "backend.tf.bucket"
unset TF_VAR_terraform_bucket_name
cp backend.tf.bucket backend.tf
terraform init
terraform apply -auto-approve

echo
echo
echo
source "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/scripts/set_environment_variables.sh"
if [[ "${TF_VAR_terraform_bucket_name}" == "${terraform_project_id}-${unique_identifier_prefix}-terraform" ]]; then
  sed -i "s/\"${TF_VAR_terraform_bucket_name}\"/null/" "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/terraform.auto.tfvars"
fi
rm -rf .terraform terraform.tfstate
terraform init
terraform apply -auto-approve

echo
echo "========================================================================"
echo "|| Now run the deployment script that was used to deploy the platform ||"
echo "========================================================================"
echo
