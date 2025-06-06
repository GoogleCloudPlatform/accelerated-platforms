import json
from google.cloud import storage  # Import storage client
from . import config  # Import config from the same package


class GameContextManager:
    """
    Manages loading and providing access to game context data from a JSON file or GCS URI.
    Uses a singleton-like pattern to ensure data is loaded only once.
    """
    _game_data = None  # Stores the loaded game data
    _data_path = config.GAME_DATA_PATH  # Default path from config

    def __init__(self, path: str = None):
        """Initializes the manager and attempts to load data if not already loaded."""
        if path:
            self._data_path = path
        GameContextManager.load_data(self._data_path)  # Load data during initialization if not already loaded

    @classmethod
    def load_data(cls, path: str):
        """Loads game data from the specified JSON file or GCS URI into the class variable."""
        if cls._game_data is None:  # Only load once globally
            try:
                if path.startswith("gs://"):  # Check if it's a GCS URI
                    # Parse bucket and blob name from GCS URI
                    parts = path.split('/')
                    bucket_name = parts[2]
                    blob_name = '/'.join(parts[3:])

                    storage_client = storage.Client()
                    bucket = storage_client.bucket(bucket_name)
                    blob = bucket.blob(blob_name)

                    # Download as string and load JSON
                    cls._game_data = json.loads(blob.download_as_text())
                    print(f"Game data loaded successfully from GCS: {path}.")
                else:  # Assume it's a local file path
                    with open(path, "r") as f:
                        cls._game_data = json.load(f)
                    print(f"Game data loaded successfully from local file: {path}.")
            except Exception as e:  # Catch broader exceptions for file/GCS issues
                print(f"Error loading game_data.json from {path}: {e}")
                cls._game_data = {}
        return cls._game_data

    def get_data(self) -> dict:
        """Returns the loaded game data."""
        # This will ensure data is loaded if accessed before explicit load_data() call
        if GameContextManager._game_data is None:
            GameContextManager.load_data(self._data_path)
        return GameContextManager._game_data


