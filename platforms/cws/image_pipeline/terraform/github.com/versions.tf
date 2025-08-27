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

terraform {
  required_version = ">= 1.5.7"

  required_providers {
    github = {
      source  = "integrations/github"
      version = "6.6.0"
    }
    google = {
      source  = "hashicorp/google"
      version = "6.49.2"
    }
  }

  provider_meta "google" {
    module_name = "cloud-solutions/acp_cws_image-pipeline_github_deploy-v1"
  }
}

provider "github" {
  owner = var.cloudbuild_cws_image_pipeline_git_namespace
  token = trimspace(data.google_secret_manager_secret_version.git_token_latest.secret_data)
}
