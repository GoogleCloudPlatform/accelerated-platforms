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
  manifests_directory_root = "${path.module}/../../../kubernetes/manifests"
}

variable "custom_metrics_adapter_version" {
  default     = "0.16.2"
  description = "Version of Custom Metrics Adapter (https://github.com/GoogleCloudPlatform/k8s-stackdriver) to install."
  type        = string
}

variable "inference_gateway_kubernetes_namespace" {
  default     = "gke-gateway"
  description = "The Kubernetes namespace where inference gateway resources will be deployed."
  type        = string
}

variable "inference_gateway_version" {
  default     = "1.0.0"
  description = "Version of Gateway API Inference Extension (https://github.com/kubernetes-sigs/gateway-api-inference-extension) to install."
  type        = string
}

variable "jobset_version" {
  default     = "0.8.2"
  description = "Version of JobSet (https://github.com/kubernetes-sigs/jobset/) to install."
  type        = string
}

variable "kueue_version" {
  default     = "0.13.2"
  description = "Version of Kueue (https://kueue.sigs.k8s.io/) to install."
  type        = string
}

variable "lws_version" {
  default     = "0.7.0"
  description = "Version of LeaderWorkerSet (LWS) (https://github.com/kubernetes-sigs/lws/) to install."
  type        = string
}
