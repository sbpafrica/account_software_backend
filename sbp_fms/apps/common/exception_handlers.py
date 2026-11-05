import logging
from django.core.exceptions import ValidationError as DjangoValidationError, PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from django.db import IntegrityError
from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException
from rest_framework import status
from rest_framework.response import Response

logger = logging.getLogger('sbp_fms.exceptions')


def _flatten_errors(errors):
    """Recursively formats DRF and Django validation errors into readable structures."""
    if isinstance(errors, dict):
        return {key: _flatten_errors(val) for key, val in errors.items()}
    if isinstance(errors, list):
        return [_flatten_errors(item) for item in errors]
    return str(errors)


def custom_exception_handler(exc, context):
    """
    [CUSTOM EXCEPTION HANDLER]:
    Intercepts and standardizes all API exceptions into a uniform JSON error envelope:
    {
        "success": false,
        "message": "Validation failed",
        "errors": {"field": ["This field is required."]},
        "code": "VALIDATION_ERROR",
        "detail": "Validation failed"
    }
    """
    # 1. Let DRF handle standard APIExceptions first
    response = exception_handler(exc, context)

    # 2. Handle Django-native exceptions that DRF doesn't catch by default
    if response is None:
        if isinstance(exc, DjangoValidationError):
            status_code = status.HTTP_400_BAD_REQUEST
            errors = exc.message_dict if hasattr(exc, 'message_dict') else (exc.messages if hasattr(exc, 'messages') else [str(exc)])
            message = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else "Validation failed."
            return Response({
                "success": False,
                "message": message,
                "errors": _flatten_errors(errors),
                "code": "VALIDATION_ERROR",
                "detail": message
            }, status=status_code)

        if isinstance(exc, Http404):
            return Response({
                "success": False,
                "message": "The requested resource was not found.",
                "errors": ["Not found."],
                "code": "NOT_FOUND",
                "detail": "The requested resource was not found."
            }, status=status.HTTP_404_NOT_FOUND)

        if isinstance(exc, DjangoPermissionDenied):
            return Response({
                "success": False,
                "message": "You do not have permission to perform this action.",
                "errors": ["Permission denied."],
                "code": "PERMISSION_DENIED",
                "detail": "You do not have permission to perform this action."
            }, status=status.HTTP_403_FORBIDDEN)

        if isinstance(exc, IntegrityError):
            logger.warning(f"IntegrityError encountered: {exc}", exc_info=True)
            return Response({
                "success": False,
                "message": "Database constraint violation.",
                "errors": [str(exc)],
                "code": "INTEGRITY_ERROR",
                "detail": "A database constraint violation occurred (e.g. duplicate unique key)."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Unhandled unexpected exceptions
        logger.error(f"Unhandled Exception in API view: {exc}", exc_info=True)
        return Response({
            "success": False,
            "message": "An unexpected internal server error occurred.",
            "errors": [str(exc)],
            "code": "INTERNAL_SERVER_ERROR",
            "detail": "An unexpected internal server error occurred."
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # 3. Standardize DRF Response into uniform envelope
    data = response.data
    status_code = response.status_code

    if isinstance(data, dict):
        # Extract main error message
        if 'detail' in data:
            message = str(data['detail'])
            errors = data
            code = getattr(exc, 'default_code', 'API_ERROR').upper()
        else:
            first_key = next(iter(data))
            first_val = data[first_key]
            first_msg = first_val[0] if isinstance(first_val, list) and first_val else str(first_val)
            message = f"{first_key}: {first_msg}"
            errors = data
            code = "VALIDATION_ERROR" if status_code == 400 else getattr(exc, 'default_code', 'API_ERROR').upper()
    elif isinstance(data, list):
        message = str(data[0]) if data else "An error occurred."
        errors = data
        code = getattr(exc, 'default_code', 'API_ERROR').upper()
    else:
        message = str(data)
        errors = [message]
        code = getattr(exc, 'default_code', 'API_ERROR').upper()

    response.data = {
        "success": False,
        "message": message,
        "errors": _flatten_errors(errors),
        "code": code,
        "detail": message  # Backward compatibility
    }

    return response
