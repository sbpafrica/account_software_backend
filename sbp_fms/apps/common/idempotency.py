import functools
import hashlib
import json
import logging
from datetime import timedelta
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status
from apps.common.models import IdempotencyRecord
from apps.organizations.context import get_current_organization

logger = logging.getLogger(__name__)


def idempotent_endpoint(expire_hours: int = 24):
    """
    [FINANCIAL IDEMPOTENCY DECORATOR]:
    Guarantees strict once-only execution for financial mutations (transactions, payments, approvals, vouchers).
    Inspects 'Idempotency-Key' / 'X-Idempotency-Key' HTTP headers.
    If the key was previously executed, returns the cached response replay immediately.
    If in-progress, rejects concurrent race conditions with HTTP 409 Conflict.
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapped(view_instance, request, *args, **kwargs):
            idempotency_key = (
                request.headers.get('Idempotency-Key')
                or request.headers.get('X-Idempotency-Key')
                or request.META.get('HTTP_IDEMPOTENCY_KEY')
                or request.META.get('HTTP_X_IDEMPOTENCY_KEY')
            )

            if not idempotency_key:
                # No idempotency key supplied: proceed normally
                return view_func(view_instance, request, *args, **kwargs)

            idempotency_key = idempotency_key.strip()
            if len(idempotency_key) > 255:
                return Response(
                    {'success': False, 'message': 'Idempotency key must not exceed 255 characters.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Compute request body digest
            try:
                body_bytes = request.body or b''
            except Exception:
                body_bytes = b''
            request_digest = hashlib.sha256(body_bytes).hexdigest()

            user = request.user if getattr(request, 'user', None) and request.user.is_authenticated else None
            org = getattr(request, 'organization', None) or get_current_organization()

            # Check existing record
            record = IdempotencyRecord.objects.filter(key=idempotency_key).first()

            if record:
                # Check expiration
                if record.expires_at < timezone.now():
                    record.delete()
                    record = None
                elif record.is_processing:
                    return Response(
                        {
                            'success': False,
                            'message': 'A request with this idempotency key is currently processing. Please retry shortly.',
                            'code': 'IDEMPOTENT_OPERATION_IN_PROGRESS'
                        },
                        status=status.HTTP_409_CONFLICT
                    )
                else:
                    # Return replayed cached response
                    response_headers = {
                        'X-Idempotency-Replay': 'true',
                        'X-Idempotency-Key': idempotency_key
                    }
                    return Response(
                        data=record.response_body,
                        status=record.response_status_code or status.HTTP_200_OK,
                        headers=response_headers
                    )

            # Create in-processing record
            expires_at = timezone.now() + timedelta(hours=expire_hours)
            try:
                record = IdempotencyRecord.objects.create(
                    key=idempotency_key,
                    user=user,
                    organization=org,
                    request_path=request.path,
                    request_method=request.method,
                    request_digest=request_digest,
                    is_processing=True,
                    expires_at=expires_at
                )
            except Exception:
                # Race condition: Another concurrent worker just created it
                return Response(
                    {
                        'success': False,
                        'message': 'Concurrent request detected for this idempotency key.',
                        'code': 'IDEMPOTENCY_CONFLICT'
                    },
                    status=status.HTTP_409_CONFLICT
                )

            try:
                response = view_func(view_instance, request, *args, **kwargs)
                
                # Persist completed response
                resp_data = getattr(response, 'data', None)
                record.response_status_code = response.status_code
                # Ensure data is serializable for JSONField
                try:
                    json.dumps(resp_data)
                    record.response_body = resp_data
                except Exception:
                    record.response_body = str(resp_data)
                record.is_processing = False
                record.save(update_fields=['response_status_code', 'response_body', 'is_processing', 'updated_at'])

                response['X-Idempotency-Key'] = idempotency_key
                return response

            except Exception:
                # On unexpected view crash, release the key so subsequent retries can proceed
                record.delete()
                raise

        return wrapped
    return decorator
