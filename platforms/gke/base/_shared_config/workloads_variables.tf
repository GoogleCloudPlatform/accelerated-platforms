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

#
# Configuration dependencies
#

locals {
  manifests_directory_root = "${path.module}/../../../kubernetes/manifests"
}

variable "jobset_version" {
  default     = "0.8.0"
  description = "Version of JobSet (https://github.com/kubernetes-sigs/jobset/) to install."
  type        = string
}

variable "kueue_version" {
  default     = "0.10.2"
  description = "Version of Kueue (https://kueue.sigs.k8s.io/) to install."
  type        = string
}

variable "lws_version" {
  default     = "0.5.1"
  description = "Version of LeaderWorkerSet (LWS) (https://github.com/kubernetes-sigs/lws/) to install."
  type        = string
}

variable "nvidia_dcgm_exporter_image" {
  default     = "nvcr.io/nvidia/k8s/dcgm-exporter:4.1.1-4.0.4-ubuntu22.04"
  description = "NVIDIA Data Center GPU Manager (DCGM) Exporter image (https://hub.docker.com/r/nvidia/dcgm-exporter/tags) to install."
  type        = string
}

variable "nvidia_dcgm_image" {
  default     = "nvcr.io/nvidia/cloud-native/dcgm:4.1.1-1-ubuntu22.04"
  description = "NVIDIA Data Center GPU Manager (DCGM) image (https://hub.docker.com/r/nvidia/dcgm-exporter/tags) to install."
  type        = string
}

variable "nvidia_dcgm_version" {
  default     = "4.1.1-1"
  description = "NVIDIA Data Center GPU Manager (DCGM) version to install. The corresponding image should be used for the 'nvidia_dcgm_image' amd 'nvidia_dcgm_exporter_image' variables."
  type        = string
}
