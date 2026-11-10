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


def api_response_postprocessing_hook(result, generator, request, public):
    """
    [DRF-SPECTACULAR POSTPROCESSING HOOK]:
    Wraps OpenAPI response schemas for 200/201 endpoints in the standardized ApiResponse envelope:
    {
        "success": true,
        "message": "...",
        "data": { ... }
    }
    Paginated schemas (which are already wrapped by CustomPageNumberPagination)
    and schemas that already define the standard envelope are preserved.
    """
    paths = result.get('paths', {})
    for path, path_item in paths.items():
        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                continue
            responses = operation.get('responses', {})
            for code, resp in responses.items():
                if str(code) in ('200', '201'):
                    content = resp.get('content', {}).get('application/json', {})
                    schema = content.get('schema')
                    if not schema:
                        continue
                    ref = schema.get('$ref', '')
                    if 'Paginated' in ref:
                        continue
                    if schema.get('type') == 'object' and 'success' in schema.get('properties', {}):
                        continue
                    content['schema'] = {
                        'type': 'object',
                        'properties': {
                            'success': {'type': 'boolean', 'example': True},
                            'message': {'type': 'string', 'example': 'Operation completed successfully.'},
                            'data': schema
                        },
                        'required': ['success', 'message']
                    }
    return result

