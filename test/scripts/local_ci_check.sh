#!/usr/bin/env bash

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

set -o errexit
set -o nounset
set -o pipefail

# Determine repository root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." >/dev/null 2>&1 && pwd -P)"

cd "${REPO_ROOT}"

# Color output helpers
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARNING]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Flags
RUN_KUSTOMIZE=false
RUN_PRETTIER=false
RUN_LICENSE=false
AUTO_FIX=false

usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Local CI Test Runner for Accelerated Platforms

Options:
  -a, --all         Run all local CI checks (Kustomize, Prettier, License)
  -k, --kustomize   Validate Kustomize manifests
  -p, --prettier    Check Markdown formatting with Prettier
  -l, --license     Check for missing Google LLC license headers
  -f, --fix         Automatically fix Prettier formatting and apply headers
  -h, --help        Show this help message

Examples:
  $(basename "$0") --all
  $(basename "$0") -p -f    # Check and fix Prettier formatting
  $(basename "$0") -k       # Validate Kustomize manifests only
EOF
  exit 0
}

if [ $# -eq 0 ]; then
  RUN_KUSTOMIZE=true
  RUN_PRETTIER=true
  RUN_LICENSE=true
fi

while [ $# -gt 0 ]; do
  case "$1" in
    -a|--all)
      RUN_KUSTOMIZE=true
      RUN_PRETTIER=true
      RUN_LICENSE=true
      ;;
    -k|--kustomize)
      RUN_KUSTOMIZE=true
      ;;
    -p|--prettier)
      RUN_PRETTIER=true
      ;;
    -l|--license)
      RUN_LICENSE=true
      ;;
    -f|--fix)
      AUTO_FIX=true
      ;;
    -h|--help)
      usage
      ;;
    *)
      error "Unknown option: $1"
      usage
      ;;
  esac
  shift
done

# Locate Node.js binary
NODE_BIN=""
if command -v node >/dev/null 2>&1; then
  NODE_BIN="$(command -v node)"
else
  NODE_BIN="$(which node 2>/dev/null || true)"
fi

# Locate Prettier CLI
PRETTIER_CLI=""
PRETTIER_DOWNLOAD_DIR="/tmp/prettier342"
if [ -d "${PRETTIER_DOWNLOAD_DIR}/package/bin" ]; then
  PRETTIER_CLI="${PRETTIER_DOWNLOAD_DIR}/package/bin/prettier.cjs"
fi

# Function: Prettier Formatting Check
check_prettier() {
  info "Checking Markdown formatting with Prettier..."
  if [ -z "${NODE_BIN}" ]; then
    warn "Node.js not found. Skipping Prettier check."
    return 0
  fi

  if [ -z "${PRETTIER_CLI}" ]; then
    info "Prettier v3.4.2 not cached locally. Downloading..."
    mkdir -p "${PRETTIER_DOWNLOAD_DIR}"
    curl -sSL "https://registry.npmjs.org/prettier/-/prettier-3.4.2.tgz" -o /tmp/prettier-3.4.2.tgz >/dev/null 2>&1 || true
    if [ -f /tmp/prettier-3.4.2.tgz ]; then
      tar -xzf /tmp/prettier-3.4.2.tgz -C "${PRETTIER_DOWNLOAD_DIR}" >/dev/null 2>&1 || true
      PRETTIER_CLI="${PRETTIER_DOWNLOAD_DIR}/package/bin/prettier.cjs"
    fi
  fi

  if [ ! -f "${PRETTIER_CLI}" ]; then
    warn "Unable to locate or download Prettier CLI. Skipping."
    return 0
  fi

  MODE="--check"
  if [ "${AUTO_FIX}" == "true" ]; then
    MODE="--write"
    info "Running Prettier in auto-fix mode (--write)..."
  fi

  if "${NODE_BIN}" "${PRETTIER_CLI}" --config .prettierrc ${MODE} "**/*.md"; then
    success "Prettier check passed!"
  else
    error "Prettier formatting check failed."
    info "Run '$(basename "$0") -p -f' to auto-fix formatting issues."
    return 1
  fi
}

# Function: License Header Check
check_license() {
  info "Checking Google LLC license headers..."
  MISSING_LICENSE=0

  # Check modified/untracked files in git
  FILES="$(git status --porcelain | awk '{print $2}' | grep -E '\.(yaml|yml|sh|py|go|tf)$' || true)"

  for file in ${FILES}; do
    if [ -f "${file}" ]; then
      if ! head -n 15 "${file}" | grep -qi "Copyright.*Google LLC"; then
        error "Missing Google LLC license header: ${file}"
        MISSING_LICENSE=$((MISSING_LICENSE + 1))

        if [ "${AUTO_FIX}" == "true" ]; then
          info "Auto-injecting license header into ${file}..."
          HEADER="# Copyright $(date +%Y) Google LLC
#
# Licensed under the Apache License, Version 2.0 (the \"License\");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an \"AS IS\" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
---"
          TEMP_FILE="$(mktemp)"
          echo "${HEADER}" > "${TEMP_FILE}"
          cat "${file}" >> "${TEMP_FILE}"
          mv "${TEMP_FILE}" "${file}"
          success "Header added to ${file}"
        fi
      fi
    fi
  done

  if [ ${MISSING_LICENSE} -eq 0 ]; then
    success "License header check passed!"
  elif [ "${AUTO_FIX}" == "true" ]; then
    success "License headers automatically injected."
  else
    return 1
  fi
}

