import logging
import logging.config
import os


def configure_logging(config_file="logging.conf"):
    """
    Configures the logging system and returns a logger for the current script.

    Args:
        config_file (str): Path to the logging configuration file. 
                            Defaults to "logging.conf".

    Returns:
        logging.Logger: A configured logger instance for the current script.
    """

    logging.config.fileConfig(config_file)
    logger = logging.getLogger(__name__)

    if "LOG_LEVEL" in os.environ:
        new_log_level = os.environ["LOG_LEVEL"].upper()
        try:
            numeric_level = getattr(logging, new_log_level)
            logging.root.setLevel(numeric_level)
            logger.info(
                "Log level set to '%s' via LOG_LEVEL environment variable", new_log_level
            )
        except AttributeError:
            logger.warning(
                "Invalid LOG_LEVEL value: '%s'. Using default log level.", new_log_level
            )

    return logger  