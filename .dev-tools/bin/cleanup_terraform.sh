#!/usr/bin/env bash

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

source "${MY_PATH}/helpers/git.sh"

ACP_REPO_DIR="$(realpath ${MY_PATH}/../../)"

echo "Removing .terraform directories..."
find "${ACP_REPO_DIR}" -name ".terraform" -type d
find "${ACP_REPO_DIR}" -name ".terraform" -type d -exec rm -r {} +
echo

echo "Searching for terraform.tfstate files..."
find "${ACP_REPO_DIR}" -name "terraform.tfstate*" -type f
echo "==================================================================================="
echo "If any terraform.tfstate files were found, review and delete any unnecessary files."
echo "==================================================================================="
