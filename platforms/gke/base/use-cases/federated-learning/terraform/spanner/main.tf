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

locals {
  spanner_ddl_statements = [
    "CREATE TABLE Aggregations (AggregationId STRING(36) NOT NULL,TaskId STRING(36) NOT NULL,Status STRING(20) NOT NULL,CreatedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),UpdatedAt TIMESTAMP OPTIONS (allow_commit_timestamp=true),CompletedAt TIMESTAMP,Parameters JSON) PRIMARY KEY (AggregationId)",
    "CREATE INDEX AggregationsByTask ON Aggregations(TaskId)",
    "CREATE INDEX AggregationsByStatus ON Aggregations(Status)",
    "CREATE TABLE Clients (ClientId STRING(36) NOT NULL,Status STRING(20) NOT NULL,LastSeen TIMESTAMP OPTIONS (allow_commit_timestamp=true),Properties JSON) PRIMARY KEY (ClientId)",
    "CREATE INDEX ClientsByStatus ON Clients(Status)",
    "CREATE TABLE ModelMetrics (PopulationName STRING(64) NOT NULL,TaskId INT64 NOT NULL,IterationId INT64 NOT NULL,MetricName STRING(64) NOT NULL,MetricValue FLOAT64 NOT NULL,CreatedTime TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true)) PRIMARY KEY(PopulationName, TaskId, IterationId, MetricName)",
    "CREATE INDEX ModelMetricsCreatedTimeIndex ON ModelMetrics(CreatedTime)",
    "CREATE TABLE Models (ModelId STRING(36) NOT NULL,Version INT64 NOT NULL,Status STRING(20) NOT NULL,CreatedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),UpdatedAt TIMESTAMP OPTIONS (allow_commit_timestamp=true),Parameters JSON) PRIMARY KEY (ModelId, Version)",
    "CREATE INDEX ModelsByStatus ON Models(Status)",
    "CREATE TABLE Tasks (TaskId STRING(36) NOT NULL,ModelId STRING(36) NOT NULL,Status STRING(20) NOT NULL,CreatedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),UpdatedAt TIMESTAMP OPTIONS (allow_commit_timestamp=true),CompletedAt TIMESTAMP,Parameters JSON) PRIMARY KEY (TaskId)",
    "CREATE INDEX TasksByStatus ON Tasks(Status)",
    "CREATE INDEX TasksByModel ON Tasks(ModelId)",
    "CREATE TABLE Task (PopulationName STRING(64) NOT NULL,TaskId INT64 NOT NULL,TotalIteration INT64,MinAggregationSize INT64,MaxAggregationSize INT64,Status INT64,CreatedTime TIMESTAMP,StartTime TIMESTAMP,StopTime TIMESTAMP,StartTaskNoEarlierThan TIMESTAMP,DoNotCreateIterationAfter TIMESTAMP,MaxParallel INT64,CorrelationId STRING(MAX),MinClientVersion STRING(32),MaxClientVersion STRING(32),Info JSON NOT NULL) PRIMARY KEY(PopulationName,TaskId)",
    "CREATE INDEX TaskStatusIndex ON Task(Status)",
    "CREATE INDEX TaskPopulationStatusMinClientIndex ON Task(PopulationName, Status, MinClientVersion)",
    "CREATE INDEX TaskPopulationStatusMaxClientIndex ON Task(PopulationName, Status, MaxClientVersion)",
    "CREATE INDEX TaskMinCorrelationIdIndex ON Task(CorrelationId)",
    "CREATE TABLE TaskStatusHistory (PopulationName STRING(64) NOT NULL,TaskId INT64 NOT NULL,StatusId INT64 NOT NULL,Status INT64 NOT NULL,CreatedTime TIMESTAMP NOT NULL) PRIMARY KEY(PopulationName, TaskId, StatusId), INTERLEAVE IN PARENT Task ON DELETE CASCADE",
    "CREATE INDEX TaskStatusHistoryStatusIndex ON TaskStatusHistory(PopulationName, TaskId, Status)",
    "CREATE INDEX TaskStatusHistoryCreatedTimeIndex ON TaskStatusHistory(CreatedTime)",
    "CREATE TABLE Iteration (PopulationName STRING(64) NOT NULL,TaskId INT64 NOT NULL,IterationId INT64 NOT NULL,AttemptId INT64 NOT NULL,Status INT64 NOT NULL,BaseIterationId INT64 NOT NULL,BaseOnResultId INT64 NOT NULL,ReportGoal INT64 NOT NULL,ExpirationTime TIMESTAMP,ResultId INT64 NOT NULL,Info JSON NOT NULL,AggregationLevel INT64 NOT NULL,MaxAggregationSize INT64 NOT NULL,MinClientVersion STRING(32) NOT NULL,MaxClientVersion STRING(32) NOT NULL) PRIMARY KEY(PopulationName, TaskId, IterationId, AttemptId), INTERLEAVE IN PARENT Task ON DELETE CASCADE",
    "CREATE INDEX IterationStatusIndex ON Iteration(Status)",
    "CREATE INDEX IterationPopulationNameStatusClientVersionIndex ON Iteration (PopulationName, Status, MinClientVersion, MaxClientVersion) STORING (BaseIterationId, BaseOnResultId, ReportGoal, ResultId, Info, AggregationLevel, MaxAggregationSize)",
    "CREATE TABLE IterationStatusHistory (PopulationName STRING(64) NOT NULL,TaskId INT64 NOT NULL,IterationId INT64 NOT NULL,AttemptId INT64 NOT NULL,StatusId INT64 NOT NULL,Status INT64 NOT NULL,CreatedTime TIMESTAMP NOT NULL,AggregationLevel INT64 NOT NULL) PRIMARY KEY(PopulationName, TaskId, IterationId, AttemptId, StatusId), INTERLEAVE IN PARENT Iteration ON DELETE CASCADE",
    "CREATE INDEX IterationStatusHistoryStatusIndex ON IterationStatusHistory(PopulationName, TaskId, IterationId, AttemptId, Status, AggregationLevel)",
    "CREATE INDEX IterationStatusHistoryCreatedTimeIndex ON IterationStatusHistory(CreatedTime)",
    "CREATE TABLE Assignment (PopulationName STRING(64) NOT NULL,TaskId INT64 NOT NULL,IterationId INT64 NOT NULL,AttemptId INT64 NOT NULL,SessionId STRING(64) NOT NULL,CorrelationId STRING(MAX),Status INT64 NOT NULL,CreatedTime TIMESTAMP NOT NULL,BatchId STRING(64)) PRIMARY KEY(PopulationName, TaskId, IterationId, AttemptId, SessionId), INTERLEAVE IN PARENT Iteration ON DELETE CASCADE",
    "CREATE INDEX AssignmentStatusIndex ON Assignment(PopulationName, TaskId, IterationId, AttemptId, Status)",
    "CREATE TABLE AssignmentStatusHistory (PopulationName STRING(64) NOT NULL,TaskId INT64 NOT NULL,IterationId INT64 NOT NULL,AttemptId INT64 NOT NULL,SessionId STRING(64) NOT NULL,StatusId INT64 NOT NULL,Status INT64 NOT NULL,CreatedTime TIMESTAMP NOT NULL,BatchId STRING(64)) PRIMARY KEY(PopulationName, TaskId, IterationId, AttemptId, SessionId, StatusId), INTERLEAVE IN PARENT Assignment ON DELETE CASCADE",
    "CREATE INDEX AssignmentStatusHistoryStatusBatchIdIndex ON AssignmentStatusHistory(PopulationName, TaskId, IterationId, AttemptId, Status, BatchId)",
    "CREATE INDEX AssignmentStatusHistoryStatusCreatedTimeIndex ON AssignmentStatusHistory(PopulationName, TaskId, IterationId, AttemptId, Status, CreatedTime)",
    "CREATE TABLE AggregationBatch (PopulationName STRING(64) NOT NULL,TaskId INT64 NOT NULL,IterationId INT64 NOT NULL,AttemptId INT64 NOT NULL,BatchId STRING(64) NOT NULL,AggregationLevel INT64 NOT NULL,Status INT64 NOT NULL,BatchSize INT64 NOT NULL,CreatedByPartition STRING(64) NOT NULL,CreatedTime TIMESTAMP NOT NULL,AggregatedBy STRING(64)) PRIMARY KEY(PopulationName, TaskId, IterationId, AttemptId, BatchId), INTERLEAVE IN PARENT Iteration ON DELETE CASCADE",
    "CREATE INDEX AggregationBatchAggregationLevelStatusIndex ON AggregationBatch(PopulationName, TaskId, IterationId, AttemptId, AggregationLevel, Status, CreatedByPartition) STORING (BatchSize)",
    "CREATE TABLE AggregationBatchStatusHistory (PopulationName STRING(64) NOT NULL,TaskId INT64 NOT NULL,IterationId INT64 NOT NULL,AttemptId INT64 NOT NULL,BatchId STRING(64) NOT NULL,StatusId INT64 NOT NULL,AggregationLevel INT64 NOT NULL,Status INT64 NOT NULL,CreatedByPartition STRING(64) NOT NULL,CreatedTime TIMESTAMP NOT NULL,AggregatedBy STRING(64)) PRIMARY KEY(PopulationName, TaskId, IterationId, AttemptId, BatchId, StatusId), INTERLEAVE IN PARENT AggregationBatch ON DELETE CASCADE",
    "CREATE INDEX AggregationBatchStatusHistoryAggregationLevelStatusIndex ON AggregationBatchStatusHistory(PopulationName, TaskId, IterationId, AttemptId, AggregationLevel, Status, CreatedByPartition)",
    "CREATE TABLE AllowedAuthorizationToken (Token STRING(64) NOT NULL,CreatedAt TIMESTAMP NOT NULL,ExpiredAt TIMESTAMP NOT NULL) PRIMARY KEY(Token), ROW DELETION POLICY (OLDER_THAN(ExpiredAt, INTERVAL 0 DAY))"
  ]

  spanner_ddl_postgres_statements = [
    "CREATE TABLE INT_LOCK (LOCK_KEY VARCHAR(36), REGION VARCHAR(100), CLIENT_ID VARCHAR(36), CREATED_DATE TIMESTAMPTZ NOT NULL, PRIMARY KEY (LOCK_KEY, REGION))"
  ]
}

