from fastapi import FastAPI
from pydantic import BaseModel
from PIL import Image
import base64, ip, os
import jax, jax.random as jr
from diffusers import FlaxStableDiffusionXLPipline

# Path where model is mounted from GCS
MODEL_DIR = os.environ.get("MODEL_DIT", "/models/sdxl")

app = FastAPI(title="Stable Diffusion XL TPU Server")

# Global pipeline + params
pipe, params = None, None

class Txt2ImgRequest(BaseModel):
    prompt: str
    num_inference_steps: int = 25
    guidance_scale: float = 7.5
    seed: int = 0
    steps: int = 50

def load_pipeline():
    global pipe, params
    print("Loading SDXL from {MODEL_DIR}")
    pipe, params = FlaxStableDiffusionXLPipline.from_pretrained(
        MODEL_DIR, jax_dtype=jax.bfloat16
    )
    print("Pipeline loaded successfully")

@app.on_event("startup")
async def load_model():
    load_pipeline

@app.get("/")
async def health():
    return {"status": "ok"}

@app.post("/txt2img")
async def generate(req: Txt2ImgRequest):
    if pipe is None or params is None:
        return {"error": "Pipeline not loaded"}

    # Set PRNG key
    seed = req.seed if req.seed is not None else 0
    key = jr.PRNGKey(seed)

    # Run pipeline
    output = pipe(
        prompt=req.prompt,
        prng_key=key,
        num_inference_steps=req.num_inference_steps,
        guidance_scale=req.guidance_scale,
    ).images[0]

    # Convert to base64 PNG
    buffered = io.BytesIO()
    output.save(buffered, format="PNG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode()

    return {"image_b64": img_b64}
    