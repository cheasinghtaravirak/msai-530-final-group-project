"""Request ID propagation: gateway header -> logs -> event envelope (correlation_id)."""

import contextvars
import json
import logging
import time
import uuid

from django.conf import settings

log = logging.getLogger("retail_common.request")

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return _request_id.get()


def set_request_id(value: str | None) -> contextvars.Token:
    return _request_id.set(value)


def reset_request_id(token: contextvars.Token) -> None:
    _request_id.reset(token)


class RequestIdMiddleware:
    """Reads X-Request-ID (set by the gateway) or creates one, and echoes it in the response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = set_request_id(rid)
        started = time.monotonic()
        try:
            response = self.get_response(request)
            if request.path != "/health":
                log.info(
                    "%s %s -> %s",
                    request.method,
                    request.path,
                    response.status_code,
                    extra={
                        "method": request.method,
                        "path": request.path,
                        "status": response.status_code,
                        "duration_ms": round((time.monotonic() - started) * 1000),
                    },
                )
        finally:
            reset_request_id(token)
        response["X-Request-ID"] = rid
        return response


class JsonFormatter(logging.Formatter):
    """One JSON object per line: the same keys in every service, so logs can be joined on request_id."""

    EXTRA = ("method", "path", "status", "duration_ms")

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "service": settings.SERVICE_NAME,
            "logger": record.name,
            "request_id": get_request_id(),
            "message": record.getMessage(),
        }
        entry.update({k: getattr(record, k) for k in self.EXTRA if hasattr(record, k)})
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry)
