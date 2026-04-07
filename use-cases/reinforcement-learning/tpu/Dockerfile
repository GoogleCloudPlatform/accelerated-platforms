FROM python:3.12-slim-bullseye

# 1. System setup (Matches official Dockerfile)
RUN apt-get update && apt-get install -y curl gnupg git build-essential wget
RUN pip install --upgrade pip uv
ENV UV_SYSTEM_PYTHON=1

WORKDIR /deps

# 2. Clone the repo to get the 'setup.sh' and requirements
RUN git clone https://github.com/google/maxtext.git .

# 3. Run the setup logic for GRPO (matches the official WORKFLOW=post-training)
# This replaces the complex ARG/ENV logic with the direct command for v5e
# Combine the install and cleanup to keep the layer small
RUN uv pip install -e ".[tpu-post-train]" --resolution=lowest && \
    install_maxtext_tpu_post_train_extra_deps && \
    uv cache clean && \
    rm -rf /root/.cache/uv

RUN uv pip install mlflow huggingface_hub clu math_verify google-cloud-storage

# 4. Copy your RL training script and chat template
COPY train_single_node_fix.py /deps/train_single_node_fix.py
COPY llama3_rl.json /deps/llama3_rl.json

# 5. Official Pathing
ENV PYTHONPATH="/deps/src"
ENV PYTHONUNBUFFERED=1

# Start your script
CMD ["python3", "train_single_node_fix.py"]
