from django.urls import path
from apps.taxation.api.public import TaxCalculatorPublicApi
from apps.taxation.api.admin import (
    TaxRuleListAdminApi, TaxRuleDetailAdminApi,
    VATReturnSummaryAdminApi, IndirectTaxCalculatorAdminApi,
    SSNITReturnSummaryAdminApi, SSNITScheduleGenerateAdminApi, SSNITReportExportAdminApi
)

urlpatterns = [
    # Public Tax Calculator
    path('public/calculate/', TaxCalculatorPublicApi.as_view(), name='tax-calculate-public'),

    # Admin Statutory Tax Rules & Returns
    path('admin/rules/', TaxRuleListAdminApi.as_view(), name='tax-rule-list-admin'),
    path('admin/rules/<uuid:rule_id>/', TaxRuleDetailAdminApi.as_view(), name='tax-rule-detail-admin'),
    path('admin/returns/vat-summary/', VATReturnSummaryAdminApi.as_view(), name='vat-return-summary-admin'),
    path('admin/returns/ssnit-summary/', SSNITReturnSummaryAdminApi.as_view(), name='ssnit-return-summary-admin'),
    path('admin/returns/ssnit-schedule/', SSNITScheduleGenerateAdminApi.as_view(), name='ssnit-schedule-generate-admin'),
    path('admin/returns/ssnit-export/', SSNITReportExportAdminApi.as_view(), name='ssnit-report-export-admin'),
    path('admin/calculate/indirect-tax/', IndirectTaxCalculatorAdminApi.as_view(), name='indirect-tax-calculate-admin'),
]
