from typing import Any, Optional
from django.db.models import QuerySet


def apply_dict_filters(
    queryset: QuerySet,
    filters: Optional[dict[str, Any]] = None,
    allowed_fields: Optional[list[str]] = None
) -> QuerySet:
    """
    [DICTIONARY QUERYSET FILTER]:
    Applies dynamic filtering to a Django QuerySet using a Python dictionary.

    Features:
    - Filters out None and empty string values automatically.
    - Supports exact fields and Django lookup expressions ('created_at__gte', 'role__name', 'status__in').
    - Optionally restricts keys against a list of allowed fields.
    """
    if not filters:
        return queryset

    cleaned_filters = {}
    for key, value in filters.items():
        if value is None or value == '':
            continue

        if allowed_fields is not None:
            base_field = key.split('__')[0]
            if base_field not in allowed_fields and key not in allowed_fields:
                continue

        cleaned_filters[key] = value

    if cleaned_filters:
        return queryset.filter(**cleaned_filters)
    return queryset


def merge_filters(filters: Optional[dict[str, Any]] = None, **kwargs) -> dict[str, Any]:
    """
    Combines a Python filter dictionary with optional keyword arguments.
    Eliminates None and empty strings.
    """
    merged = {}
    for k, v in kwargs.items():
        if v is not None and v != '':
            merged[k] = v

    if filters:
        for k, v in filters.items():
            if v is not None and v != '':
                merged[k] = v

    return merged
