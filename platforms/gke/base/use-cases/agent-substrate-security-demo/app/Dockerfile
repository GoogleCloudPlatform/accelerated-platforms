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

# Production immutable image for the Agent Substrate Security Demo actors and gateway.
# Build & push example:
#   gcloud builds submit ./app --tag "${REGION}-docker.pkg.dev/${PROJECT_ID}/agent-substrate/demo-app:v1.0.0"
#   APP_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/agent-substrate/demo-app@sha256:<DIGEST>" ./scripts/stage.sh

FROM registry.k8s.io/agent-sandbox/python-runtime-sandbox:v0.5.6@sha256:147a6a7f3b382683a065e4519b22088e75472317ce861d57031537a758836ab5

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY gateway.py gemini_agent.py egress_agent.py /app-src/
