export ACP_REPO_DIR=$(git rev-parse --show-toplevel)
export ACP_PLATFORM_BASE_DIR="$ACP_REPO_DIR/platforms/gke/base"
export ACP_PLATFORM_CORE_DIR="$ACP_PLATFORM_BASE_DIR/core"

export TF_VAR_cluster_project_id="batchref-arch-multikueue"
export TF_VAR_terraform_project_id="batchref-arch-multikueue"
export TF_VAR_initialize_backend_use_case_name="batchref-arch-multikueue"


# shellcheck disable=SC1091
source "${ACP_PLATFORM_BASE_DIR}/use-cases/alphafold/common.sh"

start_timestamp_batchref_arch=$(date +%s)

echo "Initializing the core platform"
# Don't provision any core platform terraservice becuase we just need
# to initialize the terraform environment and remote backend
# shellcheck disable=SC1091,SC2154
CORE_TERRASERVICES_APPLY="${core_platform_init_terraservices[*]}" \
  "${ACP_PLATFORM_CORE_DIR}/deploy.sh"