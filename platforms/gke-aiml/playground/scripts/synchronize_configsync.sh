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
SCRIPT_PATH="$(
    cd "$(dirname "$0")" >/dev/null 2>&1
    pwd -P
)"

if [ -z ${GIT_REPOSITORY:-} ]; then
    ${SCRIPT_PATH}/helpers/generate_oic_image.sh

    LATEST_SHA=$(crane digest ${CONFIGSYNC_IMAGE})
    LAST_COMMIT=${LATEST_SHA##sha256:}
else
    source ${SCRIPT_PATH}/helpers/clone_git_repo.sh

    cd ${GIT_REPOSITORY_PATH}
    commit_hash=$(git rev-parse HEAD)
    LAST_COMMIT=${commit_hash}
fi

${SCRIPT_PATH}/helpers/wait_for_root_sync.sh ${LAST_COMMIT}
${SCRIPT_PATH}/helpers/wait_for_repo_sync.sh ${LAST_COMMIT}
