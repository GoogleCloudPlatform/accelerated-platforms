#!/bin/bash
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
set -e

echo "########### $(date) - Starting Autotuner Entrypoint ###########"

# 1. Wait for GCSfuse and model files
echo "Waiting for model files in /gcs/${MODEL_ID}..."
until [ -f "/gcs/${MODEL_ID}/config.json" ]; do
  ls "/gcs/${MODEL_ID}" >/dev/null 2>&1 || true
  sleep 10
done
echo "Model files detected. Proceeding..."

# 2. Setup Environment
apt-get update && apt-get install -y git
pip install --upgrade pip
pip install git+https://github.com/openshift-psap/auto-tuning-vllm.git \
  optuna-dashboard \
  google-cloud-storage

mkdir -p /shared/db /tmp/results

# 3. Run Optimization
echo "Starting vLLM Auto-Tuning..."
auto-tune-vllm optimize --config /mnt/config/study.yaml --python-executable $(which python3)
TUNER_EXIT_CODE=$?

if [ $TUNER_EXIT_CODE -ne 0 ]; then
  echo "Tuner exited with error code $TUNER_EXIT_CODE. Attempting upload anyway..."
fi

# 4. Upload Results via Python (using a dedicated script file for safety)
echo "Starting GCS Upload..."
cat <<'EOF' >/tmp/upload_script.py
import os
import sys
import shutil
from google.cloud import storage
model_id = os.getenv('MODEL_ID')
bucket_name = os.getenv('VLLM_AUTO_TUNING_RESULTS_BUCKET')
# We will check both directories
paths_to_upload = {
    '/tmp/results': f'vllm-tuning/{model_id}/artifacts',
    '/shared/db': f'vllm-tuning/{model_id}/database'
}
if not model_id:
    print('ERROR: MODEL_ID is not set.')
    sys.exit(0)
if not bucket_name:
    print('ERROR: VLLM_AUTO_TUNING_RESULTS_BUCKET is not set.')
    sys.exit(0)

client = storage.Client()
bucket = client.bucket(bucket_name)

for local_dir, gcs_prefix in paths_to_upload.items():
    if not os.path.exists(local_dir):
        print(f'Skipping {local_dir}: Directory does not exist.')
        continue

    print(f'Scanning {local_dir} for files...')
    for root, _, files in os.walk(local_dir):
        for file in files:
            local_path = os.path.join(root, file)
            # Create a clean destination path in GCS
            rel_path = os.path.relpath(local_path, local_dir)
            destination_path = f"{gcs_prefix}/{rel_path}"

            try:
                blob = bucket.blob(destination_path)
                print(f'Uploading: {local_path} -> gs://{bucket_name}/{destination_path}')
                blob.upload_from_filename(local_path)
            except Exception as e:
                print(f'FAILED to upload {file}: {e}')

print('GCS Upload sequence finished.')
EOF
cat /tmp/upload_script.py
python3 /tmp/upload_script.py

# 5. Signal Completion
echo "########### $(date) - Job Finished ###########"
echo "Optimization complete. Signaling dashboard to stop."
touch /shared/db/tuning_complete.signal
