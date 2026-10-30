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

# Creates (if needed) a dedicated private GitHub repository for the Secure
# Runtime demo and seeds the legitimate scientific issue (#19 equivalent) and
# the untrusted prompt-injection test fixture (#42 equivalent).

set -o errexit
set -o nounset
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GITHUB_REPO="${GITHUB_REPO:-}"

if [[ -z "${GITHUB_REPO}" ]]; then
  echo "Usage: GITHUB_REPO=<owner>/<private-repo-name> $0" >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "Error: GitHub CLI ('gh') is required. Install from https://cli.github.com/ and run 'gh auth login'." >&2
  exit 1
fi

echo "==> Checking private demo repository: ${GITHUB_REPO}"
if ! gh repo view "${GITHUB_REPO}" >/dev/null 2>&1; then
  echo "==> Creating private GitHub repository: ${GITHUB_REPO}"
  gh repo create "${GITHUB_REPO}" --private \
    --description "Private demo repository for GKE Agent Substrate Secure Runtime live session"
fi

echo "==> Seeding legitimate scientific reproducer issue..."
ISSUE_19_URL="$(gh issue create \
  --repo "${GITHUB_REPO}" \
  --title "scipy.linalg.solve numerical instability on near-singular covariance matrices" \
  --body-file "${SCRIPT_DIR}/issues/issue-19-reproducer.md")"
echo "    Created: ${ISSUE_19_URL}"

echo "==> Seeding untrusted prompt-injection test fixture issue..."
RENDERED_ISSUE_42="$(sed "s|\${GITHUB_REPO}|${GITHUB_REPO}|g" "${SCRIPT_DIR}/issues/issue-42-untrusted-instructions.md")"
ISSUE_42_URL="$(printf '%s\n' "${RENDERED_ISSUE_42}" | gh issue create \
  --repo "${GITHUB_REPO}" \
  --title "pandas.DataFrame.rolling NaN propagation with scipy.signal.detrend" \
  --body-file -)"
echo "    Created: ${ISSUE_42_URL}"

echo "==> Done! Seeded issues in private repo ${GITHUB_REPO}."
