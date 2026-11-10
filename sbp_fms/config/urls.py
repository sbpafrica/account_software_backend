from django.urls import path, include
from django.http import JsonResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

def health_check(request):
    return JsonResponse({'status': 'ok', 'service': 'sbp-fms-api', 'version': '3.0.0'})

urlpatterns = [
    # Production Health Check
    path('health/', health_check, name='health-check'),
    path('api/health/', health_check, name='api-health-check'),

    # OpenAPI Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # SBP-FMS Domain Apps
    path('api/v1/organizations/', include('apps.organizations.api.urls')),
    path('api/v1/users/', include('apps.users.api.urls')),
    path('api/v1/ledger/', include('apps.ledger.api.urls')),
    path('api/v1/receivables/', include('apps.receivables.api.urls')),
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
