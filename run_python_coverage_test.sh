# Copyright 2025 Google LLC

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# https://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#!/bin/bash

#To add a new direcotry to coverage tests, add it to source_dirs array. 
#Add the source (folder containing src and test directories) to the array
source_dirs=("modules/python")

for source_dir in "${source_dirs[@]}"; do
    export PYTHONPATH=$PYTHONPATH:${source_dir}
    export PYTHONPATH=$PYTHONPATH:${source_dir}/src
    python -m coverage run -m unittest discover "${source_dir}/tests"
done
