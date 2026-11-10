from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, OpenApiParameter
from apps.common.pagination import CustomPageNumberPagination, paginate_queryset
from apps.ledger.selectors import account_list
from apps.ledger.serializers import AccountOutputSerializer


class AccountListPublicApi(APIView):
    """
    [PUBLIC API]: Read-only active chart of accounts list for dropdowns and external integrations.
    """
    permission_classes = [AllowAny]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Ledger - Public'],
        operation_id='public_ledger_account_list',
        summary='List active chart of accounts',
        description='Read-only active chart of accounts list for dropdowns and external integrations.',
        parameters=[
            OpenApiParameter(name='country', description='Two-letter country code filter (e.g. GH, CI)', required=False, type=str)
        ],
        responses={
            status.HTTP_200_OK: AccountOutputSerializer(many=True),
        }
    )
    def get(self, request):
        country = request.query_params.get('country')
        accounts = account_list(country_code=country, is_active=True)
        return paginate_queryset(accounts, request, AccountOutputSerializer)

