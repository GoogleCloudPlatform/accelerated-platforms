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

# Immutable image for the Agent Substrate Security Demo actors, gateway, and
# non-reflecting credential verifier. Installs hash-pinned Google Agent
# Development Kit (`google-adk`) wheels on top of the upstream
# kubernetes-sigs/agent-sandbox Python runtime image while preserving non-root
# execution (UID 1000).

FROM registry.k8s.io/agent-sandbox/python-runtime-sandbox:v0.5.6@sha256:147a6a7f3b382683a065e4519b22088e75472317ce861d57031537a758836ab5

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

USER root
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes --only-binary=:all: --root-user-action=ignore -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt
COPY gateway.py gemini_agent.py egress_agent.py partner_api.py /app-src/
RUN chmod 0644 /app-src/*.py
USER 1000:1000
