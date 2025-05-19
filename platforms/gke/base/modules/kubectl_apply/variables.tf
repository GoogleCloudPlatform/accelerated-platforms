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

variable "apply_once" {
  default     = true
  description = "Apply the manifest only once, any changes to the manifest will be ignored"
  type        = bool
}

variable "apply_server_side" {
  default     = false
  description = "Apply the manifest server side."
  type        = bool
}

variable "error_on_delete_failure" {
  default     = false
  description = "Error if deleting the resource fails."
  type        = bool
}

variable "kubeconfig_file" {
  description = "Path to the kubeconfig file to use for the kubectl commands."
  type        = string
}

variable "manifest" {
  description = "Path to the manifest or directory of manifests to apply."
  type        = string
}

variable "manifest_can_be_updated" {
  default     = false
  description = "The manifest be updated with a subsequent apply."
  type        = bool
}

variable "manifest_includes_namespace" {
  default     = false
  description = "Do the manifest includes the namespace."
  type        = bool
}

variable "namespace" {
  default     = "default"
  description = "The Kubernetes namespace to apply the manifest to."
  type        = string
}

variable "recursive" {
  default     = false
  description = "Run the command with the --recursive flag."
  type        = bool
}

variable "source_content_hash" {
  default     = ""
  description = "Hash of the contents of the source files. Can be used to trigger a new kubectl apply whenever the source contents change."
  type        = string
}

variable "use_kustomize" {
  default     = false
  description = "Does the manifest use kustomize."
  type        = string
}
