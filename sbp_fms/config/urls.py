from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from apps.common.schema_views import (
    SpectacularJSONExportView,
    SpectacularYAMLExportView,
    SpectacularDownloadView
)
from apps.organizations.api.views import PaystackWebhookPublicApi

def health_check(request):
    return JsonResponse({'status': 'ok', 'service': 'sbp-fms-api', 'version': '3.0.0'})

urlpatterns = [
    # Django Admin Portal
    path('admin/', admin.site.urls),

    # Production Health Check
    path('health/', health_check, name='health-check'),
    path('api/health/', health_check, name='api-health-check'),

    # OpenAPI Documentation & Export Formats (JSON / YAML / Download)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema.json', SpectacularJSONExportView.as_view(), name='schema-json'),
    path('api/schema.yaml', SpectacularYAMLExportView.as_view(), name='schema-yaml'),
    path('api/schema/json/', SpectacularJSONExportView.as_view(), name='schema-json-slash'),
    path('api/schema/yaml/', SpectacularYAMLExportView.as_view(), name='schema-yaml-slash'),
    path('api/schema/download/', SpectacularDownloadView.as_view(), name='schema-download'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # SBP-FMS Domain Apps
    path('api/v1/paystack/webhook/', PaystackWebhookPublicApi.as_view(), name='unified-paystack-webhook'),
    path('api/v1/organizations/', include('apps.organizations.api.urls')),
    path('api/v1/users/', include('apps.users.api.urls')),
    path('api/v1/ledger/', include('apps.ledger.api.urls')),
    path('api/v1/receivables/', include('apps.receivables.api.urls')),
    path('api/v1/invoicing/', include('apps.invoicing.api.urls')),
    path('api/v1/payables/', include('apps.payables.api.urls')),
    path('api/v1/payroll-escrow/', include('apps.payroll_escrow.api.urls')),
    path('api/v1/treasury/', include('apps.treasury.api.urls')),
    path('api/v1/taxation/', include('apps.taxation.api.urls')),
    path('api/v1/assets/', include('apps.assets.api.urls')),
    path('api/v1/common/', include('apps.common.api.urls')),
    path('api/v1/consolidation/', include('apps.consolidation.api.urls')),
    path('api/v1/budgeting/', include('apps.budgeting.api.urls')),
    path('api/v1/contracts/', include('apps.contracts.api.urls')),
]
