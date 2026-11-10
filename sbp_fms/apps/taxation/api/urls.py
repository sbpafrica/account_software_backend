from django.urls import path
from apps.taxation.api.public import TaxCalculatorPublicApi
from apps.taxation.api.admin import TaxRuleListAdminApi, TaxRuleDetailAdminApi

urlpatterns = [
    # Public Tax Calculator
    path('public/calculate/', TaxCalculatorPublicApi.as_view(), name='tax-calculate-public'),

    # Admin Statutory Tax Rules
    path('admin/rules/', TaxRuleListAdminApi.as_view(), name='tax-rule-list-admin'),
    path('admin/rules/<uuid:rule_id>/', TaxRuleDetailAdminApi.as_view(), name='tax-rule-detail-admin'),
]
