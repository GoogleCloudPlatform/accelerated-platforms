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

INFO="\033[1;34m[INFO]\033[0m"
SUCCESS="\033[1;32m[SUCCESS]\033[0m"
ERROR="\033[1;31m[ERROR]\033[0m"
WARN="\033[1;33m[WARNING]\033[0m"

echo -e "${INFO} Checking Markdown formatting with Prettier..."

if ! type -P node >/dev/null 2>&1; then
  echo -e "${WARN} Node.js not found. Skipping Prettier check."
  exit 0
fi

# Get Prettier version from devcontainer dependencies to match github workflows
PRETTIER_VERSION=$(node -p -e "require('./.devcontainer/dependencies/package.json').dependencies['prettier']")

if [ -z "${PRETTIER_VERSION}" ]; then
  echo -e "${WARN} Could not determine Prettier version from package.json. Falling back to latest."
  PRETTIER_VERSION="latest"
fi

if npx prettier@"${PRETTIER_VERSION}" --check '**/*.md'; then
  echo -e "${SUCCESS} Prettier formatting check passed!"
else
  echo -e "${ERROR} Prettier formatting check failed! Run 'npx prettier@${PRETTIER_VERSION} --write \"**/*.md\"' to fix."
  exit 1
fi
