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

variable "kubeconfig_file" {
  description = "Path to the kubeconfig file to use for the kubectl commands."
  type        = string
}

variable "filename" {
  default     = null
  description = "Filename or path containing the resources."
  type        = string
}

variable "for" {
  description = "The condition to wait on: [create|delete|condition=condition-name[=condition-value]|jsonpath='{JSONPath expression}'=[JSONPath value]]. The default condition-value is true. Condition values are compared after Unicode simple case folding, which is a more general form of case-insensitivity."
  type        = string
}

variable "namespace" {
  default     = null
  description = "The Kubernetes namespace to apply the manifest to."
  type        = string
}

variable "resource" {
  default     = null
  description = "Resources to wait for a specific condition on."
  type        = string
}

variable "selector" {
  default     = null
  description = "Selector (label query) to filter on, supports '=', '==', and '!='.(e.g. -l key1=value1,key2=value2)"
  type        = string
}

variable "timeout" {
  default     = "30s"
  description = "The length of time to wait before giving up. Zero means check once and don't wait, negative means wait for a week."
  type        = string
}
