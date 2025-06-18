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

for file in *.txt; do
  echo "Checking ${file}..."

  file_content=$(<"${file}")
  lowercase_content=${file_content,,}

  sorted_content=$(echo "${lowercase_content}" | sort)
  sorted_count=$(echo "${sorted_content}" | wc -l)

  unique_content=$(echo "${sorted_content}" | uniq)
  unique_count=$(echo "${unique_content}" | wc -l)

  fix_count=0
  if [[ "${file_content}" != "${lowercase_content}" ]]; then
    echo -e "  - Converted '${file}' to lowercase."
    tr '[:upper:]' '[:lower:]' <"${file}" | sponge "${file}"
    fix_count=$((fix_count + 1))
  fi

  if [[ "${file_content}" != "${sorted_content}" ]]; then
    echo -e "  - Sorted '${file}'." >&2
    sort "${file}" | sponge "${file}"
    fix_count=$((fix_count + 1))
  fi

  if [[ "${sorted_count}" != "${unique_count}" ]]; then
    echo -e "  - Extracted unique values in '${file}'." >&2
    sort -u "${file}" | sponge "${file}"
    fix_count=$((fix_count + 1))
  fi
done

exit ${return_code}
