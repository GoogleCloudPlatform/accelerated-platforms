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

FROM astral/uv:python3.12-bookworm-slim

# Use copy mode instead of hardlinks across filesystems
ENV UV_LINK_MODE=copy
ENV UV_TORCH_BACKEND=cpu
ENV PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
ENV PYTHONUNBUFFERED=1
ENV JAX_PLATFORMS=cpu

RUN apt-get update && apt-get install -y --no-install-recommends \
  git \
  && rm -rf /var/lib/apt/lists/*

# Set up the application directory
WORKDIR /usr/src/app

# Copy wrapper requirements first and install them
COPY --from=primary requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
  uv pip install --system --resolution=lowest -r requirements.txt

# Copy the application scripts
COPY --from=primary app.py .

CMD ["python3", "app.py"]
