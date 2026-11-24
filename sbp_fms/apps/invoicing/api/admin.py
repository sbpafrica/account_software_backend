from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.responses import api_success
from apps.common.pagination import CustomPageNumberPagination, paginate_queryset
from apps.users.permissions import HasPermissionCode
from apps.invoicing.selectors import InvoicingSelector
from apps.invoicing.services import InvoicingService
from apps.invoicing.serializers import (
    InvoiceCategorySerializer,
    InvoiceTemplateSerializer,
    TemplatePresetSerializer,
    BillableItemSerializer,
    InvoiceListSerializer,
    InvoiceDetailSerializer,
    InvoiceCreateSerializer,
    CreditNoteCreateSerializer,
    InvoiceVoidSerializer,
    ApplyPresetSerializer,
    InvoicingBuilderPreviewInputSerializer,
    RecurringScheduleSerializer,
)


class BaseInvoicingAdminApi(APIView):
    permission_classes = [IsAuthenticated]


# -----------------------------------------------------------------------------
# CATEGORY APIS (Dynamic Admin Managed)
# -----------------------------------------------------------------------------
class InvoiceCategoryListCreateAdminApi(BaseInvoicingAdminApi):
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Invoicing - Categories'],
        operation_id='admin_invoicing_category_list',
        summary='List invoice categories',
        description='Returns dynamic, admin-configurable business categories (e.g. Workforce Outsourcing, Payroll Administration).',
        parameters=[
            OpenApiParameter(name='is_active', description='Filter by active status', required=False, type=bool),
            OpenApiParameter(name='search', description='Search by name or code', required=False, type=str),
        ],
        responses={status.HTTP_200_OK: InvoiceCategorySerializer(many=True)},
    )
    def get(self, request):
        is_active_param = request.query_params.get('is_active')
        is_active = is_active_param.lower() == 'true' if is_active_param is not None else None
        search = request.query_params.get('search')

        categories = InvoicingSelector.invoice_category_list(is_active=is_active, search=search)
        return paginate_queryset(categories, request, InvoiceCategorySerializer)

    @extend_schema(
        tags=['Invoicing - Categories'],
        operation_id='admin_invoicing_category_create',
        summary='Create new invoice category',
        description='Allows admins to create new business vertical categories on the fly.',
        request=InvoiceCategorySerializer,
        responses={status.HTTP_201_CREATED: InvoiceCategorySerializer},
    )
    def post(self, request):
        serializer = InvoiceCategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        category = InvoicingService.invoice_category_create(
            name=data['name'],
            code=data['code'],
            description=data.get('description', ''),
            income_account_id=data.get('income_account_id'),
            is_active=data.get('is_active', True),
        )
        return api_success(
            data=InvoiceCategorySerializer(category).data,
            message="Invoice category created successfully.",
            status_code=status.HTTP_201_CREATED
        )


class InvoiceCategoryDetailAdminApi(BaseInvoicingAdminApi):
    @extend_schema(
        tags=['Invoicing - Categories'],
        operation_id='admin_invoicing_category_detail',
        summary='Retrieve invoice category detail',
        responses={status.HTTP_200_OK: InvoiceCategorySerializer},
    )
    def get(self, request, category_id):
        category = InvoicingSelector.invoice_category_detail(category_id=category_id)
        return api_success(data=InvoiceCategorySerializer(category).data)

    @extend_schema(
        tags=['Invoicing - Categories'],
        operation_id='admin_invoicing_category_update',
        summary='Update invoice category',
        request=InvoiceCategorySerializer,
        responses={status.HTTP_200_OK: InvoiceCategorySerializer},
    )
    def patch(self, request, category_id):
        serializer = InvoiceCategorySerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        category = InvoicingService.invoice_category_update(
            category_id=category_id,
            **serializer.validated_data
        )
        return api_success(
            data=InvoiceCategorySerializer(category).data,
            message="Invoice category updated successfully."
        )

    @extend_schema(
        tags=['Invoicing - Categories'],
        operation_id='admin_invoicing_category_delete',
        summary='Delete invoice category',
        responses={status.HTTP_200_OK: dict},
    )
    def delete(self, request, category_id):
        InvoicingService.invoice_category_delete(category_id=category_id)
        return api_success(message="Invoice category deleted successfully.")


