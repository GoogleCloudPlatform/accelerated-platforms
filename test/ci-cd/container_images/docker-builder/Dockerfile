# syntax=docker.io/docker/dockerfile:1.17.1

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

ARG AR_LOCATION
ARG AR_PROJECT_ID
ARG DOCKER_TAG=28.3.3-dind-alpine3.22

FROM ${AR_LOCATION}-docker.pkg.dev/${AR_PROJECT_ID}/docker-io/docker:${DOCKER_TAG}

COPY --chmod=700 --from=my_context ./ /
