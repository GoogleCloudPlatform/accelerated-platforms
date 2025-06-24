# Copyright 2025 Google LLC
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

ARG NVFLARE_RELEASE_TAG="2.5.2"

FROM nvflare/nvflare:${NVFLARE_RELEASE_TAG}

ARG USER_ID=10000
ARG GROUP_ID=10000

RUN groupadd -g ${GROUP_ID} nvflare
RUN useradd -ms /bin/bash --uid ${USER_ID} --gid ${GROUP_ID} nvflare && chown -R nvflare /opt/NVFlare

USER nvflare

WORKDIR /opt/NVFlare

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ARG NVFLARE_RELEASE_TAG
ENV NVFLARE_RELEASE_TAG="${NVFLARE_RELEASE_TAG}"
RUN wget -qO- "https://github.com/NVIDIA/NVFlare/archive/refs/tags/${NVFLARE_RELEASE_TAG}.tar.gz" | tar xvz

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 CMD ps aux | grep "[p]ython3" || exit 1

WORKDIR /opt/NVFlare/workspace