class InvoiceCategorySeedDefaultsAdminApi(BaseInvoicingAdminApi):
    @extend_schema(
        tags=['Invoicing - Categories'],
        operation_id='admin_invoicing_category_seed_defaults',
        summary='Seed default SBP business categories',
        description='Populates initial default categories (Workforce Outsourcing, Payroll Administration, Recruitment, Management Consulting, Camp Logistics) if missing.',
        request=None,
        responses={status.HTTP_200_OK: InvoiceCategorySerializer(many=True)},
    )
    def post(self, request):
        categories = InvoicingService.invoice_category_seed_defaults()
        return api_success(
            data=InvoiceCategorySerializer(categories, many=True).data,
            message=f"Seeded {len(categories)} default invoice categories."
        )


# -----------------------------------------------------------------------------
# TEMPLATE APIS (Builder Engine)
# -----------------------------------------------------------------------------
class InvoiceTemplateListCreateAdminApi(BaseInvoicingAdminApi):
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Invoicing - Templates Builder'],
        operation_id='admin_invoicing_template_list',
        summary='List invoice templates',
        parameters=[
            OpenApiParameter(name='client_id', description='Filter by client ID (or global)', required=False, type=str),
            OpenApiParameter(name='is_active', description='Filter by active status', required=False, type=bool),
        ],
        responses={status.HTTP_200_OK: InvoiceTemplateSerializer(many=True)},
    )
    def get(self, request):
        client_id = request.query_params.get('client_id')
        is_active_param = request.query_params.get('is_active')
        is_active = is_active_param.lower() == 'true' if is_active_param is not None else None

        templates = InvoicingSelector.invoice_template_list(client_id=client_id, is_active=is_active)
        return paginate_queryset(templates, request, InvoiceTemplateSerializer)

    @extend_schema(
        tags=['Invoicing - Templates Builder'],
        operation_id='admin_invoicing_template_create',
        summary='Create invoice template',
        request=InvoiceTemplateSerializer,
        responses={status.HTTP_201_CREATED: InvoiceTemplateSerializer},
    )
    def post(self, request):
        serializer = InvoiceTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        template = InvoicingService.invoice_template_create(
            template_name=data['template_name'],
            layout_style=data.get('layout_style', 'MODERN'),
            client_id=data.get('client_id'),
            preset_code=data.get('preset_code', ''),
            primary_color=data.get('primary_color', '#102a43'),
            secondary_color=data.get('secondary_color', '#243b53'),
            accent_color=data.get('accent_color', '#0ea5e9'),
            logo_url=data.get('logo_url', ''),
            show_logo=data.get('show_logo', True),
            font_family=data.get('font_family', 'Inter, sans-serif'),
            invoice_title=data.get('invoice_title', 'TAX INVOICE'),
            show_tax_breakdown=data.get('show_tax_breakdown', True),
            show_bank_details=data.get('show_bank_details', True),
            show_due_date_badge=data.get('show_due_date_badge', True),
            show_discount=data.get('show_discount', True),
            show_unit_of_measure=data.get('show_unit_of_measure', True),
            default_notes=data.get('default_notes', ''),
            default_terms=data.get('default_terms', ''),
            footer_text=data.get('footer_text', ''),
            header_custom_fields=data.get('header_custom_fields', []),
            line_custom_fields=data.get('line_custom_fields', []),
            is_default=data.get('is_default', False),
        )
        return api_success(
            data=InvoiceTemplateSerializer(template).data,
            message="Invoice template created successfully.",
            status_code=status.HTTP_201_CREATED
        )


class InvoiceTemplateDetailAdminApi(BaseInvoicingAdminApi):
    @extend_schema(
        tags=['Invoicing - Templates Builder'],
        operation_id='admin_invoicing_template_detail',
        summary='Retrieve invoice template',
        responses={status.HTTP_200_OK: InvoiceTemplateSerializer},
    )
    def get(self, request, template_id):
        template = InvoicingSelector.invoice_template_detail(template_id=template_id)
        return api_success(data=InvoiceTemplateSerializer(template).data)

    @extend_schema(
        tags=['Invoicing - Templates Builder'],
        operation_id='admin_invoicing_template_update',
        summary='Update invoice template',
        request=InvoiceTemplateSerializer,
        responses={status.HTTP_200_OK: InvoiceTemplateSerializer},
    )
    def patch(self, request, template_id):
        serializer = InvoiceTemplateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        template = InvoicingService.invoice_template_update(
            template_id=template_id,
            **serializer.validated_data
        )
        return api_success(
            data=InvoiceTemplateSerializer(template).data,
            message="Invoice template updated successfully."
        )

    @extend_schema(
        tags=['Invoicing - Templates Builder'],
        operation_id='admin_invoicing_template_delete',
        summary='Delete invoice template',
        responses={status.HTTP_200_OK: dict},
    )
    def delete(self, request, template_id):
        InvoicingService.invoice_template_delete(template_id=template_id)
        return api_success(message="Invoice template deleted successfully.")


