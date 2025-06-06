import os
from typing import Optional
from vertexai.preview.reasoning_engines import AdkApp

# Corrected imports
from . import config
from .game_context_manager import GameContextManager
from .bq_logger import BigQueryLogger
from .agent import setup_gaming_agents
from .utils.logging_setup import app_logger as logger

_adk_app_instance: Optional[AdkApp] = None
_game_context_instance: Optional[GameContextManager] = None
_bq_logger_instance: Optional[BigQueryLogger] = None


async def get_adk_app() -> AdkApp:
    """
    Ensures the AdkApp and its dependencies are initialized exactly once
    and returns the singleton instance.
    """
    global _game_context_instance, _bq_logger_instance, _adk_app_instance

    if _adk_app_instance is None:
        logger.info("--- Lazy Initialization: Starting ADK App Setup ---")
        try:
            logger.debug("Attempting to get game data source...")
            game_data_source = os.environ.get("GAME_DATA_GCS_URI", config.GAME_DATA_PATH)
            _game_context_instance = GameContextManager(game_data_source)
            logger.debug("GameContextManager initialized.")

            logger.debug("Attempting to initialize BigQueryLogger...")
            _bq_logger_instance = BigQueryLogger(
                config.PROJECT_ID, config.BQ_DATASET_ID, config.BQ_TABLE_ID, config.LOCATION
            )
            logger.debug("BigQueryLogger initialized.")

            logger.debug("Attempting to setup gaming agents...")
            root_agent = await setup_gaming_agents(_game_context_instance, _bq_logger_instance)
            logger.debug("Gaming agents setup complete.")

            logger.debug("Attempting to initialize AdkApp...")
            _adk_app_instance = AdkApp(agent=root_agent)
            logger.debug("_adk_app_instance initialized by getter.")
            logger.info("--- Lazy Initialization: ADK App Setup Completed ---")
        except Exception as e:
            logger.exception(f"--- Lazy Initialization: ERROR during ADK App setup: {e} ---")
            raise

    return _adk_app_instance

