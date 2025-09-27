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
RUN apt-get -y update
RUN apt-get -y install git
COPY requirements.txt ./
RUN python -m pip install --upgrade pip
RUN pip install -r requirements.txt
RUN pip install git+https://github.com/google/maxdiffusion.git@v1
COPY app.py ./
EXPOSE 8000
ENTRYPOINT ["python", "app.py"]
