# shellcheck disable=SC2034 # Variable is used in other scripts
core_platform_init_terraservices=(
  "initialize"
  "networking"
)

# shellcheck disable=SC2034 # Variable is used in other scripts
core_platform_terraservices=(
  "container_cluster"
  "container_node_pool"
  "workloads/kueue"
)