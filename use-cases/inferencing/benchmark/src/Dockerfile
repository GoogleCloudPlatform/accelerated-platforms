# Copyright 2022 Google Inc. All rights reserved.
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

FROM python:3.13.0-alpine

# Install build dependencies
RUN apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    linux-headers \
    python3-dev 

COPY requirements.txt /

# Install the required dependencies via pip
RUN pip3 install --upgrade pip
RUN pip3 install --no-cache-dir -r requirements.txt

# Remove build dependencies to keep the image size small
RUN apk del .build-deps

COPY custom_json_formatter.py logging.conf run.sh tasks.py /

# Expose the required Locust ports
EXPOSE 5557 5558 8089

# Set script to be executable
RUN chmod 755 /run.sh

# Start Locust using LOCUS_OPTS environment variable
ENTRYPOINT ["/run.sh"]
