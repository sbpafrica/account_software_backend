from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    # OpenAPI Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # SBP-FMS Domain Apps
    path('api/v1/users/', include('apps.users.api.urls')),
    path('api/v1/ledger/', include('apps.ledger.api.urls')),
    path('api/v1/receivables/', include('apps.receivables.api.urls')),
    path('api/v1/payables/', include('apps.payables.api.urls')),
    path('api/v1/payroll-escrow/', include('apps.payroll_escrow.api.urls')),
    path('api/v1/treasury/', include('apps.treasury.api.urls')),
    path('api/v1/taxation/', include('apps.taxation.api.urls')),
]
