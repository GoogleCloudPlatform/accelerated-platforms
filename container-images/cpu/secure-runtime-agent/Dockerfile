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

FROM golang:1.25-bookworm AS ate-builder

ARG SUBSTRATE_VERSION=v1.0.0-rc.2
RUN git clone --depth 1 --branch ${SUBSTRATE_VERSION} https://github.com/agent-substrate/substrate.git /substrate \
    && cd /substrate \
    && GOTOOLCHAIN=auto CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o /out/kubectl-ate ./cmd/kubectl-ate

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates git \
    && curl -fsSL "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" -o /usr/local/bin/kubectl \
    && chmod 0755 /usr/local/bin/kubectl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY --from=ate-builder /out/kubectl-ate /usr/local/bin/kubectl-ate

COPY --from=primary requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY --from=primary secure_runtime_agent /app/secure_runtime_agent

EXPOSE 8080

ENTRYPOINT ["adk", "web", "--host", "0.0.0.0", "--port", "8080", "--otel_to_cloud", "--allow_origins", "regex:https?://.*"]
