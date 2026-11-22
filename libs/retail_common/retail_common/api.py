"""API conventions: error format and pagination (implementation plan §3).

Every error response looks like:
    {"error": {"code": "PRICE_UNAVAILABLE", "message": "...", "details": {}}}
"""

from typing import Any

from rest_framework import status as http_status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import exception_handler as drf_exception_handler


class ApiError(APIException):
    """Raise for business errors: raise ApiError("PRICE_UNAVAILABLE", "No price for COKE-330", status=422)"""

    def __init__(self, code: str, message: str, *, status: int = http_status.HTTP_400_BAD_REQUEST, details: Any = None):
        super().__init__(detail=message, code=code)
        self.status_code = status
        self.error_code = code
        self.details = details or {}


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, ApiError):
        code, message, details = exc.error_code, str(exc.detail), exc.details
    elif isinstance(exc, ValidationError):
        code, message, details = "VALIDATION_ERROR", "Invalid input", response.data
    else:
        codes = exc.get_codes() if hasattr(exc, "get_codes") else getattr(exc, "default_code", "error")
        code = codes if isinstance(codes, str) else getattr(exc, "default_code", "error")
        data = response.data
        message = data.get("detail", str(exc)) if isinstance(data, dict) else str(exc)
        details = {}

    response.data = {"error": {"code": str(code).upper(), "message": str(message), "details": details}}
    return response


class Pagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 500
