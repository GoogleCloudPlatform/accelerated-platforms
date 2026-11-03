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

# Bootstraps SHA-256 verified CLI prerequisites (terraform, kustomize, jq,
# sponge, envsubst, curl, unzip) into ${HOME}/.local/bin for multi-region
# inference-ref-arch guides and demo runbook workflows.

set -o errexit
set -o nounset
set -o pipefail

mkdir -p "${HOME}/bin" "${HOME}/.local/bin"
export PATH="${HOME}/bin:${HOME}/.local/bin:${HOME}/google-cloud-sdk/bin:${PATH}"

missing_tools=0
for cmd in jq sponge git curl python3 envsubst unzip; do
  command -v "${cmd}" >/dev/null 2>&1 || missing_tools=1
done
if ((missing_tools)); then
  sudo apt-get update -qq
  sudo apt-get install -y -qq jq moreutils git curl python3 gettext-base unzip ca-certificates
fi

if ! command -v kustomize >/dev/null 2>&1; then
  KUSTOMIZE_VER="5.8.3"
  KUSTOMIZE_SHA256="cb9e31198d3f63b44848bd0afc4c8efc56e6cfef9c93a4a39a211940e6decd61"
  tmp_archive="$(mktemp "/tmp/kustomize_${KUSTOMIZE_VER}_XXXXXX.tar.gz")"
  trap 'rm -f "${tmp_archive}"' EXIT
  curl -fsSL "https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv${KUSTOMIZE_VER}/kustomize_v${KUSTOMIZE_VER}_linux_amd64.tar.gz" -o "${tmp_archive}"
  echo "${KUSTOMIZE_SHA256}  ${tmp_archive}" | sha256sum -c -
  tar -xzf "${tmp_archive}" -C "${HOME}/.local/bin" kustomize
  chmod +x "${HOME}/.local/bin/kustomize"
  rm -f "${tmp_archive}"
  trap - EXIT
fi

if ! command -v terraform >/dev/null 2>&1; then
  TF_VER="1.14.8"
  TF_SHA256="56a5d12f47cbc1c6bedb8f5426ae7d5df984d1929572c24b56f4c82e9f9bf709"
  tmp_zip="$(mktemp "/tmp/terraform_${TF_VER}_XXXXXX.zip")"
  trap 'rm -f "${tmp_zip}"' EXIT
  curl -fsSL "https://releases.hashicorp.com/terraform/${TF_VER}/terraform_${TF_VER}_linux_amd64.zip" -o "${tmp_zip}"
  echo "${TF_SHA256}  ${tmp_zip}" | sha256sum -c -
  unzip -qo "${tmp_zip}" terraform -d "${HOME}/.local/bin"
  chmod +x "${HOME}/.local/bin/terraform"
  rm -f "${tmp_zip}"
  trap - EXIT
fi

echo "Tools ready: terraform=$(terraform version -json | jq -r .terraform_version), kustomize=$(kustomize version)"