class InvoiceTemplatePresetsAdminApi(BaseInvoicingAdminApi):
    @extend_schema(
        tags=['Invoicing - Templates Builder'],
        operation_id='admin_invoicing_template_presets',
        summary='List industry template presets',
        description='Returns pre-built presets for Staffing & Workforce, Corporate Standard, Recruitment Placements, and Management Consulting.',
        responses={status.HTTP_200_OK: TemplatePresetSerializer(many=True)},
    )
    def get(self, request):
        presets = InvoicingSelector.invoice_template_presets_list()
        return api_success(data=presets)


class InvoiceTemplateApplyPresetAdminApi(BaseInvoicingAdminApi):
    @extend_schema(
        tags=['Invoicing - Templates Builder'],
        operation_id='admin_invoicing_template_apply_preset',
        summary='Apply industry preset into a new template',
        request=ApplyPresetSerializer,
        responses={status.HTTP_201_CREATED: InvoiceTemplateSerializer},
    )
    def post(self, request):
        serializer = ApplyPresetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        template = InvoicingService.invoice_template_apply_preset(
            preset_code=data['preset_code'],
            client_id=str(data['client_id']) if data.get('client_id') else None,
            template_name=data.get('template_name'),
            make_default=data.get('make_default', False),
        )
        return api_success(
            data=InvoiceTemplateSerializer(template).data,
            message=f"Preset '{data['preset_code']}' applied successfully.",
            status_code=status.HTTP_201_CREATED
        )


class InvoiceBuilderPreviewAdminApi(BaseInvoicingAdminApi):
    @extend_schema(
        tags=['Invoicing - Templates Builder'],
        operation_id='admin_invoicing_builder_preview',
        summary='Simulated live invoice builder canvas preview',
        request=InvoicingBuilderPreviewInputSerializer,
        responses={status.HTTP_200_OK: dict},
    )
    def post(self, request):
        serializer = InvoicingBuilderPreviewInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        preview = InvoicingSelector.invoice_builder_preview_data(
            template_data=data['template_data'],
            sample_invoice=data.get('sample_invoice')
        )
        return api_success(data=preview)


# -----------------------------------------------------------------------------
# BILLABLE ITEM CATALOG APIS
# -----------------------------------------------------------------------------
class BillableItemListCreateAdminApi(BaseInvoicingAdminApi):
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Invoicing - Billable Items'],
        operation_id='admin_invoicing_item_list',
        summary='List catalog services and billable items',
        parameters=[
            OpenApiParameter(name='category_id', description='Filter by category ID', required=False, type=str),
            OpenApiParameter(name='is_active', description='Filter by active status', required=False, type=bool),
            OpenApiParameter(name='search', description='Search by code or name', required=False, type=str),
        ],
        responses={status.HTTP_200_OK: BillableItemSerializer(many=True)},
    )
    def get(self, request):
        category_id = request.query_params.get('category_id')
        is_active_param = request.query_params.get('is_active')
        is_active = is_active_param.lower() == 'true' if is_active_param is not None else None
        search = request.query_params.get('search')

        items = InvoicingSelector.billable_item_list(
            category_id=category_id,
            is_active=is_active,
            search=search
        )
        return paginate_queryset(items, request, BillableItemSerializer)

    @extend_schema(
        tags=['Invoicing - Billable Items'],
        operation_id='admin_invoicing_item_create',
        summary='Create billable catalog item',
        request=BillableItemSerializer,
        responses={status.HTTP_201_CREATED: BillableItemSerializer},
    )
    def post(self, request):
        serializer = BillableItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        item = InvoicingService.billable_item_create(
            code=data['code'],
            name=data['name'],
            category_id=data.get('category_id'),
            description=data.get('description', ''),
            default_unit=data.get('default_unit', 'Unit'),
            default_unit_price=data.get('default_unit_price', 0.0),
            default_tax_code=data.get('default_tax_code', 'VAT_STANDARD'),
            default_tax_rate=data.get('default_tax_rate', 0.15),
            income_account_id=data.get('income_account_id'),
            is_active=data.get('is_active', True),
        )
        return api_success(
            data=BillableItemSerializer(item).data,
            message="Billable item created successfully.",
            status_code=status.HTTP_201_CREATED
        )


