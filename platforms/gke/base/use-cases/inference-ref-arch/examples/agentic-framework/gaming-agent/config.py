# config.py

# Google Cloud Project and Location
PROJECT_ID = "cloud-sa-ml"
LOCATION = "us-central1"

# BigQuery Logging Configuration
BQ_DATASET_ID = "gaming_logs"
BQ_TABLE_ID = "game_agent_outputs"

# Google Cloud Storage Configuration
GCS_BUCKET_NAME = "gaming-demo"
GCS_DESTINATION_BLOB_PREFIX = "generated_images/" # For images
VIDEO_OUTPUT_GCS_PREFIX = f"gs://{GCS_BUCKET_NAME}/generated_videos/" # For videos

# Game Data File Path
GAME_DATA_PATH = "my_gaming_agent/game_data.json"
GAME_DATA_GCS_URI="gs://gaming-demo/game_data.json"


# AI Model IDs
GEMINI_FLASH_MODEL = "gemini-2.0-flash"
IMAGEN_MODEL = "imagen-3.0-generate-002"
VEO_MODEL = "veo-2.0-generate-001"


# Generation Quantities
NUM_IMAGES_TO_GENERATE = 4 # Generate 4 images for each dialogue
NUM_DIALOGUES_TO_GENERATE = 3 # (This is implicitly handled by dialogue generation agent)
NUM_VIDEOS_PER_CALL = 2 # How many videos generate_and_log_video_tool produces per call