# Function: Kustomize Manifests Check
check_kustomize() {
  info "Validating Kustomize manifests across all deployment directories..."
  
  export ACP_REPO_DIR="${REPO_ROOT}"
  export ACP_PLATFORM_BASE_DIR="${ACP_REPO_DIR}/platforms/gke/base"
  export HF_MODEL_ID="google/gemma-3-27b-it"
  export HF_MODEL_NAME="gemma-3-27b-it"

  # Source environment setup if script exists
  SET_ENV_SCRIPT="${ACP_PLATFORM_BASE_DIR}/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  if [ -f "${SET_ENV_SCRIPT}" ]; then
    source "${SET_ENV_SCRIPT}" >/dev/null 2>&1 || true
  fi

  # Run configuration scripts to prepare env templates across all use cases
  info "Configuring environment templates across all workload use cases..."
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/configure_huggingface.sh" >/dev/null 2>&1 || true

  export ACCELERATOR_TYPE="l4"
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/async-inference-gpu/async-load-generator/configure_load_generator.sh" >/dev/null 2>&1 || true
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/async-inference-gpu/async-pubsub-subscriber/configure_pubsub_subscriber.sh" >/dev/null 2>&1 || true
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/async-inference-gpu/vllm/configure_vllm.sh" >/dev/null 2>&1 || true
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm/configure_vllm.sh" >/dev/null 2>&1 || true
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/configure_vllm_runai.sh" >/dev/null 2>&1 || true
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-auto-tuning/configure_vllm.sh" >/dev/null 2>&1 || true

  export HF_MODEL_ID="black-forest-labs/flux.1-schnell"
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/diffusers/configure_diffusers.sh" >/dev/null 2>&1 || true

  export ACCELERATOR_TYPE="v5e"
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/max-diffusion/configure_max_diffusion.sh" >/dev/null 2>&1 || true
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/vllm/configure_vllm.sh" >/dev/null 2>&1 || true

  export ACCELERATOR_TYPE="rtx-pro-6000"
  export ACCELERATOR="GPU"
  export APP_LABEL="vllm-rtx-pro-6000-gemma-3-27b-it"
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm/configure_benchmark.sh" >/dev/null 2>&1 || true
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-spec-decoding/configure_vllm_spec_decoding.sh" >/dev/null 2>&1 || true

  export ACCELERATOR_TYPE="l4"
  export HF_MODEL_NAME="HF_MODEL_NAME"
  export K6_REQUEST_BATCH_SIZE=1
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/k6-benchmark/configure_deployment.sh" >/dev/null 2>&1 || true

  export ACCELERATOR_TYPE="rtx-pro-6000"
  export HF_MODEL_ID="meta-llama/Llama-3.3-70B-Instruct"
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh" >/dev/null 2>&1 || true
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/offline-batch-inference-gpu/configure_jobset.sh" >/dev/null 2>&1 || true
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/offline-batch-inference-gpu/offline-batch-dataset-downloader/configure_dataset_downloader.sh" >/dev/null 2>&1 || true
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/offline-batch-inference-gpu/offline-batch-worker/configure_worker.sh" >/dev/null 2>&1 || true

  export llmd_model_id="google/gemma-3-27b-it"
  export llmd_accelerator_type="l4"
  source "${ACP_PLATFORM_BASE_DIR}/use-cases/inference-ref-arch/examples/llmd/_shared_config/scripts/set_environment_variables.sh" >/dev/null 2>&1 || true
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/llmd/vllm/configure_vllm.sh" >/dev/null 2>&1 || true

  FAILED_BUILD=0
  MANIFEST_DIRS="$(find "${ACP_PLATFORM_BASE_DIR}/use-cases/inference-ref-arch/kubernetes-manifests" -name "kustomization.yaml" -not -path "*/base/*" -exec dirname {} \;)"

  for dir in ${MANIFEST_DIRS}; do
    if kubectl kustomize "${dir}" >/dev/null 2>&1; then
      success "Kustomize build OK: $(basename "${dir}")"
    else
      error "Kustomize build FAILED: ${dir}"
      FAILED_BUILD=$((FAILED_BUILD + 1))
    fi
  done

  if [ ${FAILED_BUILD} -eq 0 ]; then
    success "All Kustomize manifests validated successfully!"
  else
    error "${FAILED_BUILD} Kustomize manifest directory(s) failed build check."
    return 1
  fi
}

check_cspell() {
  info "Checking spellings with CSpell..."
  if command -v cspell >/dev/null 2>&1; then
    if cspell --config cspell.json "test/ci-cd/**/*" "docs/**/*" "platforms/**/*"; then
      success "CSpell check passed!"
    else
      error "CSpell check failed!"
      return 1
    fi
  elif npx --version >/dev/null 2>&1; then
    if npx --yes cspell --config cspell.json "test/ci-cd/**/*" "docs/**/*" "platforms/**/*"; then
      success "CSpell check passed!"
    else
      error "CSpell check failed!"
      return 1
    fi
  else
    warn "npx/cspell CLI not found in environment. Skipping CSpell check."
  fi
}

# Main Execution Flow
FAILURES=0

if [ "${RUN_PRETTIER}" == "true" ]; then
  check_prettier || FAILURES=$((FAILURES + 1))
fi

if [ "${RUN_LICENSE}" == "true" ]; then
  check_license || FAILURES=$((FAILURES + 1))
fi

if [ "${RUN_KUSTOMIZE}" == "true" ]; then
  check_kustomize || FAILURES=$((FAILURES + 1))
fi

check_cspell || FAILURES=$((FAILURES + 1))

echo ""
if [ ${FAILURES} -eq 0 ]; then
  success "🎉 All local CI checks passed! You are ready to create or update your PR."
else
  error "❌ ${FAILURES} check(s) failed. Please review the errors above before pushing."
  exit 1
fi
