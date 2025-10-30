# syntax=docker.io/docker/dockerfile:1.17.1

# Copyright 2025 Google LLC
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

FROM python:3.12-slim

WORKDIR /app

RUN apt-get -y update && \
  apt-get -y install git && \
  python -m pip install pip && \
  pip install git+https://github.com/google/maxdiffusion.git@v1

COPY --from=primary requirements.txt ./

RUN pip install -r requirements.txt

COPY --from=primary app.py ./

EXPOSE 8000

ENTRYPOINT ["python", "app.py"]
