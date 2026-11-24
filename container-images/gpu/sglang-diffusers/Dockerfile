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

ARG SGLANG_BASE_IMAGE=lmsysorg/sglang:v0.5.23-cu130-runtime@sha256:3ce6da3e5ea0fee2dac6a23b528cb294fedd31ca74a55a4511f709c5e01e8652
FROM ${SGLANG_BASE_IMAGE}

RUN apt-get update && \
    apt-get upgrade -y && \
    rm -rf /var/lib/apt/lists/* && \
    sed -i 's/"diffusers==0\.37\.0"/"diffusers==0.43.0"/' python/*.toml && \
    grep -q '"diffusers==0.43.0"' python/*.toml && \
    SGLANG_BUILD_RUST_EXTS=none pip install --no-cache-dir -e "python[diffusion]" && \
    pip install --no-cache-dir --upgrade "pillow==13.0.0" && \
    python3 -c "import importlib, sglang, diffusers, PIL; importlib.import_module('sglang.multimodal_gen.runtime.pipelines.flux_2_klein')"

ENTRYPOINT [ "sglang" ]

EXPOSE 30000

CMD [ "--help" ]
