import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent / "modules" / "python"))

# Mock the 'folder_paths' module
sys.modules["folder_paths"] = MagicMock()
