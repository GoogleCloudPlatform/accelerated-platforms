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

echo -e "${INFO} Checking spellings with CSpell..."

if type -P cspell >/dev/null 2>&1; then
  if cspell --config cspell.json "**" 2>/dev/null; then
    echo -e "${SUCCESS} CSpell check passed!"
  else
    echo -e "${ERROR} CSpell check failed!"
    exit 1
  fi
elif type -P npx >/dev/null 2>&1; then
  if npx --yes cspell --config cspell.json "**" 2>/dev/null; then
    echo -e "${SUCCESS} CSpell check passed!"
  else
    echo -e "${ERROR} CSpell check failed!"
    exit 1
  fi
else
  echo -e "${WARN} npx/cspell CLI not found in environment. Skipping CSpell check."
  exit 0
fi
