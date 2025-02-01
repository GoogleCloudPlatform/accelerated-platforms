# Copyright 2024 Google LLC
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

FROM python:3.12.4-slim as build-stage

ENV PATH=/venv/bin:${PATH}
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get -y update \
    && pip install --upgrade pip \
    && python -m venv /venv

COPY requirements.txt /venv/requirements.txt

RUN pip install --no-cache-dir -r /venv/requirements.txt

COPY logging.conf /app/
COPY datapreprocessing/ /app/datapreprocessing

WORKDIR /app

CMD ["python", "-m", "datapreprocessing.preprocessing_finetuning"]
