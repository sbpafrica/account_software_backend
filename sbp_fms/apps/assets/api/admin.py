from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import exceptions, status
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.pagination import CustomPageNumberPagination, paginate_queryset
from apps.common.responses import api_success
from apps.users.permissions import HasPermissionCode, CountryScopedAccess
from apps.assets.selectors import (
    asset_category_list, asset_category_detail,
    fixed_asset_list, fixed_asset_detail,
    depreciation_run_list, depreciation_run_detail,
    fixed_asset_schedule_get, asset_register_summary_get
)
from apps.assets.services import AssetsService
from apps.assets.serializers import (
    AssetCategoryOutputSerializer, AssetCategoryCreateInputSerializer, AssetCategoryUpdateInputSerializer,
    FixedAssetOutputSerializer, FixedAssetCreateInputSerializer, FixedAssetUpdateInputSerializer,
    FixedAssetDisposeInputSerializer, DepreciationRunOutputSerializer,
    DepreciationRunCalculateInputSerializer, DepreciationScheduleLineOutputSerializer,
    AssetRegisterSummaryOutputSerializer
)


# ============================================================================
# 1. ASSET CATEGORIES
# ============================================================================

class AssetCategoryListCreateAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]

    @extend_schema(
        tags=['Fixed Assets - Categories'],
        operation_id='admin_assets_category_list',
        summary='List asset categories',
        responses={status.HTTP_200_OK: AssetCategoryOutputSerializer(many=True)}
    )
    def get(self, request):
        categories = asset_category_list(country_code=request.query_params.get('country'))
        return api_success(data=AssetCategoryOutputSerializer(categories, many=True).data)

    @extend_schema(
        tags=['Fixed Assets - Categories'],
        operation_id='admin_assets_category_create',
        summary='Create asset category',
        request=AssetCategoryCreateInputSerializer,
        responses={status.HTTP_201_CREATED: AssetCategoryOutputSerializer}
    )
    def post(self, request):
        if not request.user.has_permission_code('ledger:write'):
            raise exceptions.PermissionDenied('Permission denied: ledger:write required')
        serializer = AssetCategoryCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            cat = AssetsService.asset_category_create(**serializer.validated_data)
            return api_success(
                data=AssetCategoryOutputSerializer(cat).data,
                message="Asset category created successfully.",
                status_code=status.HTTP_201_CREATED
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class AssetCategoryDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]

    @extend_schema(
        tags=['Fixed Assets - Categories'],
        operation_id='admin_assets_category_detail',
        summary='Retrieve asset category details',
        description='Fetch configuration details, useful life, depreciation method, and linked GL accounts for a specific asset category by UUID.',
        responses={status.HTTP_200_OK: AssetCategoryOutputSerializer}
    )
    def get(self, request, category_id):
        cat = asset_category_detail(category_id=category_id)
        return api_success(data=AssetCategoryOutputSerializer(cat).data)

    @extend_schema(
        tags=['Fixed Assets - Categories'],
        operation_id='admin_assets_category_update',
        summary='Update asset category',
        description='Update asset category attributes, useful life, depreciation method, or linked GL accounts.',
        request=AssetCategoryUpdateInputSerializer,
        responses={status.HTTP_200_OK: AssetCategoryOutputSerializer}
    )
    def put(self, request, category_id):
        if not request.user.has_permission_code('ledger:write'):
            raise exceptions.PermissionDenied('Permission denied: ledger:write required')
        serializer = AssetCategoryUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            cat = AssetsService.asset_category_update(category_id=category_id, **serializer.validated_data)
            return api_success(data=AssetCategoryOutputSerializer(cat).data, message="Asset category updated successfully.")
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})

    @extend_schema(
        tags=['Fixed Assets - Categories'],
        operation_id='admin_assets_category_partial_update',
        summary='Partially update asset category',
        description='Partially update specific fields of an existing asset category.',
        request=AssetCategoryUpdateInputSerializer,
        responses={status.HTTP_200_OK: AssetCategoryOutputSerializer}
    )
    def patch(self, request, category_id):
        return self.put(request, category_id)


# ============================================================================
# 2. FIXED ASSET REGISTER
# ============================================================================

class FixedAssetListCreateAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Fixed Assets - Register'],
        operation_id='admin_assets_list',
        summary='List registered fixed assets',
        parameters=[
            OpenApiParameter(name='category_id', description='Filter by category UUID', required=False, type=str),
            OpenApiParameter(name='status', description='Filter by status (ACTIVE/DISPOSED/FULLY_DEPRECIATED)', required=False, type=str),
            OpenApiParameter(name='department', description='Filter by department', required=False, type=str),
        ],
        responses={status.HTTP_200_OK: FixedAssetOutputSerializer(many=True)}
    )
    def get(self, request):
        assets = fixed_asset_list(
            category_id=request.query_params.get('category_id'),
            status=request.query_params.get('status'),
            department=request.query_params.get('department'),
            country_code=request.query_params.get('country')
        )
        return paginate_queryset(assets, request, FixedAssetOutputSerializer)

    @extend_schema(
        tags=['Fixed Assets - Register'],
        operation_id='admin_assets_create',
        summary='Register new fixed asset in register',
        request=FixedAssetCreateInputSerializer,
        responses={status.HTTP_201_CREATED: FixedAssetOutputSerializer}
    )
    def post(self, request):
        if not request.user.has_permission_code('ledger:write'):
            raise exceptions.PermissionDenied('Permission denied: ledger:write required')
        serializer = FixedAssetCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            asset = AssetsService.fixed_asset_create(**serializer.validated_data)
            return api_success(
                data=FixedAssetOutputSerializer(asset).data,
                message="Fixed asset registered successfully.",
                status_code=status.HTTP_201_CREATED
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class FixedAssetDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]

    @extend_schema(
        tags=['Fixed Assets - Register'],
        operation_id='admin_assets_detail',
        summary='Retrieve fixed asset details',
        description='Retrieve comprehensive fixed asset details, acquisition cost, accumulated depreciation, net book value, and lifecycle status.',
        responses={status.HTTP_200_OK: FixedAssetOutputSerializer}
    )
    def get(self, request, asset_id):
        asset = fixed_asset_detail(asset_id=asset_id)
        return api_success(data=FixedAssetOutputSerializer(asset).data)


class FixedAssetScheduleAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]

    @extend_schema(
        tags=['Fixed Assets - Register'],
        operation_id='admin_assets_schedule',
        summary='Retrieve depreciation schedule lines for an asset',
        responses={status.HTTP_200_OK: DepreciationScheduleLineOutputSerializer(many=True)}
    )
    def get(self, request, asset_id):
        lines = fixed_asset_schedule_get(asset_id=asset_id)
        return api_success(data=DepreciationScheduleLineOutputSerializer(lines, many=True).data)


class FixedAssetDisposeAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:write')()]

    @extend_schema(
        tags=['Fixed Assets - Register'],
        operation_id='admin_assets_dispose',
        summary='Dispose / Sell / Derecognize fixed asset and post GL entries',
        request=FixedAssetDisposeInputSerializer,
        responses={status.HTTP_200_OK: FixedAssetOutputSerializer}
    )
    def post(self, request, asset_id):
        serializer = FixedAssetDisposeInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            asset = AssetsService.fixed_asset_dispose(
                asset_id=asset_id,
                user=request.user,
                **serializer.validated_data
            )
            return api_success(
                data=FixedAssetOutputSerializer(asset).data,
                message=f"Fixed asset {asset.asset_tag} disposed successfully. Gain/Loss: {asset.disposal_gain_loss}"
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


# ============================================================================
# 3. DEPRECIATION RUNS
# ============================================================================

class DepreciationRunListCalculateAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Fixed Assets - Depreciation'],
        operation_id='admin_assets_depreciation_run_list',
        summary='List depreciation runs',
        responses={status.HTTP_200_OK: DepreciationRunOutputSerializer(many=True)}
    )
    def get(self, request):
        runs = depreciation_run_list()
        return paginate_queryset(runs, request, DepreciationRunOutputSerializer)

    @extend_schema(
        tags=['Fixed Assets - Depreciation'],
        operation_id='admin_assets_depreciation_run_calculate',
        summary='Calculate draft depreciation run for period',
        request=DepreciationRunCalculateInputSerializer,
        responses={status.HTTP_201_CREATED: DepreciationRunOutputSerializer}
    )
    def post(self, request):
        if not request.user.has_permission_code('ledger:write'):
            raise exceptions.PermissionDenied('Permission denied: ledger:write required')
        serializer = DepreciationRunCalculateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            run = AssetsService.depreciation_run_calculate(
                period_end_date=serializer.validated_data['period_end_date'],
                user=request.user
            )
            return api_success(
                data=DepreciationRunOutputSerializer(run).data,
                message=f"Depreciation run {run.run_number} calculated: {run.total_assets_processed} assets processed, total: {run.total_depreciation}.",
                status_code=status.HTTP_201_CREATED
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


class DepreciationRunDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]

    @extend_schema(
        tags=['Fixed Assets - Depreciation'],
        operation_id='admin_assets_depreciation_run_detail',
        summary='Retrieve depreciation run details',
        description='Retrieve calculation summary, asset count, total depreciation computed, and GL posting status of a depreciation run.',
        responses={status.HTTP_200_OK: DepreciationRunOutputSerializer}
    )
    def get(self, request, run_id):
        run = depreciation_run_detail(run_id=run_id)
        return api_success(data=DepreciationRunOutputSerializer(run).data)


class DepreciationRunPostAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:write')()]

    @extend_schema(
        tags=['Fixed Assets - Depreciation'],
        operation_id='admin_assets_depreciation_run_post',
        summary='Post depreciation run to General Ledger (DR Expense, CR Accumulated Depr)',
        description='Post an approved draft depreciation run to General Ledger, generating balanced double-entry journal lines across asset categories.',
        request=None,
        responses={status.HTTP_200_OK: DepreciationRunOutputSerializer}
    )
    def post(self, request, run_id):
        try:
            run = AssetsService.depreciation_run_post(depreciation_run_id=run_id, user=request.user)
            return api_success(
                data=DepreciationRunOutputSerializer(run).data,
                message=f"Depreciation run {run.run_number} posted to GL successfully."
            )
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, 'messages') and exc.messages else str(exc)
            raise exceptions.ValidationError({'detail': msg})


# ============================================================================
# 4. ASSET REGISTER SUMMARY
# ============================================================================

class AssetRegisterSummaryAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('ledger:read')()]

    @extend_schema(
        tags=['Fixed Assets - Summary'],
        operation_id='admin_assets_summary',
        summary='Retrieve Asset Register financial summary metrics',
        responses={status.HTTP_200_OK: AssetRegisterSummaryOutputSerializer}
    )
    def get(self, request):
        summary = asset_register_summary_get(country_code=request.query_params.get('country'))
        return api_success(data=summary, message="Asset register summary retrieved successfully.")