class BillableItemDetailAdminApi(BaseInvoicingAdminApi):
    @extend_schema(
        tags=['Invoicing - Billable Items'],
        operation_id='admin_invoicing_item_detail',
        summary='Retrieve billable item detail',
        responses={status.HTTP_200_OK: BillableItemSerializer},
    )
    def get(self, request, item_id):
        item = InvoicingSelector.billable_item_detail(item_id=item_id)
        return api_success(data=BillableItemSerializer(item).data)

    @extend_schema(
        tags=['Invoicing - Billable Items'],
        operation_id='admin_invoicing_item_update',
        summary='Update billable item',
        request=BillableItemSerializer,
        responses={status.HTTP_200_OK: BillableItemSerializer},
    )
    def patch(self, request, item_id):
        serializer = BillableItemSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        item = InvoicingService.billable_item_update(
            item_id=item_id,
            **serializer.validated_data
        )
        return api_success(
            data=BillableItemSerializer(item).data,
            message="Billable item updated successfully."
        )

    @extend_schema(
        tags=['Invoicing - Billable Items'],
        operation_id='admin_invoicing_item_delete',
        summary='Delete billable item',
        responses={status.HTTP_200_OK: dict},
    )
    def delete(self, request, item_id):
        InvoicingService.billable_item_delete(item_id=item_id)
        return api_success(message="Billable item deleted successfully.")


# -----------------------------------------------------------------------------
# INVOICE CORE APIS
# -----------------------------------------------------------------------------
class InvoiceListCreateAdminApi(BaseInvoicingAdminApi):
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Invoicing - Invoices'],
        operation_id='admin_invoicing_invoice_list',
        summary='List customer commercial & tax invoices',
        parameters=[
            OpenApiParameter(name='client_id', description='Filter by client ID', required=False, type=str),
            OpenApiParameter(name='category_id', description='Filter by business category ID', required=False, type=str),
            OpenApiParameter(name='status', description='Filter by invoice status', required=False, type=str),
            OpenApiParameter(name='invoice_type', description='Filter by invoice type', required=False, type=str),
            OpenApiParameter(name='start_date', description='Filter by issue_date >= start_date', required=False, type=str),
            OpenApiParameter(name='end_date', description='Filter by issue_date <= end_date', required=False, type=str),
            OpenApiParameter(name='search', description='Search invoice #, PO, description, client', required=False, type=str),
        ],
        responses={status.HTTP_200_OK: InvoiceListSerializer(many=True)},
    )
    def get(self, request):
        invoices = InvoicingSelector.invoice_list(
            client_id=request.query_params.get('client_id'),
            category_id=request.query_params.get('category_id'),
            status=request.query_params.get('status'),
            invoice_type=request.query_params.get('invoice_type'),
            start_date=request.query_params.get('start_date'),
            end_date=request.query_params.get('end_date'),
            search=request.query_params.get('search'),
        )
        return paginate_queryset(invoices, request, InvoiceListSerializer)

    @extend_schema(
        tags=['Invoicing - Invoices'],
        operation_id='admin_invoicing_invoice_create',
        summary='Create new customer invoice',
        description='Creates a commercial or tax invoice with dynamic custom header fields, custom line columns, and Ghana GRA tax cascading calculations.',
        request=InvoiceCreateSerializer,
        responses={status.HTTP_201_CREATED: InvoiceDetailSerializer},
    )
    def post(self, request):
        serializer = InvoiceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        invoice = InvoicingService.invoice_create(
            client_id=str(data['client_id']),
            issue_date=data['issue_date'],
            due_date=data['due_date'],
            invoice_type=data.get('invoice_type', 'STANDARD'),
            category_id=str(data['category_id']) if data.get('category_id') else None,
            description=data.get('description', ''),
            template_id=str(data['template_id']) if data.get('template_id') else None,
            currency=data.get('currency', 'GHS'),
            exchange_rate=data.get('exchange_rate', 1.0),
            billing_period_start=data.get('billing_period_start'),
            billing_period_end=data.get('billing_period_end'),
            reference_number=data.get('reference_number', ''),
            invoice_number=data.get('invoice_number'),
            lines=data['lines'],
            custom_fields=data.get('custom_fields', {}),
            notes=data.get('notes', ''),
            terms_and_conditions=data.get('terms_and_conditions', ''),
            footer_text=data.get('footer_text', ''),
            auto_calculate_tax=data.get('auto_calculate_tax', True),
            user=request.user,
        )
        return api_success(
            data=InvoiceDetailSerializer(invoice).data,
            message="Invoice created successfully.",
            status_code=status.HTTP_201_CREATED
        )


