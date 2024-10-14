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

module "create-vpc" {
  source = "../../../terraform/modules/network"

  depends_on = [
    google_project_service.compute_googleapis_com
  ]

  network_name     = local.unique_identifier_prefix
  project_id       = data.google_project.environment.project_id
  routing_mode     = var.routing_mode
  subnet_01_ip     = var.subnet_ip_cidr_range
  subnet_01_name   = var.region
  subnet_01_region = var.region
}

module "cloud-nat" {
  source = "../../../terraform/modules/cloud-nat"

  create_router = true
  name          = local.unique_identifier_prefix
  network       = module.create-vpc.vpc
  project_id    = data.google_project.environment.project_id
  region        = var.region
  router        = local.unique_identifier_prefix
}
