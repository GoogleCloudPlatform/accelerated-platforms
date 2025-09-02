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
# ComfyUI workflow tester (runs INSIDE pod)

log() { echo "---- $*" >&2; }

# --- 1) Submit a workflow; print {"prompt_id":"..."} to stdout (compact JSON) ---
execute_workflow() {
  local test_file=$1
  local filename; filename=$(basename "$test_file")

  log "execute_workflow: wrapping '${filename}'"
  local wrapped_file
  wrapped_file=$(mktemp)
  jq '{prompt: .}' < "$test_file" > "$wrapped_file"

  log "POST ${COMFYUI_URL}/prompt"
  local resp http_code body
  resp=$(curl -sS --connect-timeout 10 --max-time 150 \
         -o - -w "HTTPSTATUS:%{http_code}" \
         -X POST "${COMFYUI_URL}/prompt" \
         -H "Content-Type: application/json" \
         --data @"${wrapped_file}")
  http_code="${resp##*HTTPSTATUS:}"
  body="${resp%HTTPSTATUS:*}"

  log "prompt POST http=${http_code}"
  if [[ "${http_code}" != "200" ]]; then
    echo "Error in execute_workflow for file '${filename}': HTTP ${http_code}" >&2
    echo "Response: ${body}" >&2
    return 1
  fi

  local prompt_id; prompt_id=$(printf '%s' "${body}" | jq -r '.prompt_id')
  if [ -z "${prompt_id}" ] || [ "${prompt_id}" = "null" ]; then
    echo "Error in execute_workflow for file '${filename}': missing prompt_id" >&2
    echo "Response: ${body}" >&2
    return 1
  fi

  # stdout: compact JSON ONLY
  jq -c --null-input --arg id "${prompt_id}" '{"prompt_id":$id}'
}

