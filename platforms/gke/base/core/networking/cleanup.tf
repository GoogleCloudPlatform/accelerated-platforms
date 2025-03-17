# Copyright 2025 Google LLC
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

resource "terraform_data" "cleanup_network_endpoint_groups" {
  depends_on = [
    google_compute_network.vpc
  ]

  input = {
    project_id = var.cluster_project_id
    identifier = local.unique_identifier_prefix
  }

  provisioner "local-exec" {
    command     = <<EOT
      echo "Cleaning up network endpoint groups..."
      negs=$(gcloud compute network-endpoint-groups list --filter="name~'k8s.*-.*' AND network~'${self.input.identifier}$'" --format='value(format("{0},{1}", name, zone.basename()))' --project=${self.input.project_id})
      for neg in $${negs}; do
          name="$${neg%,*}"
          zone="$${neg#*,}"

          echo "Deleting '$${name}' network endpoint group in $${zone}..."
          gcloud compute network-endpoint-groups delete $${name} --project=${self.input.project_id} --quiet --zone=$${zone}
      done
    EOT
    interpreter = ["bash", "-c"]
    when        = destroy
    working_dir = path.root
  }
}
