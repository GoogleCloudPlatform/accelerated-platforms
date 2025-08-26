
import sys
import os
import pytest
from unittest.mock import MagicMock

# Add the 'src' directory to the Python path to resolve custom nodes
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Mock the 'folder_paths' module before any tests are imported.
# This is needed because it's a dependency of the code being tested,
# but it's part of the ComfyUI environment and not available during testing.
sys.modules['folder_paths'] = MagicMock()


@pytest.fixture(autouse=True)
def mock_sibling_nodes(monkeypatch):
    """
    Mocks all sibling node modules imported by the __init__.py file.
    This isolates the gemini_nodes test from its dependencies.
    """
    # Define a generic mock object to represent a node module
    mock_module = MagicMock()
    mock_module.NODE_CLASS_MAPPINGS = {}
    mock_module.NODE_DISPLAY_NAME_MAPPINGS = {}

    # A list of all sibling modules that __init__.py tries to import
    modules_to_mock = [
        "custom_nodes.google_genmedia.helper_nodes",
        "custom_nodes.google_genmedia.imagen3_nodes",
        "custom_nodes.google_genmedia.imagen4_nodes",
        "custom_nodes.google_genmedia.veo2_nodes",
        "custom_nodes.google_genmedia.veo3_nodes",
        "custom_nodes.google_genmedia.virtual_try_on",
    ]

    # Add the mocks to Python's list of loaded modules
    for module_name in modules_to_mock:
        monkeypatch.setitem(sys.modules, module_name, mock_module)
