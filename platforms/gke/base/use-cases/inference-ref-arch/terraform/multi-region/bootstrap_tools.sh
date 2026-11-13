#!/usr/bin/env bash
#
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Bootstraps SHA-256 verified CLI prerequisites (terraform >= 1.14.8,
# kustomize >= 5.8.3, jq, sponge, envsubst, curl, unzip, and gcloud beta when
# gcloud is present) into ${HOME}/.local/bin for multi-region
# inference-ref-arch guides and demo runbook workflows.

set -o errexit
set -o nounset
set -o pipefail

CALLER_PATH=":${PATH}:"
mkdir -p "${HOME}/bin" "${HOME}/.local/bin"
export PATH="${HOME}/bin:${HOME}/.local/bin:${HOME}/google-cloud-sdk/bin:${PATH}"

# Succeeds when version $2 is greater than or equal to minimum version $1.
version_at_least() {
  local min_ver="${1}" cur_ver="${2:-}"
  [[ -n "${cur_ver}" ]] || return 1
  [[ "$(printf '%s\n%s\n' "${min_ver}" "${cur_ver}" | sort -V | head -n 1)" == "${min_ver}" ]]
}

missing_tools=0
for cmd in jq sponge git curl python3 envsubst unzip; do
  command -v "${cmd}" >/dev/null 2>&1 || missing_tools=1
done
if ((missing_tools)); then
  sudo apt-get update -qq
  sudo apt-get install -y -qq jq moreutils git curl python3 gettext-base unzip ca-certificates
fi

KUSTOMIZE_VER="5.8.3"
KUSTOMIZE_SHA256="cb9e31198d3f63b44848bd0afc4c8efc56e6cfef9c93a4a39a211940e6decd61"
cur_kustomize_ver=""
if command -v kustomize >/dev/null 2>&1; then
  cur_kustomize_ver="$(kustomize version 2>/dev/null | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -n 1 || true)"
fi
if ! version_at_least "${KUSTOMIZE_VER}" "${cur_kustomize_ver}"; then
  tmp_archive="$(mktemp "/tmp/kustomize_${KUSTOMIZE_VER}_XXXXXX.tar.gz")"
  trap 'rm -f "${tmp_archive}"' EXIT
  curl -fsSL "https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv${KUSTOMIZE_VER}/kustomize_v${KUSTOMIZE_VER}_linux_amd64.tar.gz" -o "${tmp_archive}"
  echo "${KUSTOMIZE_SHA256}  ${tmp_archive}" | sha256sum -c -
  tar -xzf "${tmp_archive}" -C "${HOME}/.local/bin" kustomize
  chmod +x "${HOME}/.local/bin/kustomize"
  rm -f "${tmp_archive}"
  trap - EXIT
  hash -r
fi

TF_VER="1.14.8"
TF_SHA256="56a5d12f47cbc1c6bedb8f5426ae7d5df984d1929572c24b56f4c82e9f9bf709"
cur_tf_ver=""
if command -v terraform >/dev/null 2>&1; then
  cur_tf_ver="$(terraform version -json 2>/dev/null | jq -r '.terraform_version // empty' 2>/dev/null || true)"
  if [[ -z "${cur_tf_ver}" ]]; then
    cur_tf_ver="$(terraform version 2>/dev/null | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -n 1 || true)"
  fi
fi
if ! version_at_least "${TF_VER}" "${cur_tf_ver}"; then
  tmp_zip="$(mktemp "/tmp/terraform_${TF_VER}_XXXXXX.zip")"
  trap 'rm -f "${tmp_zip}"' EXIT
  curl -fsSL "https://releases.hashicorp.com/terraform/${TF_VER}/terraform_${TF_VER}_linux_amd64.zip" -o "${tmp_zip}"
  echo "${TF_SHA256}  ${tmp_zip}" | sha256sum -c -
  unzip -qo "${tmp_zip}" terraform -d "${HOME}/.local/bin"
  chmod +x "${HOME}/.local/bin/terraform"
  rm -f "${tmp_zip}"
  trap - EXIT
  hash -r
fi

# Ensure gcloud beta is installed non-interactively (needed by provision.sh
# when ENABLE_POD_SNAPSHOTS=true).
if command -v gcloud >/dev/null 2>&1 && ! gcloud --quiet beta --help >/dev/null 2>&1; then
  if ! gcloud --quiet components install beta >/dev/null 2>&1; then
    sudo apt-get update -qq && sudo apt-get install -y -qq google-cloud-cli
  fi
  gcloud --quiet beta --help >/dev/null 2>&1
fi

echo "Tools ready: terraform=$(terraform version -json | jq -r .terraform_version), kustomize=$(kustomize version)"
if [[ "${CALLER_PATH}" != *":${HOME}/.local/bin:"* ]]; then
  echo "Ensure \${HOME}/.local/bin is in your shell PATH: export PATH=\"\${HOME}/.local/bin:\${PATH}\""
fi