# Wait for Spanner API to be enabled
resource "terraform_data" "wait_for_spanner_api" {
  depends_on = [
    google_project_service.spanner_googleapis_com,
  ]

  provisioner "local-exec" {
    command = <<EOT
retries=12
until gcloud spanner instances list --quiet --project="${data.google_project.cluster.project_id}"
do
  if ((retries <= 0)); then
    exit 1
  fi

  retries=$((retries - 1))
  echo "Waiting for Cloud Spanner API to be enabled..."
  sleep 5
done
EOT
  }
}

# Create the Spanner instance
resource "google_spanner_instance" "federated_learning_spanner_instance" {
  depends_on = [
    terraform_data.wait_for_spanner_api,
  ]

  name             = local.federated_learning_cross_device_example_spanner_instance_name
  project          = google_project_service.spanner_googleapis_com.project
  config           = "regional-${local.cluster_region}"
  display_name     = "Federated Compute Database"
  processing_units = var.federated_learning_cross_device_example_spanner_processing_units == null ? var.federated_learning_cross_device_example_spanner_nodes * 1000 : var.federated_learning_cross_device_example_spanner_processing_units
  force_destroy    = true

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
}

# Create the Spanner database with deletion protection disabled
resource "google_spanner_database" "federated_learning_spanner_database" {
  instance                 = google_spanner_instance.federated_learning_spanner_instance.name
  name                     = local.federated_learning_cross_device_example_spanner_database_name
  project                  = google_project_service.spanner_googleapis_com.project
  version_retention_period = var.federated_learning_cross_device_example_spanner_database_retention_period
  deletion_protection      = var.federated_learning_cross_device_example_spanner_database_deletion_protection

  ddl = local.spanner_ddl_statements

  lifecycle {
    ignore_changes = [
      deletion_protection
    ]
  }
}

resource "google_spanner_database" "federated_learning_spanner_lock_database" {
  instance            = google_spanner_instance.federated_learning_spanner_instance.name
  name                = local.federated_learning_cross_device_example_spanner_lock_database_name
  project             = google_project_service.spanner_googleapis_com.project
  deletion_protection = var.federated_learning_cross_device_example_spanner_database_deletion_protection
  // Spring JDBC Lock Registry DDL
  // https://docs.spring.io/spring-integration/reference/jdbc/lock-registry.html
  database_dialect = "POSTGRESQL"
  ddl              = local.spanner_ddl_postgres_statements
}
