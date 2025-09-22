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

import io
import os
import torch
import uvicorn
from diffusers import FluxPipeline
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from PIL import Image
from accelerate import Accelerator 

# It's crucial to instantiate the Accelerator object before any
# other library-specific code is run.
accelerator = Accelerator(device_placement=False)

# The model path is the local path mounted from GCS
MODEL_DIR = os.environ.get("MODEL_ID")
NUM_GPUS = int(os.environ.get("TENSOR_PARALLEL_SIZE", 1))

print(f"MODEL_DIR: {MODEL_DIR}")
print(f"Number of GPUs: {NUM_GPUS}")

# Define the FastAPI app globally.
app = FastAPI()

# Initialize pipeline object globally. It will only be loaded on the main process.
pipeline = None

# --- CRITICAL FIX: Load and Prepare ONLY on the Main Process (GPU 0) ---
if accelerator.is_main_process:
    try:
        # Load the pipeline from the local GCS mount with local_files_only=True
        # Only rank 0 executes this code block.
        pipeline = FluxPipeline.from_pretrained(
            f"/gcs/{MODEL_DIR}",
            dtype=torch.float16,
            local_files_only=True,
        )
    except Exception as e:
        print(f"Error loading pipeline: {e}")
        raise e

    # The `accelerator.prepare()` call wraps the pipeline for distributed execution.
    # When run on rank 0, this prepares the model for sharding across ALL processes/GPUs.
    pipeline = accelerator.prepare(pipeline)


class InferenceRequest(BaseModel):
    prompt: str
    height: int = 1024
    width: int = 1024
    num_inference_steps: int = 4


@app.post("/generate")
async def generate_image(request: InferenceRequest):
    # This endpoint is served by the main process (GPU 0), which coordinates
    # the sharded model across all 8 GPUs for the actual computation.

    # Ensure this runs only if the pipeline was successfully loaded on rank 0
    if pipeline is None:
        raise Exception("Model pipeline failed to initialize on main process.")

    # This ensures that PyTorch doesn't build a computation graph during inference.
    with torch.no_grad():
        generated_images = pipeline(
            prompt=request.prompt,
            height=request.height,
            width=request.width,
            num_inference_steps=request.num_inference_steps,
        ).images

    image = generated_images[0]

    byte_stream = io.BytesIO()
    image.save(byte_stream, format="PNG")
    byte_stream.seek(0)

    return StreamingResponse(byte_stream, media_type="image/png")


# The `accelerate` launcher is responsible for running the Uvicorn server
# on the main process only, to avoid conflicts.
if __name__ == "__main__":
    port = int(os.environ.get("MAIN_PROCESS_PORT", 8000))

    # ⭐ FINAL FIX: Initial synchronization for ALL 8 processes BEFORE branching
    # This ensures model loading and preparation is complete on Rank 0
    # and all workers are ready for the group to begin.
    accelerator.wait_for_everyone()

    if accelerator.is_main_process:
        # Rank 0 runs the web server.
        uvicorn.run(app, host="0.0.0.0", port=port, workers=1)
    else:
        # Workers (Ranks 1-7) MUST stay alive to serve sharded requests.
        print(
            f"Worker process {accelerator.process_index} waiting indefinitely for tasks..."
        )
        import time

        while True:
            # Sleep briefly to reduce unnecessary CPU load on the workers
            time.sleep(5)