class InvoiceDetailAdminApi(BaseInvoicingAdminApi):
    @extend_schema(
        tags=['Invoicing - Invoices'],
        operation_id='admin_invoicing_invoice_detail',
        summary='Retrieve invoice detail',
        responses={status.HTTP_200_OK: InvoiceDetailSerializer},
    )
    def get(self, request, invoice_id):
        invoice = InvoicingSelector.invoice_detail(invoice_id=invoice_id)
        return api_success(data=InvoiceDetailSerializer(invoice).data)

    @extend_schema(
        tags=['Invoicing - Invoices'],
        operation_id='admin_invoicing_invoice_update',
        summary='Update draft invoice metadata',
        request=InvoiceDetailSerializer,
        responses={status.HTTP_200_OK: InvoiceDetailSerializer},
    )
    def patch(self, request, invoice_id):
        invoice = InvoicingService.invoice_update(invoice_id=invoice_id, **request.data)
        return api_success(
            data=InvoiceDetailSerializer(invoice).data,
            message="Invoice updated successfully."
        )


class InvoiceApproveAdminApi(BaseInvoicingAdminApi):
    @extend_schema(
        tags=['Invoicing - Invoices'],
        operation_id='admin_invoicing_invoice_approve',
        summary='Approve and issue invoice (posts to General Ledger)',
        description='Moves invoice status to ISSUED, debits Accounts Receivable (1100-AR-GH), credits Revenue (4010-REVENUE-GH), and credits Indirect Tax Payable (2020-TAX-PAYABLE-GH).',
        request=None,
        responses={status.HTTP_200_OK: InvoiceDetailSerializer},
    )
    def post(self, request, invoice_id):
        invoice = InvoicingService.invoice_approve(invoice_id=invoice_id, user=request.user)
        return api_success(
            data=InvoiceDetailSerializer(invoice).data,
            message=f"Invoice {invoice.invoice_number} approved and posted to General Ledger."
        )


class InvoiceCreditNoteAdminApi(BaseInvoicingAdminApi):
    @extend_schema(
        tags=['Invoicing - Invoices'],
        operation_id='admin_invoicing_invoice_credit_note',
        summary='Issue credit note against invoice',
        description='Creates an adjusting credit note, points parent_invoice to original, and posts reversal journal entry to GL.',
        request=CreditNoteCreateSerializer,
        responses={status.HTTP_201_CREATED: InvoiceDetailSerializer},
    )
    def post(self, request, invoice_id):
        serializer = CreditNoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cn = InvoicingService.invoice_issue_credit_note(
            invoice_id=invoice_id,
            reason=data['reason'],
            credit_amount=data.get('credit_amount'),
            user=request.user
        )
        return api_success(
            data=InvoiceDetailSerializer(cn).data,
            message=f"Credit note {cn.invoice_number} issued successfully.",
            status_code=status.HTTP_201_CREATED
        )


class InvoiceVoidAdminApi(BaseInvoicingAdminApi):
    @extend_schema(
        tags=['Invoicing - Invoices'],
        operation_id='admin_invoicing_invoice_void',
        summary='Void an invoice',
        description='Voids an issued or draft invoice. If GL journal entries were posted, automatically performs accounting reversal.',
        request=InvoiceVoidSerializer,
        responses={status.HTTP_200_OK: InvoiceDetailSerializer},
    )
    def post(self, request, invoice_id):
        serializer = InvoiceVoidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        invoice = InvoicingService.invoice_void(
            invoice_id=invoice_id,
            reason=serializer.validated_data['reason'],
            user=request.user
        )
        return api_success(
            data=InvoiceDetailSerializer(invoice).data,
            message=f"Invoice {invoice.invoice_number} voided successfully."
        )


