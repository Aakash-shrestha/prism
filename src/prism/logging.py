import json
import logging
import logging.config
from typing import Any


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # stdlib LogRecord attributes — everything else is an extra field
        _STDLIB_ATTRS = {
            "name", "msg", "args", "created", "filename", "funcName", "levelname",
            "levelno", "lineno", "module", "msecs", "pathname", "process",
            "processName", "relativeCreated", "thread", "threadName", "taskName",
            "exc_info", "exc_text", "stack_info", "message", "asctime",
        }
        for key, value in record.__dict__.items():
            if key not in _STDLIB_ATTRS and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload)


def configure_logging(level: str = "INFO") -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {"()": _JsonFormatter},
            },
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                },
            },
            "root": {
                "handlers": ["stdout"],
                "level": level,
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
