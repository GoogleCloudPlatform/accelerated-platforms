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

variable "agent_sandbox_version" {
  default     = "0.4.6"
  description = "Version of Agent Sandbox (https://github.com/kubernetes-sigs/agent-sandbox) to install."
  type        = string
}

variable "custom_metrics_adapter_version" {
  default     = "0.16.7"
  description = "Version of Custom Metrics Adapter (https://github.com/GoogleCloudPlatform/k8s-stackdriver) to install."
  type        = string
}

variable "inference_gateway_kubernetes_namespace" {
  default     = "gke-gateway"
  description = "The Kubernetes namespace where inference gateway resources will be deployed."
  type        = string
}

variable "inference_gateway_version" {
  default     = "1.5.0"
  description = "Version of Gateway API Inference Extension (https://github.com/kubernetes-sigs/gateway-api-inference-extension) to install."
  type        = string
}

variable "jobset_version" {
  default     = "0.12.0"
  description = "Version of JobSet (https://github.com/kubernetes-sigs/jobset/) to install."
  type        = string
}

variable "kuberay_version" {
  default     = "1.6.1"
  description = "Version of KubeRay (https://github.com/ray-project/kuberay) to install."
  type        = string
}

variable "kueue_version" {
  default     = "0.17.2"
  description = "Version of Kueue (https://github.com/kubernetes-sigs/kueue) to install."
  type        = string
}

variable "lws_version" {
  default     = "0.8.0"
  description = "Version of LeaderWorkerSet (LWS) (https://github.com/kubernetes-sigs/lws/) to install."
  type        = string
}

variable "pathways_version" {
  default     = "0.1.4"
  description = "Version of Pathways (https://github.com/google/pathways-job) to install."
  type        = string
}
