# syntax=docker.io/docker/dockerfile:1.17.1

# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM astral/uv:python3.12-bookworm-slim

# Use copy mode instead of hardlinks across filesystems
ENV UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
  git \
  && rm -rf /var/lib/apt/lists/*

# Leverage uv's built-in caching for fast subsequent builds
RUN --mount=type=cache,target=/root/.cache/uv \
  uv pip install --system maxtext[tpu-post-train]==0.2.2 --resolution=lowest

# Script name for the extra TPU post-training dependencies
RUN install_tpu_post_train_extra_deps

COPY --from=primary train.py .

CMD ["python3", "train.py"]
