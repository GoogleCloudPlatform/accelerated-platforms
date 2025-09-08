#!/usr/bin/env bash

# Copyright 2025 Google LLC
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
set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

OPTIONS=$(getopt -o "" --long "modify-rc-file" --name "$0" -- "$@")
if [ ${?} -ne 0 ]; then
    echo "Error parsing options." >&2
    exit 1
fi

eval set -- "$OPTIONS"

while true; do
  case "${1}" in
    --modify-rc-file) 
      MODIFY_RC_FILE=true
      shift
      ;;
    -- )
      shift
      break
      ;;
    *) 
      echo "Invalid option: ${1}" >&2
      exit 1
      ;;
  esac
done
shift $((OPTIND - 1))

echo "Installing 'tfswitch' in '\${HOME}/.local/bin'"
curl -L https://raw.githubusercontent.com/warrensbox/terraform-switcher/master/install.sh | bash -s -- -b "${HOME}/.local/bin"
echo

echo "Switching to Terraform v1.8.0 in '\${HOME}/bin'"
"${HOME}/.local/bin/tfswitch" 1.8.0
echo

echo "\${HOME}/bin/terraform version"
"${HOME}/bin/terraform" version
echo
echo
echo

if [[ -v MODIFY_RC_FILE ]] || { [[ -v USER_EMAIL ]] && [[ "${USER_EMAIL}" == *@qwiklabs.net ]] }; then
  grep -qxF 'export PATH=${HOME}/bin:${HOME}/.local/bin:${PATH}' "${HOME}/.bashrc" || echo -e "\nexport PATH=\${HOME}/bin:\${HOME}/.local/bin:\${PATH}" >> "${HOME}/.bashrc"

  echo "NOTE: '\${HOME}/bin' and '\${HOME}/.local/bin' have been added to your PATH in '\${HOME}/.bashrc'"
  echo
  echo "Restart your shell or update the PATH of your current shell with the following command:"
  echo " export PATH=\${HOME}/bin:\${HOME}/.local/bin:\${PATH}"
  echo
else
  echo "NOTE: Ensure that '\${HOME}/bin' and '\${HOME}/.local/bin' are on your PATH."
  echo
  echo "To add them to your '\${HOME}/.bashrc' file, run the following command: "
  echo "  echo \"export PATH=\\\${HOME}/bin:\\\${HOME}/.local/bin:\\\${PATH}\" >> \"\${HOME}/.bashrc\""
  echo
  echo "To add them to the PATH of your current shell, run the following command:"
  echo "  export PATH=\${HOME}/bin:\${HOME}/.local/bin:\${PATH}"
  echo
fi
