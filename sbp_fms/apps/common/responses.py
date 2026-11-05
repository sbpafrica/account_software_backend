from typing import Any, Optional
from rest_framework.response import Response
from rest_framework import status


class ApiResponse:
    """
    [API RESPONSE]:
    Standardized API response wrapper for SBP Africa Group (SBP-FMS).
    Ensures predictable, consistent JSON envelopes across all API endpoints.
    """
    @staticmethod
    def success(
        data: Any = None,
        message: str = "Operation completed successfully.",
        status_code: int = status.HTTP_200_OK,
        meta: Optional[dict] = None,
        headers: Optional[dict] = None
    ) -> Response:
        payload = {
            "success": True,
            "message": message,
            "data": data,
        }
        if meta is not None:
            payload["meta"] = meta
        return Response(payload, status=status_code, headers=headers)

    @staticmethod
    def error(
        message: str = "An error occurred.",
        errors: Any = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: Optional[str] = None,
        headers: Optional[dict] = None
    ) -> Response:
        payload = {
            "success": False,
            "message": message,
            "errors": errors if errors is not None else [],
            "detail": message,  # Backward compatibility for DRF error consumers
        }
        if code:
            payload["code"] = code
        return Response(payload, status=status_code, headers=headers)


def api_success(
    data: Any = None,
    message: str = "Operation completed successfully.",
    status_code: int = status.HTTP_200_OK,
    meta: Optional[dict] = None,
    **kwargs
) -> Response:
    return ApiResponse.success(data=data, message=message, status_code=status_code, meta=meta, **kwargs)


def api_error(
    message: str = "An error occurred.",
    errors: Any = None,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    code: Optional[str] = None,
    **kwargs
) -> Response:
    return ApiResponse.error(message=message, errors=errors, status_code=status_code, code=code, **kwargs)
