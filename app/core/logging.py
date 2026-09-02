from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar

from app.config import settings

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get("-")
        return True


class _JsonFormatter(logging.Formatter):

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _build_formatter() -> logging.Formatter:
    if settings.is_deployed:
        return _JsonFormatter()
    return logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] [%(request_id)s] %(message)s"
    )


def _ensure_request_id_filter(handler: logging.Handler) -> None:
    if not any(isinstance(f, RequestIdFilter) for f in handler.filters):
        handler.addFilter(RequestIdFilter())


def configure_logging(level: str | None = None) -> None:
    root = logging.getLogger()
    resolved = (level or settings.log_level).upper()
    root.setLevel(resolved)

    formatter = _build_formatter()

    if root.handlers:
        for handler in root.handlers:
            _ensure_request_id_filter(handler)
            handler.setFormatter(formatter)
    else:
        handler = logging.StreamHandler(sys.stdout)
        _ensure_request_id_filter(handler)
        handler.setFormatter(formatter)
        root.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("apscheduler").setLevel(logging.INFO)
