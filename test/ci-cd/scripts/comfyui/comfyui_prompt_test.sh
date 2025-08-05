#!/bin/sh

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

# Exit on any non-zero exit code, unassigned variables, or pipeline failure.
set -o errexit
set -o nounset
set -o pipefail

# Execute a workflow and get the prompt ID.
execute_workflow() {
    local test_file=$1
    echo "Executing workflow from '$test_file'..."
    local wrapped_file=$(mktemp)

    jq '{prompt: .}' < "$test_file" > "$wrapped_file"
 
    response=$(curl -s -X POST "$COMFYUI_URL/prompt" -H "Content-Type: application/json" -d @"$wrapped_file")
    
    prompt_id=$(echo "$response" | jq -r '.prompt_id')

    if [ -z "$prompt_id" ] || [ "$prompt_id" == "null" ]; then
        echo "Error: Failed to get prompt ID." >&2
        echo "Response: $response" >&2
        return 1
    fi
    sleep 60
    get_history "$prompt_id"
}

# Poll the history endpoint for output details.
get_history() {
    local current_prompt_id=$1
    local start_time=$(date +%s)
    local response http_code body now
    echo "Polling history for prompt ID: $current_prompt_id..."
    
    while true; do
        response=$(curl -s -o - -w "%{http_code}" "$COMFYUI_URL/history/$current_prompt_id")
        http_code="${response: -3}"
        body="${response::-3}"
        
        if [[ "$http_code" == "200" && "$body" != "{}" ]]; then
            
            local filename subfolder type

            filename=$(echo "$body" | jq -r --arg id "$current_prompt_id" '
                    (.[$id].outputs | to_entries[] | select(.value.video) | .value.video[0][0]) //
                    (.[$id].outputs | to_entries[] | select(.value.images) | .value.images[0].filename)
                ')

            subfolder=$(echo "$body" | jq -r '.[].outputs | .[] | select(.images) | .images[0].subfolder')
            type=$(echo "$body" | jq -r '.[].outputs | .[] | select(.images) | .images[0].type')

            if [[ -n "$filename" ]]; then
                get_image_metadata "$filename" "$subfolder" "$type"
                return 0
            else
                echo "Error: Could not find filename in response." >&2
                return 1
            fi
        fi

        now=$(date +%s)
        if (( now - start_time >= POLL_TIMEOUT )); then
            echo "Polling timeout." >&2
            return 1
        fi
        sleep "$POLL_INTERVAL"
    done
}
# Get the image size information from headers.
get_image_metadata() {
    local filename=$1 subfolder=$2 folder_type=$3
    local image_url="${COMFYUI_URL}/view?filename=${filename}&subfolder=${subfolder}&type=${folder_type}"
    local size_in_bytes
    
    size_in_bytes=$(curl -sI "$image_url" | grep -i "Content-Length" | awk '{print $2}' | tr -d '\r')

    if ! [[ "$size_in_bytes" =~ ^[0-9]+$ ]] || [ "$size_in_bytes" -lt $MINIMUM_FILE_SIZE_BYTES ]; then
        echo "Error: File size ${size_in_bytes} bytes is too small or could not be determined." >&2
        return 1
    fi
    echo "Image ${filename} found with size: $size_in_bytes bytes."
    return 0
}

# --- Main Test Execution ---
main() {
    local test_file=$1
    echo "--- Running test for: $test_file ---"
    
    # Check for dependencies.
    command -v jq &> /dev/null
    command -v curl &> /dev/null
    
    # Check if the test file exists.
    if [ ! -f "$test_file" ]; then
        echo "Error: Test file '$test_file' does not exist." >&2
        exit 1
    fi

    # Execute workflow, poll history, and get metadata sequentially.
    local prompt_id
    execute_workflow "$test_file"    
    echo "--- Test completed successfully ---"
}

# Loop through each file in the directory
for file in tmp/workflows/*.json; do
    main "$file"
done
