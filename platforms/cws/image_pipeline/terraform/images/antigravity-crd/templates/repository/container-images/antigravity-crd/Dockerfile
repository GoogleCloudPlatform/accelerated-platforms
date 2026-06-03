# syntax=docker.io/docker/dockerfile:1.17.1

# Copyright 2026 Google LLC
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

FROM $${AR_LOCATION}-docker.pkg.dev/$${AR_PROJECT_ID}/${cloudbuild_cws_image_registry_upstream_name}/base:latest

ARG DEBIAN_FRONTEND="noninteractive"

RUN apt-get update && \
  apt-get upgrade -y && \
  apt-get install -y \
  xvfb \
  xfce4 \
  xfce4-goodies \
  xbase-clients \
  dbus-x11 \
  psmisc \
  python3-psutil \
  xserver-xorg-video-dummy

RUN npm install --global @google/gemini-cli@latest

RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome-keyring.gpg && \
  echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" | tee /etc/apt/sources.list.d/google-chrome.list > /dev/null && \
  echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] https://dl.google.com/linux/chrome-remote-desktop/deb stable main" | tee /etc/apt/sources.list.d/chrome-remote-desktop.list > /dev/null && \
  apt-get update && \
  apt-get install -y google-chrome-stable chrome-remote-desktop

RUN dpkg-divert --add --rename --divert /usr/bin/google-chrome-stable.real /usr/bin/google-chrome-stable && \
  echo '#!/bin/bash' > /usr/bin/google-chrome-stable && \
  echo 'exec /usr/bin/google-chrome-stable.real --no-sandbox --disable-dev-shm-usage "$@"' >> /usr/bin/google-chrome-stable && \
  chmod +x /usr/bin/google-chrome-stable

RUN echo '#!/bin/bash' > /usr/bin/systemctl \
  && echo 'echo "Mock systemctl: $@"' >> /usr/bin/systemctl \
  && echo 'exit 0' >> /usr/bin/systemctl \
  && chmod +x /usr/bin/systemctl

RUN mkdir -p /etc/apt/keyrings && \
  curl -fsSL https://us-central1-apt.pkg.dev/doc/repo-signing-key.gpg | gpg --dearmor -o /etc/apt/keyrings/antigravity-repo-key.gpg && \
  echo "deb [signed-by=/etc/apt/keyrings/antigravity-repo-key.gpg] https://us-central1-apt.pkg.dev/projects/antigravity-auto-updater-dev/ antigravity-debian main" | tee /etc/apt/sources.list.d/antigravity.list > /dev/null && \
  apt-get update && \
  apt-get install -y antigravity && \
  dpkg-divert --add --rename --divert /usr/bin/antigravity.real /usr/bin/antigravity && \
  echo '#!/bin/bash' > /usr/bin/antigravity && \
  echo 'exec /usr/bin/antigravity.real --no-sandbox --disable-dev-shm-usage --disable-gpu "$@"' >> /usr/bin/antigravity && \
  chmod +x /usr/bin/antigravity

COPY --chmod=755 --from=my_context ./etc/workstation-startup.d/110_start-antigravity-crd.sh /etc/workstation-startup.d/110_start-antigravity-crd.sh

