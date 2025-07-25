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

# KeyRings cannot be deleted; append a random suffix to the keyring name
resource "random_id" "keyring_suffix" {
  byte_length = 4
}

resource "google_kms_key_ring" "key_ring" {
  location = var.cluster_region
  name     = "${local.unique_identifier_prefix}-keyring-${random_id.keyring_suffix.hex}"
  project  = google_project_service.cloudkms_googleapis_com.project
}

resource "google_kms_crypto_key" "cluster_secrets_key" {
  import_only                   = false
  key_ring                      = google_kms_key_ring.key_ring.id
  name                          = "${local.unique_identifier_prefix}-clusterSecretsKey"
  purpose                       = "ENCRYPT_DECRYPT"
  rotation_period               = "7776000s"
  skip_initial_version_creation = false

  lifecycle {
    prevent_destroy = false
  }

  version_template {
    # Ref: https://cloud.google.com/kms/docs/reference/rest/v1/CryptoKeyVersionAlgorithm
    algorithm = "GOOGLE_SYMMETRIC_ENCRYPTION"

    # Ref: https://cloud.google.com/kms/docs/reference/rest/v1/ProtectionLevel
    protection_level = "SOFTWARE"
  }
}

resource "google_kms_crypto_key_iam_binding" "cluster_secrets_decrypters" {
  crypto_key_id = google_kms_crypto_key.cluster_secrets_key.id
  # Ref: https://cloud.google.com/kubernetes-engine/docs/how-to/encrypting-secrets#grant_permission_to_use_the_key
  # Ref: https://cloud.google.com/kubernetes-engine/docs/how-to/using-cmek#grant_permission
  members = [local.gke_robot_service_account_iam_email, local.compute_system_service_account_iam_email]
  role    = "roles/cloudkms.cryptoKeyDecrypter"

  depends_on = [
    # Wait for the GKE robot account to be created
    google_project_service.container_googleapis_com,
  ]
}

resource "google_kms_crypto_key_iam_binding" "cluster_secrets_encrypters" {
  crypto_key_id = google_kms_crypto_key.cluster_secrets_key.id
  # Ref: https://cloud.google.com/kubernetes-engine/docs/how-to/encrypting-secrets#grant_permission_to_use_the_key
  # Ref: https://cloud.google.com/kubernetes-engine/docs/how-to/using-cmek#grant_permission
  members = [local.gke_robot_service_account_iam_email, local.compute_system_service_account_iam_email]
  role    = "roles/cloudkms.cryptoKeyEncrypter"

  depends_on = [
    # Wait for the GKE robot account to be created
    google_project_service.container_googleapis_com,
  ]
}
