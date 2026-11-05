from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class CustomPageNumberPagination(PageNumberPagination):
    """
    [CUSTOM PAGINATION]:
    Standard enterprise pagination envelope for SBP-FMS.
    Wraps results in a uniform metadata structure:
    {
        "success": true,
        "message": "Data retrieved successfully.",
        "pagination": {
            "count": 120,
            "total_pages": 3,
            "current_page": 1,
            "page_size": 50,
            "next": "...",
            "previous": null
        },
        "data": [...]
    }
    """
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200
    page_query_param = 'page'

    def get_paginated_response(self, data):
        return Response({
            'success': True,
            'message': 'Data retrieved successfully.',
            'pagination': {
                'count': self.page.paginator.count,
                'total_pages': self.page.paginator.num_pages,
                'current_page': self.page.number,
                'page_size': self.get_page_size(self.request),
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
            },
            'data': data
        })

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean', 'example': True},
                'message': {'type': 'string', 'example': 'Data retrieved successfully.'},
                'pagination': {
                    'type': 'object',
                    'properties': {
                        'count': {'type': 'integer', 'example': 100},
                        'total_pages': {'type': 'integer', 'example': 2},
                        'current_page': {'type': 'integer', 'example': 1},
                        'page_size': {'type': 'integer', 'example': 50},
                        'next': {'type': 'string', 'nullable': True},
                        'previous': {'type': 'string', 'nullable': True},
                    }
                },
                'data': schema
            }
        }


def paginate_queryset(queryset, request, serializer_class, pagination_class=CustomPageNumberPagination):
    """
    Helper function to paginate any queryset or list using a serializer.
    """
    paginator = pagination_class()
    page = paginator.paginate_queryset(queryset, request)
    if page is not None:
        serializer = serializer_class(page, many=True)
        return paginator.get_paginated_response(serializer.data)
    serializer = serializer_class(queryset, many=True)
    return Response({
        'success': True,
        'message': 'Data retrieved successfully.',
        'data': serializer.data
    })
