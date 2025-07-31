#!/bin/bash
#
# Copyright 2024 Google LLC
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

ParseSeparatedBashArray() {
  local STRING_TO_PARSE="${1}"
  local -n DESTINATION_ARRAY="${2}"
  local STRING_ARRAY_SEPARATOR="${3}"

  [ -v DEBUG ] && echo "Parsing ${STRING_TO_PARSE} as a Bash array"

  local -a PARSED_ARRAY
  IFS="${STRING_ARRAY_SEPARATOR}" read -r -a PARSED_ARRAY <<<"${STRING_TO_PARSE}"

  [ -v DEBUG ] && echo "Elements to add to ${!DESTINATION_ARRAY}: ${PARSED_ARRAY[*]}"

  DESTINATION_ARRAY+=("${PARSED_ARRAY[@]}")

  [ -v DEBUG ] && echo "${!DESTINATION_ARRAY} after adding options: ${DESTINATION_ARRAY[*]}"

  unset -n DESTINATION_ARRAY
}

ParseSpaceSeparatedBashArray() {
  ParseSeparatedBashArray "${1}" "${2}" " "
}
