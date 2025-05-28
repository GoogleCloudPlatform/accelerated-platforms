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
  federated_learning_cross_device_example_spanner_schema_base_directory_path = "${path.module}/../example_cross_device/spanner/schema"
  # Read all .sdl files from the schema directory
  schema_files = fileset(local.federated_learning_cross_device_example_spanner_schema_base_directory_path, "*.sdl")

  # Read each file's content
  file_contents = {
    for file in local.schema_files :
    file => file("${local.federated_learning_cross_device_example_spanner_schema_base_directory_path}/${file}")
  }

  # Process the content of each file to extract DDL statements
  raw_statements = flatten([
    for content in values(local.file_contents) : split("CREATE", content)
  ])

  # Clean up and format statements
  ddl_statements = [
    for stmt in local.raw_statements :
    "CREATE${stmt}"
    if trimspace(stmt) != ""
  ]
}

# Create the Spanner instance
resource "google_spanner_instance" "federated_learning_spanner_instance" {
  name             = local.spanner_instance_name
  config           = "regional-${var.cluster_region}"
  display_name     = "Federated Compute Database"
  processing_units = var.federated_learning_spanner_processing_units == null ? var.federated_learning_spanner_nodes * 1000 : var.federated_learning_spanner_processing_units
  force_destroy    = true
  project          = data.google_project.default.project_id

  labels = {
    environment = var.platform_name
    purpose     = "federated-compute"
  }

  lifecycle {
    prevent_destroy = false
    ignore_changes = [
      processing_units,
      labels,
      display_name,
      config,
      force_destroy,
    ]
  }

  depends_on = [
    google_project_service.spanner_googleapis_com
  ]
}

# Create the Spanner database with deletion protection disabled
resource "google_spanner_database" "federated_learning_spanner_database" {
  instance                 = google_spanner_instance.federated_learning_spanner_instance.name
  name                     = local.spanner_database_name
  project                  = data.google_project.default.project_id
  version_retention_period = var.federated_learning_spanner_database_retention_period
  deletion_protection      = var.federated_learning_spanner_database_deletion_protection

  ddl = [
    for stmt in local.ddl_statements :
    replace(
      replace(
        trimspace(stmt),
        "\n",
        " "
      ),
      ",)",
      ")"
    )
  ]

  lifecycle {
    ignore_changes = [
      deletion_protection
    ]
  }

  depends_on = [
    google_spanner_instance.federated_learning_spanner_instance
  ]
}

resource "google_spanner_database" "federated_learning_spanner_lock_database" {
  instance            = google_spanner_instance.federated_learning_spanner_instance.name
  name                = join("-", [local.unique_identifier_prefix, var.federated_learning_spanner_lock_database_name])
  project             = data.google_project.default.project_id
  deletion_protection = var.federated_learning_spanner_database_deletion_protection
  // Spring JDBC Lock Registry DDL
  // https://docs.spring.io/spring-integration/reference/jdbc/lock-registry.html
  database_dialect = "POSTGRESQL"
  ddl = [
    <<-EOT
    CREATE TABLE INT_LOCK (
      LOCK_KEY VARCHAR(36),
      REGION VARCHAR(100),
      CLIENT_ID VARCHAR(36),
      CREATED_DATE TIMESTAMPTZ NOT NULL,
      PRIMARY KEY (LOCK_KEY, REGION)
    )
    EOT
  ]
}
