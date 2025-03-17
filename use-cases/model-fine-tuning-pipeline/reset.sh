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
set -o errexit
set -o nounset

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

git restore \
  ${MY_PATH}/data-preparation/gemma-it/manifests/*.yaml \
  ${MY_PATH}/data-preparation/gemma-it/src/cloudbuild.yaml \
  ${MY_PATH}/data-processing/ray/manifests/*.yaml \
  ${MY_PATH}/data-processing/ray/src/cloudbuild.yaml \
  ${MY_PATH}/fine-tuning/pytorch/manifests/*.yaml \
  ${MY_PATH}/fine-tuning/pytorch/src/cloudbuild.yaml \
  ${MY_PATH}/model-eval/manifests/*.yaml \
  ${MY_PATH}/model-eval/src/cloudbuild.yaml
