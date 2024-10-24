import json
import logging


class CustomJSONFormatter(logging.Formatter):
    def __init__(
        self,
        fmt=None,
        datefmt=None,
        style="%",
        validate=True,
        defaults=None,
    ):
        super().__init__(
            fmt=fmt,
            datefmt=datefmt,
            style=style,
            validate=validate,
            defaults=defaults,
        )

        self._ignore_keys = {
            "args",
            "levelno",
            "msecs",
            "msg",
            "pathname",
        }

        self._rename_keys = {
            "created": "timestamp",
            "levelname": "level",
            "relativeCreated": "runtime",
        }

        self._debug_keys = {
            "filename",
            "funcName",
            "lineno",
            "module",
        }

    # LogRecord object: https://docs.python.org/3/library/logging.html#logrecord-attributes
    def format(self, record: logging.LogRecord) -> str:
        entry = record.__dict__.copy()
        entry["message"] = record.getMessage()

        # Removed ignored keys
        for key in self._ignore_keys:
            entry.pop(key, None)

        # Remove keys based on log level
        if record.levelno > logging.DEBUG:
            for key in self._debug_keys:
                entry.pop(key, None)

        # Rename keys
        for key, value in list(self._rename_keys.items()):
            if key in entry:
                entry[value] = entry.pop(key)

        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)

        if record.exc_text:
            entry["exc_info"] = record.exc_text

        if record.stack_info:
            entry["stack_info"] = self.formatStack(record.stack_info)

        # Delete keys with None value
        for key, value in list(entry.items()):
            if value is None:
                del entry[key]

        return json.dumps(entry)
    
