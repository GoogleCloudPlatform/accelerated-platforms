# syntax=docker.io/docker/dockerfile:1.17.1

# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

ARG AR_PROJECT_ID
ARG AR_LOCATION

FROM $${AR_LOCATION}-docker.pkg.dev/$${AR_PROJECT_ID}/${cloudbuild_cws_image_registry_upstream_name}/code-oss:latest

ARG DEBIAN_FRONTEND="noninteractive"

# Temporary fix until the list files is updated upstream
RUN curl -fsSL https://packages.buildkite.com/helm-linux/helm-debian/gpgkey | gpg --dearmor | sudo tee /usr/share/keyrings/helm.gpg > /dev/null && \
  echo "deb [signed-by=/usr/share/keyrings/helm.gpg] https://packages.buildkite.com/helm-linux/helm-debian/any/ any main" | sudo tee /etc/apt/sources.list.d/helm-stable-debian.list

RUN apt-get -y update && \
  apt-get -y upgrade && \
  apt-get install -y \
  build-essential \
  gettext-base \
  libffi-dev \
  libz-dev \
  libbz2-dev \
  liblzma-dev \
  libncursesw5-dev \
  libreadline-dev \
  libsqlite3-dev \
  libssl-dev \
  moreutils
