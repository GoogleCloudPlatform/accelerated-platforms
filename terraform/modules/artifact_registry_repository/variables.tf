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

variable "format" {
  description = "The format of the repository"
  type        = string
}

variable "location" {
  description = "The location of the repository"
  type        = string
}

variable "project" {
  description = "The project of the repository"
  type        = string
}

variable "reader_members" {
  default     = []
  description = "List of members to have reader permissions to the repository"
  type        = list(string)
}

variable "repo_admin_members" {
  default     = []
  description = "List of members to have repoAdmin permissions to the repository"
  type        = list(string)
}

variable "repository_id" {
  description = "The ID of the repository"
  type        = string
}

variable "writer_members" {
  default     = []
  description = "List of members to have writer permissions to the repository"
  type        = list(string)
}
