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

# Use a NVIDIA CUDA base image
FROM nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04

# Set a non-root user and group
ARG UID=1000
ARG GID=1000
ARG USER=comfyuser
ARG GROUP=comfygroup

# Create the group and user
RUN groupadd --gid $GID $GROUP && \
    useradd --uid $UID --gid $GID -m $USER

# Set the working directory for the application
WORKDIR /app

# Install system dependencies
# Use --no-install-recommends to keep the image size down
# And clean up apt cache to further reduce image size
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        python3.10 \
        python3-pip \
        python3.10-venv && \  
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
# Ensure the app directory is owned by the new user
RUN chown -R ${USER}:${GROUP} /app

# Switch to the non-root user
USER ${USER}

# Create and activate the Python virtual environment
ENV VIRTUAL_ENV=/app/venv
RUN python3.10 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Clone ComfyUI and its dependencies
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /app/ComfyUI --branch v0.3.9
#WORKDIR /app/ComfyUI
#RUN git checkout v0.3.9

# Install PyTorch (inside the venv)
RUN pip install --no-cache-dir torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu121

# Install ComfyUI requirements (inside the venv)
RUN pip install --no-cache-dir -r /app/ComfyUI/requirements.txt

# Clone custom nodes (ensure they are in the correct location relative to the WORKDIR)
RUN git clone https://github.com/ltdrdata/ComfyUI-Manager /app/ComfyUI/custom_nodes/comfyui-manager

# Expose the port
EXPOSE 8848

# Define the command to run the application
# Use the python interpreter from the virtual environment
CMD ["python", "-u", "/app/ComfyUI/main.py", "--listen", "0.0.0.0", "--port", "8848"]
