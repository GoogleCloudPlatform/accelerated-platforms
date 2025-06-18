#!/usr/bin/env bash

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

ACP_REPO_DIR="$(realpath ${MY_PATH}/../../)"

cd "${ACP_REPO_DIR}/.github/workflows/dictionary" ||
  {
    echo "Dictionary folder '${ACP_REPO_DIR}/.github/workflows/dictionary' does not exist, exiting!" >&2
    exit 1
  }

return_code=0
for file in *.txt; do
  echo "Checking ${file}..."

  file_content=$(<"${file}")
  lowercase_content=${file_content,,}

  sorted_content=$(echo "${lowercase_content}" | sort)
  sorted_count=$(echo "${sorted_content}" | wc -l)

  unique_content=$(echo "${sorted_content}" | uniq)
  unique_count=$(echo "${unique_content}" | wc -l)

  if [[ "${file_content}" != "${lowercase_content}" ]]; then
    echo -e "  - The content of '${file}' contains uppercase characters." >&2
    return_code=$((return_code + 1))
  fi

  if [[ "${file_content}" != "${sorted_content}" ]]; then
    echo -e "  - The content of '${file}' is not sorted." >&2
    return_code=$((return_code + 1))
  fi

  if [[ "${sorted_count}" != "${unique_count}" ]]; then
    echo -e "  - The content of '${file}' contains non-unique values." >&2
    return_code=$((return_code + 1))
  fi
done
echo -e "\nError(s) detected: ${return_code}"

exit ${return_code}