# --- 2) Poll history; print {"filename":"...","subfolder":"...","type":"..."} to stdout ---
get_history() {
  local prompt_id=$1
  local poll_timeout=${POLL_TIMEOUT:-1200}

  log "get_history: id=${prompt_id}"
  local start; start=$(date +%s)

  while true; do
    local response http_code body now
    response=$(curl -s --connect-timeout 5 \
      -o - -w "%{http_code}" "${COMFYUI_URL}/history/${prompt_id}")
  
    http_code="${response: -3}"
    body="${response::-3}"

    # --- Check status and handle errors ---
    if [[ "${http_code}" == "200" && -n "${body}" && "${body}" != "{}" ]]; then
      local status_str
      status_str=$(printf '%s' "${body}" \
        | jq -r --arg id "${prompt_id}" '.[$id].status.status_str // empty' 2>/dev/null || true)

      # If status is 'error', extract the message and fail
      if [[ "${status_str}" == "error" ]]; then
        local exception_msg
        exception_msg=$(printf '%s' "${body}" | jq -r '.[] | .status.messages[] | select(.[0] == "execution_error") | .[1].exception_message' 2>/dev/null)
        
        echo "Error in get_history: Job failed with message: ${exception_msg}" >&2
        return 1
      fi
    fi

    # --- Success path: emit first output as JSON to stdout ---
    if [[ "${http_code}" == "200" && "${body}" != "{}" ]]; then
      local json
      json=$(printf '%s' "${body}" \
        | jq -c --arg id "${prompt_id}" '
            (.[$id].outputs | to_entries[] | .value
              | select(.video)
              | {filename: .video[0].filename, subfolder: .video[0].subfolder, type: .video[0].type}) //
            (.[$id].outputs | to_entries[] | .value
              | select(.images)
              | {filename: .images[0].filename, subfolder: .images[0].subfolder, type: .images[0].type})
          ')
      if [ -n "${json}" ] && [ "${json}" != "null" ]; then
        printf '%s\n' "${json}"
        return 0
      fi
    fi

    now=$(date +%s)
    if (( now - start >= poll_timeout )); then
      echo "Error in get_history: timeout after ${poll_timeout}s for id=${prompt_id}" >&2
      return 1
    fi
    sleep 5 # Changed to 5s for more frequent checks
  done
}

# --- 3) HEAD the file; print {"size_in_bytes":1234} to stdout ---
get_image_metadata() {
  local filename=$1
  local subfolder=$2
  local folder_type=$3

  local url="${COMFYUI_URL}/view?filename=${filename}&subfolder=${subfolder}&type=${folder_type}"
  log "HEAD ${url}"

  local size_in_bytes
  size_in_bytes=$(curl -sI --connect-timeout 5 --max-time 20 "${url}" \
    | awk 'tolower($1)=="content-length:"{print $2}' \
    | tr -d "\r")

  if ! [[ "${size_in_bytes:-}" =~ ^[0-9]+$ ]]; then
    echo "Error in get_image_metadata: content-length not numeric (got '${size_in_bytes:-unknown}')" >&2
    return 1
  fi

  # stdout: compact JSON ONLY
  jq -c --null-input --argjson n "${size_in_bytes}" '{"size_in_bytes":$n}'
}

# --- 4) Orchestration for one workflow file; logs to stderr, JSON stays clean ---
main() {
  local test_file=$1
  log "main: start '${test_file}'"

  command -v jq   >/dev/null 2>&1 || { echo "Error: 'jq' is not installed." >&2; exit 1; }
  command -v curl >/dev/null 2>&1 || { echo "Error: 'curl' is not installed." >&2; exit 1; }
  [ -f "${test_file}" ] || { echo "Error: Test file '${test_file}' does not exist." >&2; exit 1; }

  # 4.1 Submit
  log "main: execute_workflow '${test_file}'"
  local submit_json;
  submit_json=$(execute_workflow "${test_file}")
  log "main: submit_json=${submit_json}"
  local prompt_id;
  prompt_id=$(printf '%s' "${submit_json}" | jq -r '.prompt_id')
  [ -n "${prompt_id}" ] && [ "${prompt_id}" != "null" ] || {
    echo "Error: missing prompt_id in submit_json" >&2
    return 1
  }

  # 4.2 Poll
  log "main: get_history id=${prompt_id}"
  local hist_json;
  hist_json=$(get_history "${prompt_id}")
  log "main: hist_json=${hist_json}"
  local out_fn subfolder ftype
  out_fn=$(printf '%s' "${hist_json}" | jq -r '.filename')
  subfolder=$(printf '%s' "${hist_json}" | jq -r '.subfolder')
  ftype=$(printf '%s' "${hist_json}" | jq -r '.type')
  if [ -z "${out_fn}" ] || [ "${out_fn}" = "null" ]; then
    echo "Error: missing filename from history" >&2
    return 1
  fi

  # 4.3 Metadata
  log "main: get_image_metadata file='${out_fn}'"
  local meta_json;
  meta_json=$(get_image_metadata "${out_fn}" "${subfolder}" "${ftype}")
  log "main: meta_json=${meta_json}"
  local size_in_bytes;
  size_in_bytes=$(printf '%s' "${meta_json}" | jq -r '.size_in_bytes')
  if ! [[ "${size_in_bytes}" =~ ^[0-9]+$ ]]; then
    echo "Error: size_in_bytes invalid from meta_json" >&2
    return 1
  fi

  # 4.4 Validate size
  local min_bytes=${MINIMUM_FILE_SIZE_BYTES:-1}
  log "main: validate size=${size_in_bytes} min=${min_bytes}"
  if [ "${size_in_bytes}" -lt "${min_bytes}" ]; then
    echo "Error: output '${out_fn}' too small (${size_in_bytes} < ${min_bytes})" >&2
    return 1
  fi

  log "main: success '${test_file}' (file='${out_fn}', bytes=${size_in_bytes})"
  return 0
}


