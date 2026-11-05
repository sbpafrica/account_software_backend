from django.urls import path
from apps.taxation.api.public import TaxCalculatorPublicApi
from apps.taxation.api.admin import TaxRuleListAdminApi

urlpatterns = [
    path('public/calculate/', TaxCalculatorPublicApi.as_view(), name='tax-calculate-public'),
    path('admin/rules/', TaxRuleListAdminApi.as_view(), name='tax-rule-list-admin'),
]
