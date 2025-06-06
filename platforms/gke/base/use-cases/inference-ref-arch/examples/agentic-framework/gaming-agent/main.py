import os
import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles

# Import configured logger and other components
from .utils.logging_setup import app_logger as logger
from .adk_service import get_adk_app
from .api import endpoints

# --- FastAPI Lifespan event handler ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("--- API Lifespan: Triggering ADK App Initialization ---")
    await get_adk_app()
    logger.info("--- API Lifespan: ADK App ready ---")
    yield
    logger.info("--- API Shutdown: Performing cleanup (if any) ---")


# Initialize FastAPI app
app = FastAPI(
    title="Gaming Content Agent API",
    description="API for AI-powered game content generation (dialogue, images, video) driven by an ADK agent.",
    version="0.1.0",
    lifespan=lifespan
)

# --- STATIC FILE MOUNTING ---
# Get the absolute path of the directory containing main.py
current_dir = os.path.dirname(os.path.abspath(__file__))
print(f"Debug: current_dir = {current_dir}") # Expected: .../my_gaming_agent/app

# Construct the path to the static directory
STATIC_DIR = os.path.join(current_dir, "static")
print(f"Debug: STATIC_DIR = {STATIC_DIR}") # Expected: .../my_gaming_agent/static

if not os.path.isdir(STATIC_DIR):
    # This block *should not* be hit if your pwd and ls -ltr are accurate.
    # If it is hit, it implies the path is genuinely wrong at runtime.
    logger.error(f"Static directory NOT FOUND at expected path: {STATIC_DIR}")
    raise RuntimeError(f"Static directory '{STATIC_DIR}' does not exist. Please check your project structure.")
else:
    logger.info(f"Static directory FOUND at: {STATIC_DIR}")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(endpoints.router)

if __name__ == "__main__":
    logger.info("Running Uvicorn in single-process mode (via if __name__ == '__main__':).")
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), workers=1)
