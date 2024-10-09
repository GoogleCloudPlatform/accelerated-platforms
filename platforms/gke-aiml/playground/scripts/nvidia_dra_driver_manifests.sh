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
set -u

SCRIPT_PATH="$(
    cd "$(dirname "$0")" >/dev/null 2>&1
    pwd -P
)"

source ${SCRIPT_PATH}/helpers/clone_git_repo.sh

# Set directory and path variables
clusters_directory="manifests/clusters"
clusters_path="${GIT_REPOSITORY_PATH}/${clusters_directory}"
cluster_template_directory="templates/_cluster_template"
cluster_template_path="${GIT_REPOSITORY_PATH}/${cluster_template_directory}"
repo_container_images_url="${MLP_AR_REPO_URL}"

cd "${clusters_path}" || {
    echo "Clusters directory '${clusters_directory}' does not exist"
    exit 100
}

echo "'${repo_container_images_url}'"

cp -pr ${cluster_template_path}/dra/nvidia-dra-drivers ${clusters_path}/
cp -pr ${cluster_template_path}/namespace-nvidia.yaml ${clusters_path}/

# Added entries to the kustomization file
resources=$(find ${clusters_path} -maxdepth 1 -mindepth 1 -type d | sort)
resources+=" "
export resources+=$(find ${clusters_path} -maxdepth 1 -type f -name "*.yaml" ! -name "kustomization.yaml" ! -name "*values.yaml" | sort)
export kustomization_file="${clusters_path}/kustomization.yaml"
source ${SCRIPT_PATH}/helpers/add_to_kustomization.sh

#TODO: build the image here as well
# something like `./${k8s-nvidia-driver-path}/demo/clusters/kind/scripts/build-driver-image.sh`
docker tag nvcr.io/nvidia/cloud-native/k8s-dra-driver:v0.1.0 ${repo_container_images_url}
docker push ${repo_container_images_url}

# Add, commit, and push changes to the repository
cd ${GIT_REPOSITORY_PATH}
git add .
git commit -m "Manifests for NVIDIA DRA"
git push origin
