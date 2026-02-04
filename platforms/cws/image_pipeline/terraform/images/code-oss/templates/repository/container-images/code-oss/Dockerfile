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

# Temporary workaround until the key is updated in the upstream base image
RUN curl -sS https://dl.yarnpkg.com/debian/pubkey.gpg | sudo gpg --dearmour -o /usr/share/keyrings/yarn-keyring.gpg && \
  echo "deb [signed-by=/usr/share/keyrings/yarn-keyring.gpg] https://dl.yarnpkg.com/debian stable main" | sudo tee /etc/apt/sources.list.d/yarn.list && \
  apt-get update

RUN apt-get update && \
  apt-get upgrade -y && \
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
