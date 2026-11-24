from django.urls import path
from apps.invoicing.api.admin import (
    # Categories
    InvoiceCategoryListCreateAdminApi,
    InvoiceCategoryDetailAdminApi,
    InvoiceCategorySeedDefaultsAdminApi,
    # Templates Builder
    InvoiceTemplateListCreateAdminApi,
    InvoiceTemplateDetailAdminApi,
    InvoiceTemplatePresetsAdminApi,
    InvoiceTemplateApplyPresetAdminApi,
    InvoiceBuilderPreviewAdminApi,
    # Billable Items
    BillableItemListCreateAdminApi,
    BillableItemDetailAdminApi,
    # Invoices
    InvoiceListCreateAdminApi,
    InvoiceDetailAdminApi,
    InvoiceApproveAdminApi,
    InvoiceCreditNoteAdminApi,
    InvoiceVoidAdminApi,
    InvoiceRenderAdminApi,
    # Recurring
    RecurringScheduleListCreateAdminApi,
    RecurringScheduleDetailAdminApi,
    RecurringScheduleRunDueAdminApi,
)

app_name = 'invoicing'

urlpatterns = [
    # Categories Endpoints
    path('categories/', InvoiceCategoryListCreateAdminApi.as_view(), name='category_list_create'),
    path('categories/seed-defaults/', InvoiceCategorySeedDefaultsAdminApi.as_view(), name='category_seed_defaults'),
    path('categories/<uuid:category_id>/', InvoiceCategoryDetailAdminApi.as_view(), name='category_detail'),

    # Template Builder Endpoints
    path('templates/', InvoiceTemplateListCreateAdminApi.as_view(), name='template_list_create'),
    path('templates/presets/', InvoiceTemplatePresetsAdminApi.as_view(), name='template_presets'),
    path('templates/apply-preset/', InvoiceTemplateApplyPresetAdminApi.as_view(), name='template_apply_preset'),
    path('templates/preview/', InvoiceBuilderPreviewAdminApi.as_view(), name='template_preview'),
    path('templates/<uuid:template_id>/', InvoiceTemplateDetailAdminApi.as_view(), name='template_detail'),

    # Billable Catalog Items Endpoints
    path('items/', BillableItemListCreateAdminApi.as_view(), name='item_list_create'),
    path('items/<uuid:item_id>/', BillableItemDetailAdminApi.as_view(), name='item_detail'),

    # Commercial & Tax Invoices Endpoints
    path('invoices/', InvoiceListCreateAdminApi.as_view(), name='invoice_list_create'),
    path('invoices/<uuid:invoice_id>/', InvoiceDetailAdminApi.as_view(), name='invoice_detail'),
    path('invoices/<uuid:invoice_id>/approve/', InvoiceApproveAdminApi.as_view(), name='invoice_approve'),
    path('invoices/<uuid:invoice_id>/credit-note/', InvoiceCreditNoteAdminApi.as_view(), name='invoice_credit_note'),
    path('invoices/<uuid:invoice_id>/void/', InvoiceVoidAdminApi.as_view(), name='invoice_void'),
    path('invoices/<uuid:invoice_id>/render/', InvoiceRenderAdminApi.as_view(), name='invoice_render'),

    # Recurring Billing Schedules Endpoints
    path('schedules/', RecurringScheduleListCreateAdminApi.as_view(), name='schedule_list_create'),
    path('schedules/run-due/', RecurringScheduleRunDueAdminApi.as_view(), name='schedule_run_due'),
    path('schedules/<uuid:schedule_id>/', RecurringScheduleDetailAdminApi.as_view(), name='schedule_detail'),
]
