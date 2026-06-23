#!/bin/bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# Script to configure llm-d stack deployment (rename cluster)
# Should be run from the repository root.

set -e

PLATFORM_NAME=${1:-"llm-d-bench"}

echo "Updating platform_name to $PLATFORM_NAME in platform.auto.tfvars..."
python3 -c "
import sys
path = 'platforms/gke/base/_shared_config/platform.auto.tfvars'
name = sys.argv[1]
try:
    with open(path, 'r') as f:
        content = f.read()
except FileNotFoundError:
    content = ''
lines = content.splitlines()
found = False
for i, line in enumerate(lines):
    if line.startswith('platform_name'):
        lines[i] = f'platform_name = \"{name}\"'
        found = True
        break
if not found:
    lines.append(f'platform_name = \"{name}\"')
with open(path, 'w') as f:
    f.write('\\n'.join(lines) + '\\n')
" "$PLATFORM_NAME"

echo "To apply terraform, run:"
echo "cd platforms/gke/base/use-cases/inference-ref-arch/terraform && terraform init && terraform apply"

