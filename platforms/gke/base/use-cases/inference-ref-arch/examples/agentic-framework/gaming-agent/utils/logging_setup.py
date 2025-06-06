import logging
import sys
from google.cloud import logging as cloud_logging
from google.cloud.logging.handlers import CloudLoggingHandler

def setup_logging():
    logger = logging.getLogger("gaming_agent_app")
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    logger.setLevel(logging.DEBUG)

    logging_client = cloud_logging.Client()
    cloud_handler = CloudLoggingHandler(logging_client, name="gaming_agent_app_logs")
    formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
    cloud_handler.setFormatter(formatter)
    logger.addHandler(cloud_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical("Unhandled exception caught by global handler:", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception
    return logger

# Call setup_logging once when this module is imported
app_logger = setup_logging()

