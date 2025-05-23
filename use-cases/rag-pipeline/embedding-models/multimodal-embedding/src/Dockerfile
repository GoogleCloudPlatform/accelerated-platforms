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

FROM pytorch/pytorch:2.5.0-cuda12.4-cudnn9-runtime

RUN apt-get update && \
    apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy your Python script
COPY requirements.txt /app/

# Install necessary libraries
RUN pip install -r requirements.txt

COPY blip2_server.py \ 
    logging.conf /app/

ENV PORT=8000

# Command to run your script
CMD gunicorn --bind=0.0.0.0:${PORT} --workers=4 'blip2_server:app'
