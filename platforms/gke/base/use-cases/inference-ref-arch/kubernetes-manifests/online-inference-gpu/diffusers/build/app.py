# Copyright 2025 Google LLC

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# https://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
from diffusers import FluxPipeline
from fastapi import FastAPI
import io
import os
from pydantic import BaseModel
from PIL import Image
import torch

app = FastAPI()

# The model path is the local path mounted from GCS
MODEL_DIR = os.environ.get("MODEL_ID")
print(f"MODEL_DIR: {MODEL_DIR}")

pipeline = FluxPipeline.from_pretrained(
    f"/gcs/{MODEL_DIR}",
    torch_dtype=torch.float16,
    local_files_only=True, 
)
pipeline.enable_model_cpu_offload()

class InferenceRequest(BaseModel):
    prompt: str
    height: int = 1024
    width: int = 1024
    num_inference_steps: int = 4

@app.post("/generate")
async def generate_image(request: InferenceRequest):
    generated_images = pipeline(
        prompt=request.prompt,
        height=request.height,
        width=request.width,
        num_inference_steps=request.num_inference_steps,
    ).images
    
    # Convert the first image to a base64 string or save to a file
    generated_images[0].save("generated_image.png")
    # Take the first image
    image = generated_images[0]

    # Save the image to a byte buffer
    byte_stream = io.BytesIO()
    image.save(byte_stream, format="PNG")
    byte_stream.seek(0)

    # Encode the image bytes to a Base64 string
    base64_image = base64.b64encode(byte_stream.read()).decode("utf-8")

    # Return the Base64 string in a JSON response
    return {"message": "Image generation complete.", "image": base64_image}
    