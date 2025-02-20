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

locals {
  # Use this list to deploy examples when the relevant variable is set to true
  examples_templates_to_render = flatten(
    concat(
      var.federated_learning_nvidia_flare_tff_example_deploy ? local.federated_learning_nvidia_flare_tff_example_templates_to_render : [],
    )
  )
}
