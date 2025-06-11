#!/usr/bin/env bash

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

source "${MY_PATH}/helpers/git.sh"

ACP_REPO_DIR="$(realpath ${MY_PATH}/../../)"

for file in "${git_assume_unchanged_files[@]}"; do
  echo "no-assume-unchanged ${file}"
  git update-index --no-assume-unchanged ${ACP_REPO_DIR}/${file}
done

echo "Removing the .dev-tools/.gitignore file"
cd "${ACP_REPO_DIR}" &&
  git config core.excludesfile "" &&
  cd - &>/dev/null
