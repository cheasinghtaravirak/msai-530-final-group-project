"""Request ID propagation: gateway header -> logs -> event envelope (correlation_id)."""

import contextvars
import logging
import uuid

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
        try:
            response = self.get_response(request)
        finally:
            reset_request_id(token)
        response["X-Request-ID"] = rid
        return response


class RequestIdFilter(logging.Filter):
    """Adds `request_id` to every log record so the log format can include it."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True
