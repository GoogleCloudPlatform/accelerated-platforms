#!/bin/bash

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

# Dynamic python patch of parallel_state.py
python3 -c "
path = '/sgl-workspace/sglang/python/sglang/multimodal_gen/runtime/distributed/parallel_state.py'
with open(path, 'r') as f:
    content = f.read()

old_code = '''        extra_args = (
            {}
            if (
                current_platform.is_mps()
                or current_platform.is_musa()
                or current_platform.is_npu()
            )
            else dict(device_id=device_id)
        )'''

new_code = '''        extra_args = (
            {}
            if (
                current_platform.is_mps()
                or current_platform.is_musa()
                or current_platform.is_npu()
                or world_size == 1
            )
            else dict(device_id=device_id)
        )'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open(path, 'w') as f:
        f.write(content)
    print('[Patch] Successfully patched parallel_state.py!')
else:
    print('[Patch] Target code not found or already patched.')
"

# Execute normal SGLang binary entrypoint with arguments
exec sglang "$@"
