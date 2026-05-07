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

FROM python:3.11-slim

# Set working directory
WORKDIR /app

ARG MODEL_NAME

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY gradio_app.py logging.conf .

# Expose Gradio's default port
EXPOSE 7860

# environment variable for Gateway (will be overridden by K8s)
ENV GATEWAY_URL="http://localhost:8000"

# environment variable for the model to use
ENV MODEL=${MODEL_NAME}

# Run the application
CMD ["python", "gradio_app.py"]
