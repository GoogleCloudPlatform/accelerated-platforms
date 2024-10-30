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
SHARED_CONFIG_PATH=${1}

echo "Loading shared configuration(${SHARED_CONFIG_PATH})"
echo "-------------------------------------------------------------------------"
cd ${SHARED_CONFIG_PATH} || exit 1
terraform apply -auto-approve -input=false >/dev/null
terraform output
echo -e "-------------------------------------------------------------------------\n"

eval $(terraform output | sed -r 's/(\".*\")|\s*/\1/g')

echo "Setting environment varibles"
echo "-------------------------------------------------------------------------"
export ACP_TERRAFORM_BUCKET_NAME="${terraform_bucket_name}"
echo "ACP_TERRAFORM_BUCKET_NAME=${ACP_TERRAFORM_BUCKET_NAME}"
echo -e "-------------------------------------------------------------------------\n"
