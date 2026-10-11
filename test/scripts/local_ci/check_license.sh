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

echo -e "${INFO} Checking Google LLC license headers..."

AUTO_FIX=${AUTO_FIX:-false}
MISSING_LICENSE=0

FILES="$(git status --porcelain | awk '{print $2}' | grep -E '\.(yaml|yml|sh|py|go|tf)$' || true)"

for file in ${FILES}; do
  if [ -f "${file}" ]; then
    if ! head -n 15 "${file}" | grep -qi "Copyright.*Google LLC"; then
      echo -e "${ERROR} Missing Google LLC license header: ${file}"
      MISSING_LICENSE=$((MISSING_LICENSE + 1))

      if [ "${AUTO_FIX}" == "true" ]; then
        echo -e "${INFO} Auto-injecting license header into ${file}..."
        
        EXT="${file##*.}"
        TEMP_FILE="$(mktemp)"
        
        if [[ "${EXT}" == "yaml" || "${EXT}" == "yml" ]]; then
          echo "# Copyright $(date +%Y) Google LLC" > "${TEMP_FILE}"
          echo "#" >> "${TEMP_FILE}"
          echo "# Licensed under the Apache License, Version 2.0 (the \"License\");" >> "${TEMP_FILE}"
          echo "# you may not use this file except in compliance with the License." >> "${TEMP_FILE}"
          echo "# You may obtain a copy of the License at" >> "${TEMP_FILE}"
          echo "#" >> "${TEMP_FILE}"
          echo "#     http://www.apache.org/licenses/LICENSE-2.0" >> "${TEMP_FILE}"
          echo "#" >> "${TEMP_FILE}"
          echo "# Unless required by applicable law or agreed to in writing, software" >> "${TEMP_FILE}"
          echo "# distributed under the License is distributed on an \"AS IS\" BASIS," >> "${TEMP_FILE}"
          echo "# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied." >> "${TEMP_FILE}"
          echo "# See the License for the specific language governing permissions and" >> "${TEMP_FILE}"
          echo "# limitations under the License." >> "${TEMP_FILE}"
          cat "${file}" >> "${TEMP_FILE}"
          cat "${TEMP_FILE}" > "${file}" && rm -f "${TEMP_FILE}"
        elif [[ "${EXT}" == "sh" || "${EXT}" == "py" || "${EXT}" == "tf" ]]; then
          # For scripts, preserve the shebang if it exists
          if head -n 1 "${file}" | grep -q "^#!"; then
            head -n 1 "${file}" > "${TEMP_FILE}"
            tail -n +2 "${file}" > "${TEMP_FILE}.content"
          else
            cat "${file}" > "${TEMP_FILE}.content"
          fi
          
          echo "# Copyright $(date +%Y) Google LLC" >> "${TEMP_FILE}"
          echo "#" >> "${TEMP_FILE}"
          echo "# Licensed under the Apache License, Version 2.0 (the \"License\");" >> "${TEMP_FILE}"
          echo "# you may not use this file except in compliance with the License." >> "${TEMP_FILE}"
          echo "# You may obtain a copy of the License at" >> "${TEMP_FILE}"
          echo "#" >> "${TEMP_FILE}"
          echo "#     http://www.apache.org/licenses/LICENSE-2.0" >> "${TEMP_FILE}"
          echo "#" >> "${TEMP_FILE}"
          echo "# Unless required by applicable law or agreed to in writing, software" >> "${TEMP_FILE}"
          echo "# distributed under the License is distributed on an \"AS IS\" BASIS," >> "${TEMP_FILE}"
          echo "# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied." >> "${TEMP_FILE}"
          echo "# See the License for the specific language governing permissions and" >> "${TEMP_FILE}"
          echo "# limitations under the License." >> "${TEMP_FILE}"
          
          cat "${TEMP_FILE}.content" >> "${TEMP_FILE}"
          cat "${TEMP_FILE}" > "${file}" && rm -f "${TEMP_FILE}"
          rm -f "${TEMP_FILE}.content"
        elif [[ "${EXT}" == "go" ]]; then
          echo "// Copyright $(date +%Y) Google LLC" > "${TEMP_FILE}"
          echo "//" >> "${TEMP_FILE}"
          echo "// Licensed under the Apache License, Version 2.0 (the \"License\");" >> "${TEMP_FILE}"
          echo "// you may not use this file except in compliance with the License." >> "${TEMP_FILE}"
          echo "// You may obtain a copy of the License at" >> "${TEMP_FILE}"
          echo "//" >> "${TEMP_FILE}"
          echo "//     http://www.apache.org/licenses/LICENSE-2.0" >> "${TEMP_FILE}"
          echo "//" >> "${TEMP_FILE}"
          echo "// Unless required by applicable law or agreed to in writing, software" >> "${TEMP_FILE}"
          echo "// distributed under the License is distributed on an \"AS IS\" BASIS," >> "${TEMP_FILE}"
          echo "// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied." >> "${TEMP_FILE}"
          echo "// See the License for the specific language governing permissions and" >> "${TEMP_FILE}"
          echo "// limitations under the License." >> "${TEMP_FILE}"
          cat "${file}" >> "${TEMP_FILE}"
          cat "${TEMP_FILE}" > "${file}" && rm -f "${TEMP_FILE}"
        fi
        
        echo -e "${SUCCESS} Header added to ${file}"
      fi
    fi
  fi
done

if [ ${MISSING_LICENSE} -eq 0 ]; then
  echo -e "${SUCCESS} License header check passed!"
elif [ "${AUTO_FIX}" == "true" ]; then
  echo -e "${SUCCESS} License headers automatically injected."
else
  exit 1
fi
