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

variable "project_id" {
  description = "Project that hosts the config cluster and the external load balancer."
  type        = string
}

variable "name" {
  description = "Base name of every Google Cloud resource created by this terraservice (global address, SSL certificate, SSL policy, Cloud Armor policy)."
  type        = string

  validation {
    # Leaves room for the longest suffix ("-armor") within the 63 character
    # limit of Compute Engine resource names.
    condition     = can(regex("^[a-z]([-a-z0-9]{0,55}[a-z0-9])?$", var.name))
    error_message = "name must be a lowercase RFC 1035 label of at most 57 characters."
  }
}

variable "hostname" {
  description = "Fully qualified host name of the front door. A Cloud Endpoints service with this name is created, so it must be <name>.endpoints.<project_id>.cloud.goog."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]([-a-z0-9]*[a-z0-9])?\\.endpoints\\.[a-z0-9][-a-z0-9.]*\\.cloud\\.goog$", var.hostname))
    error_message = "hostname must have the form <name>.endpoints.<project_id>.cloud.goog."
  }
}

variable "iap_members" {
  description = "Principals that are granted roles/iap.httpsResourceAccessor (IAP-secured Web App User). Only used here when iap_grant_project_level is true; otherwise scripts/deploy-front-door.sh grants the role on the front door backend service only. Public principals are rejected."
  type        = list(string)

  validation {
    condition     = length(var.iap_members) > 0
    error_message = "iap_members must contain at least one principal."
  }

  validation {
    condition = alltrue([
      for m in var.iap_members : !contains(["allusers", "allauthenticatedusers"], lower(trimspace(m)))
    ])
    error_message = "allUsers and allAuthenticatedUsers are not allowed: the front door must never be public."
  }

  validation {
    condition = alltrue([
      for m in var.iap_members : can(regex("^(user|group|serviceAccount|domain):[^\\s]+$|^principal(Set)?://[^\\s]+$", m))
    ])
    error_message = "Each member must be user:, group:, serviceAccount:, domain:, principal://, or principalSet:// followed by an identifier."
  }
}

variable "iap_grant_project_level" {
  description = "When true, grant roles/iap.httpsResourceAccessor to iap_members at the project level. This also grants access to every other IAP-secured web resource in the project, so the default (false) grants the role only on the front door backend service."
  type        = bool
  default     = false
}

variable "cloud_armor_enabled" {
  description = "Create a Cloud Armor backend security policy that only allows cloud_armor_allowed_source_cidrs."
  type        = bool
  default     = false
}

variable "cloud_armor_allowed_source_cidrs" {
  description = "Source IP ranges that the Cloud Armor policy allows. Every other source is denied with HTTP 403 before IAP is evaluated."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for c in var.cloud_armor_allowed_source_cidrs : can(cidrhost(c, 0))])
    error_message = "cloud_armor_allowed_source_cidrs must only contain valid CIDR ranges."
  }
}