class InvoiceRenderAdminApi(BaseInvoicingAdminApi):
    @extend_schema(
        tags=['Invoicing - Invoices'],
        operation_id='admin_invoicing_invoice_render',
        summary='Render invoice payload for print/PDF/preview',
        description='Returns complete hierarchical rendering tree including branding styling, header custom fields, line custom columns, bank remittance details, and statutory tax breakdown.',
        responses={status.HTTP_200_OK: dict},
    )
    def get(self, request, invoice_id):
        render_payload = InvoicingSelector.invoice_render_data(invoice_id=invoice_id)
        return api_success(data=render_payload)


# -----------------------------------------------------------------------------
# RECURRING SCHEDULE APIS
# -----------------------------------------------------------------------------
class RecurringScheduleListCreateAdminApi(BaseInvoicingAdminApi):
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Invoicing - Recurring Schedules'],
        operation_id='admin_invoicing_schedule_list',
        summary='List recurring billing schedules',
        parameters=[
            OpenApiParameter(name='client_id', description='Filter by client ID', required=False, type=str),
            OpenApiParameter(name='status', description='Filter by schedule status (ACTIVE, PAUSED, COMPLETED)', required=False, type=str),
        ],
        responses={status.HTTP_200_OK: RecurringScheduleSerializer(many=True)},
    )
    def get(self, request):
        schedules = InvoicingSelector.recurring_schedule_list(
            client_id=request.query_params.get('client_id'),
            status=request.query_params.get('status')
        )
        return paginate_queryset(schedules, request, RecurringScheduleSerializer)

    @extend_schema(
        tags=['Invoicing - Recurring Schedules'],
        operation_id='admin_invoicing_schedule_create',
        summary='Create recurring billing schedule',
        request=RecurringScheduleSerializer,
        responses={status.HTTP_201_CREATED: RecurringScheduleSerializer},
    )
    def post(self, request):
        serializer = RecurringScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        schedule = InvoicingService.recurring_schedule_create(
            schedule_name=data['schedule_name'],
            client_id=str(data['client_id']),
            template_id=str(data['template_id']) if data.get('template_id') else None,
            category_id=str(data['category_id']) if data.get('category_id') else None,
            frequency=data.get('frequency', 'MONTHLY'),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            auto_issue=data.get('auto_issue', False),
            auto_email=data.get('auto_email', False),
            invoice_payload=data.get('invoice_payload', {}),
        )
        return api_success(
            data=RecurringScheduleSerializer(schedule).data,
            message="Recurring schedule created successfully.",
            status_code=status.HTTP_201_CREATED
        )


class RecurringScheduleDetailAdminApi(BaseInvoicingAdminApi):
    @extend_schema(
        tags=['Invoicing - Recurring Schedules'],
        operation_id='admin_invoicing_schedule_detail',
        summary='Retrieve recurring schedule detail',
        responses={status.HTTP_200_OK: RecurringScheduleSerializer},
    )
    def get(self, request, schedule_id):
        schedule = InvoicingSelector.recurring_schedule_detail(schedule_id=schedule_id)
        return api_success(data=RecurringScheduleSerializer(schedule).data)

    @extend_schema(
        tags=['Invoicing - Recurring Schedules'],
        operation_id='admin_invoicing_schedule_update',
        summary='Update recurring schedule',
        request=RecurringScheduleSerializer,
        responses={status.HTTP_200_OK: RecurringScheduleSerializer},
    )
    def patch(self, request, schedule_id):
        serializer = RecurringScheduleSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        schedule = InvoicingService.recurring_schedule_update(
            schedule_id=schedule_id,
            **serializer.validated_data
        )
        return api_success(
            data=RecurringScheduleSerializer(schedule).data,
            message="Recurring schedule updated successfully."
        )


class RecurringScheduleRunDueAdminApi(BaseInvoicingAdminApi):
    @extend_schema(
        tags=['Invoicing - Recurring Schedules'],
        operation_id='admin_invoicing_schedule_run_due',
        summary='Execute due recurring schedules',
        description='Generates invoices for all active schedules where next_run_date <= today, advances next_run_date.',
        request=None,
        responses={status.HTTP_200_OK: InvoiceListSerializer(many=True)},
    )
    def post(self, request):
        invoices = InvoicingService.recurring_schedule_execute_due(user=request.user)
        return api_success(
            data=InvoiceListSerializer(invoices, many=True).data,
            message=f"Executed recurring billing: generated {len(invoices)} invoice(s)."
        )
