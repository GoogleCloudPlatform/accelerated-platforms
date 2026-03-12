# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# This is a preview version of Google GenAI custom nodes

import configparser
import importlib
import logging
import os
import sys


# Since ComfyUI uses a root logger with fileConfig(), setting up the custom logger with fileConfig()
# will result in duplicate logging so we are defining the custom logger with ConfigParser() that
# allows us to stop the propagation of the logs to the root logger
def setup_custom_package_logger():
    """
    Reads the custom format, level, handler class, and arguments from logging.conf,
    creates a custom isolated handler, and attaches it to the package logger.
    """

    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(current_dir, "logging.conf")
    config = configparser.ConfigParser(interpolation=None)

    try:
        config.read(config_file)
        if "formatter_customFormatter" not in config:
            logging.warning(
                f"Could not find [formatter_customFormatter] in {config_file}."
            )
            return
        CUSTOM_FORMAT = config["formatter_customFormatter"]["format"]
        custom_formatter = logging.Formatter(CUSTOM_FORMAT)

        if "handler_consoleHandler" not in config:
            logging.warning(
                f"Could not find [handler_consoleHandler] in {config_file}. Skipping."
            )
            return
        # Read and initialize logger with the configs defined in console handler section of the logging.conf
        handler_config = config["handler_consoleHandler"]
        handler_class_str = handler_config["class"]
        handler_args_str = handler_config["args"]
        LOG_LEVEL_STR = handler_config["level"]

        module_name = "logging"
        class_name = handler_class_str
        handler_module = importlib.import_module(module_name)
        HandlerClass = getattr(
            handler_module, class_name
        )  # initializes logging.StreamHandler but will dynamically instantiate any class defined in logging.conf

        # Safely evaluate the arguments (e.g., (sys.stdout,))
        handler_args = eval(handler_args_str, {"sys": sys, "logging": logging})
        custom_handler = HandlerClass(*handler_args)
        LOG_LEVEL = logging.getLevelName(LOG_LEVEL_STR.upper())
        custom_handler.setFormatter(custom_formatter)
        custom_handler.setLevel(LOG_LEVEL)

        package_name = __name__.split(".")[0]
        package_logger = logging.getLogger(package_name)

        # Prevent logs from flowing up to ComfyUI's root logger
        package_logger.propagate = False

        if not package_logger.handlers:
            package_logger.setLevel(LOG_LEVEL)
            package_logger.addHandler(custom_handler)
            package_logger.info(
                f"Initialized isolated custom logger for '{package_name}' using external config."
            )

    except Exception as e:
        logging.error(f"Failed to load or apply logging configuration: {e}")


setup_custom_package_logger()


from .gemini_flash_image_node import (
    NODE_CLASS_MAPPINGS as GEMINI_FLASH_25_IMAGE_NODE_CLASS_MAPPINGS,
)
from .gemini_flash_image_node import (
    NODE_DISPLAY_NAME_MAPPINGS as GEMINI_FLASH_25_IMAGE_NODE_DISPLAY_NAME_MAPPINGS,
)
from .gemini_nodes import NODE_CLASS_MAPPINGS as GEMINI_NODE_CLASS_MAPPINGS
from .gemini_nodes import (
    NODE_DISPLAY_NAME_MAPPINGS as GEMINI_NODE_DISPLAY_NAME_MAPPINGS,
)
from .gemini_pro_image_node import (
    NODE_CLASS_MAPPINGS as GEMINI_PRO_IMAGE_NODE_CLASS_MAPPINGS,
)
from .gemini_pro_image_node import (
    NODE_DISPLAY_NAME_MAPPINGS as GEMINI_PRO_IMAGE_NODE_DISPLAY_NAME_MAPPINGS,
)
from .helper_nodes import NODE_CLASS_MAPPINGS as HELPER_NODE_CLASS_MAPPINGS
from .helper_nodes import (
    NODE_DISPLAY_NAME_MAPPINGS as HELPER_NODE_DISPLAY_NAME_MAPPINGS,
)
from .imagen3_nodes import NODE_CLASS_MAPPINGS as IMAGEN3_NODE_CLASS_MAPPINGS
from .imagen3_nodes import (
    NODE_DISPLAY_NAME_MAPPINGS as IMAGEN3_NODE_DISPLAY_NAME_MAPPINGS,
)
from .imagen4_nodes import NODE_CLASS_MAPPINGS as IMAGEN4_NODE_CLASS_MAPPINGS
from .imagen4_nodes import (
    NODE_DISPLAY_NAME_MAPPINGS as IMAGEN4_NODE_DISPLAY_NAME_MAPPINGS,
)
from .lyria2_nodes import NODE_CLASS_MAPPINGS as LYRIA2_NODE_CLASS_MAPPINGS
from .lyria2_nodes import (
    NODE_DISPLAY_NAME_MAPPINGS as LYRIA2_NODE_DISPLAY_NAME_MAPPINGS,
)
from .veo2_nodes import NODE_CLASS_MAPPINGS as VEO2_NODE_CLASS_MAPPINGS
from .veo2_nodes import NODE_DISPLAY_NAME_MAPPINGS as VEO2_NODE_DISPLAY_NAME_MAPPINGS
from .veo3_nodes import NODE_CLASS_MAPPINGS as VEO3_NODE_CLASS_MAPPINGS
from .veo3_nodes import NODE_DISPLAY_NAME_MAPPINGS as VEO3_NODE_DISPLAY_NAME_MAPPINGS
from .virtual_try_on import NODE_CLASS_MAPPINGS as VTO_NODE_CLASS_MAPPINGS
from .virtual_try_on import NODE_DISPLAY_NAME_MAPPINGS as VTO_NODE_DISPLAY_NAME_MAPPINGS

# Combine all node class mappings
NODE_CLASS_MAPPINGS = {
    **IMAGEN3_NODE_CLASS_MAPPINGS,
    **IMAGEN4_NODE_CLASS_MAPPINGS,
    **LYRIA2_NODE_CLASS_MAPPINGS,
    **VEO2_NODE_CLASS_MAPPINGS,
    **VEO3_NODE_CLASS_MAPPINGS,
    **GEMINI_NODE_CLASS_MAPPINGS,
    **HELPER_NODE_CLASS_MAPPINGS,
    **VTO_NODE_CLASS_MAPPINGS,
    **GEMINI_FLASH_25_IMAGE_NODE_CLASS_MAPPINGS,
    **GEMINI_PRO_IMAGE_NODE_CLASS_MAPPINGS,
}

# Combine all node display name mappings
NODE_DISPLAY_NAME_MAPPINGS = {
    **IMAGEN3_NODE_DISPLAY_NAME_MAPPINGS,
    **IMAGEN4_NODE_DISPLAY_NAME_MAPPINGS,
    **LYRIA2_NODE_DISPLAY_NAME_MAPPINGS,
    **VEO2_NODE_DISPLAY_NAME_MAPPINGS,
    **VEO3_NODE_DISPLAY_NAME_MAPPINGS,
    **GEMINI_NODE_DISPLAY_NAME_MAPPINGS,
    **HELPER_NODE_DISPLAY_NAME_MAPPINGS,
    **VTO_NODE_DISPLAY_NAME_MAPPINGS,
    **GEMINI_FLASH_25_IMAGE_NODE_DISPLAY_NAME_MAPPINGS,
    **GEMINI_PRO_IMAGE_NODE_DISPLAY_NAME_MAPPINGS,
}

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
