# Copyright 2026 Google LLC
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
  repo_root = abspath("${path.module}/../../../../../../..")

  secure_runtime_images = {
    runner = {
      dir         = "container-images/cpu/secure-runtime-runner"
      destination = local.secure_runtime_runner_image_url
    }
    intent_extproc = {
      dir         = "container-images/cpu/secure-runtime-intent-extproc"
      destination = local.secure_runtime_intent_extproc_image_url
    }
    agent = {
      dir         = "container-images/cpu/secure-runtime-agent"
      destination = local.secure_runtime_agent_image_url
    }
  }
}

resource "terraform_data" "build_secure_runtime_images" {
  for_each = local.secure_runtime_images

  input = {
    cloudbuild_project_id         = local.cloudbuild_project_id
    cloudbuild_service_account_id = local.cloudbuild_service_account_id
    cloudbuild_source_bucket_name = local.cloudbuild_source_bucket_name
    dir                           = each.value.dir
    image_destination             = each.value.destination
    repo_root                     = local.repo_root
    substrate_version             = var.agent_substrate_version
  }

  provisioner "local-exec" {
    command     = <<-EOT
export PATH="$${HOME}/.local/bin:$${HOME}/google-cloud-sdk/bin:$${PATH}"
gcloud builds submit "${self.input.dir}" \
--config="${self.input.dir}/cloudbuild.yaml" \
--gcs-source-staging-dir="gs://${self.input.cloudbuild_source_bucket_name}/source" \
--project="${self.input.cloudbuild_project_id}" \
--quiet \
--service-account="${self.input.cloudbuild_service_account_id}" \
--substitutions=_DESTINATION="${self.input.image_destination}"
EOT
    interpreter = ["bash", "-c"]
    working_dir = self.input.repo_root
  }

  triggers_replace = {
    cloudbuild_yaml_hash = filebase64sha256("${local.repo_root}/${each.value.dir}/cloudbuild.yaml")
    dockerfile_hash      = filebase64sha256("${local.repo_root}/${each.value.dir}/Dockerfile")
    image_destination    = each.value.destination
    source_hash          = sha256(join("", [for file in fileset("${local.repo_root}/${each.value.dir}/src", "**") : filesha256("${local.repo_root}/${each.value.dir}/src/${file}")]))
  }
}
