from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

_CONFIGURED = False


class StructuredFormatter(logging.Formatter):
    """Render log records as compact key-value lines."""

    _RESERVED_FIELDS = {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
    }

    def format(self, record: logging.LogRecord) -> str:
        base_message = record.getMessage()
        fields: list[tuple[str, Any]] = [
            ("level", record.levelname),
            ("logger", record.name),
        ]

        if base_message:
            fields.append(("message", base_message))

        for key, value in sorted(record.__dict__.items()):
            if key in self._RESERVED_FIELDS or key.startswith("_"):
                continue
            if isinstance(value, Mapping):
                continue
            fields.append((key, value))

        rendered = " ".join(
            f"{key}={self._render_value(value)}" for key, value in fields
        )

        if record.exc_info:
            rendered = f"{rendered}\n{self.formatException(record.exc_info)}"

        return rendered

    @staticmethod
    def _render_value(value: Any) -> str:
        text = str(value)
        if not text:
            return '""'
        if any(char.isspace() for char in text) or "=" in text:
            return f'"{text.replace("\\", "\\\\").replace("\"", "\\\"")}"'
        return text


def configure_logging(level: int = logging.INFO) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Preserve handlers installed by hosting environments and test runners.
    # Removing the root handlers here can detach pytest's caplog handler when
    # application logging is configured after pytest starts capturing logs.
    if not any(getattr(handler, "_tiffin_structured", False) for handler in root_logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredFormatter())
        setattr(handler, "_tiffin_structured", True)
        root_logger.addHandler(handler)

    _CONFIGURED = True

def setup_logger(name: str) -> logging.Logger:
    configure_logging()
    logger = logging.getLogger(name)
    # Ensure structured application events reach root and pytest/host handlers.
    logger.setLevel(logging.NOTSET)
    logger.propagate = True
    return logger
