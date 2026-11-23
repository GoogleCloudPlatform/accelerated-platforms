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

locals {
  ca_pools = {
    "actor-id-ca-pool" = {
      algorithm = "ED25519"
      curve     = null
    }
    "egress-mitm-ca-pool" = {
      algorithm = "ECDSA"
      curve     = "P256"
    }
    "pod-identity-ca-pool" = {
      algorithm = "ED25519"
      curve     = null
    }
    "postgres-ca-pool" = {
      algorithm = "ED25519"
      curve     = null
    }
    "service-dns-ca-pool" = {
      algorithm = "ED25519"
      curve     = null
    }
  }

  ca_pool_json = {
    for k, v in local.ca_pools : k => jsonencode({
      ActiveForSigning = "1"
      CAs = [
        {
          ID = "1"
          RootCertificateDER = replace(
            replace(
              replace(
                replace(tls_self_signed_cert.ca[k].cert_pem, "-----BEGIN CERTIFICATE-----", ""),
                "-----END CERTIFICATE-----",
                ""
              ),
              "\n",
              ""
            ),
            "\r",
            ""
          )
          SigningKeyPKCS8 = replace(
            replace(
              replace(
                replace(tls_private_key.ca[k].private_key_pem_pkcs8, "-----BEGIN PRIVATE KEY-----", ""),
                "-----END PRIVATE KEY-----",
                ""
              ),
              "\n",
              ""
            ),
            "\r",
            ""
          )
        }
      ]
    })
  }

  b64_std_chars = split("", "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/")
  b64_url_chars = split("", "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")

  actor_jwt_pub_der_b64 = replace(
    replace(
      replace(
        replace(tls_private_key.actor_jwt.public_key_pem, "-----BEGIN PUBLIC KEY-----", ""),
        "-----END PUBLIC KEY-----",
        ""
      ),
      "\n",
      ""
    ),
    "\r",
    ""
  )

  # An ECDSA P-256 SubjectPublicKeyInfo DER has a 27-byte (36 Base64 character)
  # ASN.1 header followed by the 64-byte uncompressed point X (32 bytes) || Y (32 bytes).
  actor_jwt_xy_b64 = substr(local.actor_jwt_pub_der_b64, 36, 86)
  actor_jwt_xy_vals = [
    for ch in split("", local.actor_jwt_xy_b64) : index(local.b64_std_chars, ch)
  ]

  actor_jwt_x_b64url = "${replace(replace(substr(local.actor_jwt_xy_b64, 0, 42), "+", "-"), "/", "_")}${local.b64_url_chars[floor(local.actor_jwt_xy_vals[42] / 4) * 4]}"
  actor_jwt_y_b64url = join("", [
    for j in range(43) : local.b64_url_chars[(local.actor_jwt_xy_vals[42 + j] % 4) * 16 + floor(local.actor_jwt_xy_vals[42 + j + 1] / 4)]
  ])

  actor_jwt_jwks_json = jsonencode({
    keys = [
      {
        alg = "ES256"
        crv = "P-256"
        kid = "1"
        kty = "EC"
        use = "sig"
        x   = local.actor_jwt_x_b64url
        y   = local.actor_jwt_y_b64url
      }
    ]
  })

  actor_jwt_pool_json = jsonencode({
    ActiveForSigning = "1"
    Authorities = [
      {
        Algorithm = "ES256"
        ID        = "1"
        SigningKeyPKCS8 = replace(
          replace(
            replace(
              replace(tls_private_key.actor_jwt.private_key_pem_pkcs8, "-----BEGIN PRIVATE KEY-----", ""),
              "-----END PRIVATE KEY-----",
              ""
            ),
            "\n",
            ""
          ),
          "\r",
          ""
        )
      }
    ]
  })
}

resource "tls_private_key" "ca" {
  for_each = local.ca_pools

  algorithm   = each.value.algorithm
  ecdsa_curve = each.value.curve
}

resource "tls_self_signed_cert" "ca" {
  for_each = local.ca_pools

  allowed_uses = [
    "cert_signing",
    "digital_signature",
  ]
  is_ca_certificate     = true
  private_key_pem       = tls_private_key.ca[each.key].private_key_pem
  validity_period_hours = 8760

  subject {
    common_name = "ate-ca-${each.key}"
  }
}

resource "tls_private_key" "actor_jwt" {
  algorithm   = "ECDSA"
  ecdsa_curve = "P256"
}
