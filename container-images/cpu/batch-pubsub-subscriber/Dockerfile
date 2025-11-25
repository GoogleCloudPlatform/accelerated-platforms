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

# --- STAGE 1: Build Stage ---
# Use a Python image that includes tools for installing dependencies
FROM python:3.14.0-slim-trixie as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_HOME /usr/src/app

# Create and set the working directory
WORKDIR $APP_HOME

# Copy only the requirements file first to leverage Docker cache
COPY --from=primary requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# --- STAGE 2: Final Runtime Stage ---
# Use a minimal runtime image for security and size
FROM python:3.14.0-slim-trixie

# Set environment variables for the runtime
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_HOME /usr/src/app

# Create and set the working directory
WORKDIR $APP_HOME

# Copy installed dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the application script itself
COPY --from=primary app.py .

# Command to run the application when the container starts
CMD ["python", "app.py"]
