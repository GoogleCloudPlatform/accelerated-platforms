# syntax=docker.io/docker/dockerfile:1.17.1

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

ARG PYTHON_VERSION=3.14
FROM python:${PYTHON_VERSION}

ARG TORCHTITAN_COMMIT=a83bff7316789b740d951db1eb951d197255b3ee
ARG TORCH_VERSION=2.15.0
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
ARG TORCH_TPU_VERSION=0.3.0

ENV PIP_NO_CACHE_DIR=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      git \
      libgoogle-perftools-dev \
      procps && \
    rm -rf /var/lib/apt/lists/*

COPY --from=primary constraints.txt /etc/pip-constraints.txt
ENV PIP_CONSTRAINT=/etc/pip-constraints.txt

RUN mkdir -p /tmp/torchtitan-src && \
    git -C /tmp/torchtitan-src init -q && \
    git -C /tmp/torchtitan-src remote add origin https://github.com/google-pytorch/torchtitan.git && \
    git -C /tmp/torchtitan-src fetch -q --depth=1 origin "${TORCHTITAN_COMMIT}" && \
    git -C /tmp/torchtitan-src checkout -q --detach FETCH_HEAD && \
    test "$(git -C /tmp/torchtitan-src rev-parse HEAD)" = "${TORCHTITAN_COMMIT}"

RUN pip install --pre "torch==${TORCH_VERSION}" --index-url "${TORCH_INDEX_URL}" && \
    pip install -r /tmp/torchtitan-src/torchtitan/experiments/tpu/requirements.txt \
      -f https://storage.googleapis.com/jax-releases/libtpu_releases.html && \
    pip install "torch_tpu==${TORCH_TPU_VERSION}" --extra-index-url "${TORCH_INDEX_URL}" && \
    pip install -r /tmp/torchtitan-src/requirements.txt && \
    pip install -r /tmp/torchtitan-src/.ci/docker/requirements-flux.txt && \
    python -c "import importlib.metadata as m; assert m.version('torch').startswith('${TORCH_VERSION}'), m.version('torch'); assert m.version('torch-tpu') == '${TORCH_TPU_VERSION}', m.version('torch-tpu')"

RUN mkdir -p /torchtitan && \
    cp -r /tmp/torchtitan-src/torchtitan /torchtitan/torchtitan && \
    cp -r /tmp/torchtitan-src/assets /torchtitan/assets && \
    rm -rf /tmp/torchtitan-src

WORKDIR /torchtitan
ENV PYTHONPATH=/torchtitan

COPY --from=primary torchtitan_tpu_sft /torchtitan/torchtitan_tpu_sft

RUN TORCH_DEVICE_BACKEND_AUTOLOAD=0 python -m unittest discover -s /torchtitan/torchtitan_tpu_sft/tests -v

ENV LD_PRELOAD="/usr/lib/x86_64-linux-gnu/libtcmalloc.so.4"
