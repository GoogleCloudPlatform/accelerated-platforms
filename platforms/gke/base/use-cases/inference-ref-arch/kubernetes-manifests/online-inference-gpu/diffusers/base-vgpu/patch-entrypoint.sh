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

v23_old_code = '''        extra_args = (
            dict(device_id=device_id)
            if current_platform.supports_distributed_device_id()
            else {}
        )'''

v23_new_code = '''        extra_args = (
            dict(device_id=device_id)
            if (current_platform.supports_distributed_device_id() and world_size > 1)
            else {}
        )'''

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

if v23_old_code in content:
    content = content.replace(v23_old_code, v23_new_code, 1)
    with open(path, 'w') as f:
        f.write(content)
    print('[Patch] Successfully patched parallel_state.py!')
elif old_code in content:
    content = content.replace(old_code, new_code, 1)
    with open(path, 'w') as f:
        f.write(content)
    print('[Patch] Successfully patched parallel_state.py!')
elif v23_new_code in content or new_code in content:
    print('[Patch] parallel_state.py already patched.')
else:
    raise RuntimeError(
        f'[Patch] Expected init_process_group block not found in {path}; '
        'verify compatibility with the SGLang base image version.'
    )
"

# Execute normal SGLang binary entrypoint with arguments
exec sglang "$@"
