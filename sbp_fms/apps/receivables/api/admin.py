from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.responses import api_success
from apps.common.pagination import CustomPageNumberPagination, paginate_queryset
from apps.users.permissions import HasPermissionCode, CountryScopedAccess
from apps.receivables.models import Client
from apps.receivables.selectors import (
    client_list, client_detail, client_invoice_list, client_invoice_detail, aging_report_get,
    client_invoice_template_list, client_invoice_template_detail, invoice_template_presets_list,
    client_invoice_render_data, invoice_builder_preview_data
)
from apps.receivables.services import ReceivablesService
from apps.receivables.serializers import (
    ClientOutputSerializer, ClientCreateInputSerializer, ClientUpdateInputSerializer,
    ClientInvoiceOutputSerializer, ClientInvoiceCreateInputSerializer, ClientInvoiceUpdateInputSerializer,
    AgingReportOutputSerializer,
    ClientInvoiceTemplateOutputSerializer, ClientInvoiceTemplateCreateInputSerializer,
    ClientInvoiceTemplateUpdateInputSerializer, InvoiceBuilderPreviewInputSerializer,
    ApplyPresetInputSerializer, ClientInvoiceRenderOutputSerializer
)


class ClientListAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('receivables:read')(), CountryScopedAccess]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Receivables - Clients Admin'],
        operation_id='admin_receivables_client_list',
        summary='List enterprise clients',
        description='Returns client billing profiles with credit limits and payment terms.',
        parameters=[
            OpenApiParameter(name='country', description='Two-letter country code filter (e.g. GH, CI)', required=False, type=str)
        ],
        responses={
            status.HTTP_200_OK: ClientOutputSerializer(many=True),
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        clients = client_list(country_code=request.query_params.get('country'))
        return paginate_queryset(clients, request, ClientOutputSerializer)

    @extend_schema(
        tags=['Receivables - Clients Admin'],
        operation_id='admin_receivables_client_create',
        summary='Create client account',
        description='Creates a new customer billing profile with assigned country and credit terms.',
        request=ClientCreateInputSerializer,
        responses={
            status.HTTP_201_CREATED: ClientOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        if not request.user.has_permission_code('receivables:create'):
            return Response({'detail': 'Permission denied: receivables:create required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ClientCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        client = ReceivablesService.client_create(**serializer.validated_data)
        return api_success(
            data=ClientOutputSerializer(client).data,
            message="Client created successfully.",
            status_code=status.HTTP_201_CREATED
        )


class ClientDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('receivables:read')()]

    @extend_schema(
        tags=['Receivables - Clients Admin'],
        operation_id='admin_receivables_client_detail',
        summary='Retrieve client profile',
        responses={
            status.HTTP_200_OK: ClientOutputSerializer,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def get(self, request, client_id):
        client = client_detail(client_id=client_id)
        return api_success(data=ClientOutputSerializer(client).data, message="Client retrieved successfully.")

    @extend_schema(
        tags=['Receivables - Clients Admin'],
        operation_id='admin_receivables_client_update',
        summary='Update client profile',
        request=ClientUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: ClientOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def put(self, request, client_id):
        if not request.user.has_permission_code('receivables:create'):
            return Response({'detail': 'Permission denied: receivables:create required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ClientUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        client = ReceivablesService.client_update(client_id=client_id, **serializer.validated_data)
        return api_success(data=ClientOutputSerializer(client).data, message="Client updated successfully.")

    @extend_schema(
        tags=['Receivables - Clients Admin'],
        operation_id='admin_receivables_client_partial_update',
        summary='Partially update client profile',
        request=ClientUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: ClientOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def patch(self, request, client_id):
        return self.put(request, client_id)

    @extend_schema(
        tags=['Receivables - Clients Admin'],
        operation_id='admin_receivables_client_delete',
        summary='Delete client profile',
        responses={
            status.HTTP_200_OK: dict,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def delete(self, request, client_id):
        if not request.user.has_permission_code('receivables:create'):
            return Response({'detail': 'Permission denied: receivables:create required'}, status=status.HTTP_403_FORBIDDEN)
        ReceivablesService.client_delete(client_id=client_id)
        return api_success(message="Client deleted successfully.", status_code=status.HTTP_200_OK)


class ClientInvoiceListAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('receivables:read')()]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Receivables - Invoices Admin'],
        operation_id='admin_receivables_invoice_list',
        summary='List customer invoices',
        parameters=[
            OpenApiParameter(name='status', description='Filter by invoice status (e.g. ISSUED, PAID, OVERDUE)', required=False, type=str),
            OpenApiParameter(name='client_id', description='Filter by client UUID', required=False, type=str)
        ],
        responses={
            status.HTTP_200_OK: ClientInvoiceOutputSerializer(many=True),
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        invoices = client_invoice_list(
            status=request.query_params.get('status'),
            client_id=request.query_params.get('client_id')
        )
        return paginate_queryset(invoices, request, ClientInvoiceOutputSerializer)

    @extend_schema(
        tags=['Receivables - Invoices Admin'],
        operation_id='admin_receivables_invoice_create',
        summary='Create customer invoice',
        description='Issues a new invoice to a client with specified billing dates and total amount.',
        request=ClientInvoiceCreateInputSerializer,
        responses={
            status.HTTP_201_CREATED: ClientInvoiceOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        if not request.user.has_permission_code('receivables:create'):
            return Response({'detail': 'Permission denied: receivables:create required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ClientInvoiceCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        client = Client.objects.get(id=data['client_id'])
        inv = ReceivablesService.invoice_create(
            invoice_number=data['invoice_number'],
            client=client,
            issue_date=data['issue_date'],
            due_date=data['due_date'],
            total_amount=data.get('total_amount'),
            lines_data=data.get('lines'),
            template_id=data.get('template_id'),
            custom_fields=data.get('custom_fields'),
            notes=data.get('notes'),
            terms_and_conditions=data.get('terms_and_conditions'),
            user=request.user
        )
        return api_success(
            data=ClientInvoiceOutputSerializer(inv).data,
            message="Client invoice created successfully.",
            status_code=status.HTTP_201_CREATED
        )


class ClientInvoiceDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('receivables:read')()]

    @extend_schema(
        tags=['Receivables - Invoices Admin'],
        operation_id='admin_receivables_invoice_detail',
        summary='Retrieve customer invoice',
        responses={
            status.HTTP_200_OK: ClientInvoiceOutputSerializer,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def get(self, request, invoice_id):
        invoice = client_invoice_detail(invoice_id=invoice_id)
        return api_success(data=ClientInvoiceOutputSerializer(invoice).data, message="Client invoice retrieved successfully.")

    @extend_schema(
        tags=['Receivables - Invoices Admin'],
        operation_id='admin_receivables_invoice_update',
        summary='Update customer invoice',
        request=ClientInvoiceUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: ClientInvoiceOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def put(self, request, invoice_id):
        if not request.user.has_permission_code('receivables:create'):
            return Response({'detail': 'Permission denied: receivables:create required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ClientInvoiceUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inv = ReceivablesService.invoice_update(invoice_id=invoice_id, **serializer.validated_data)
        return api_success(data=ClientInvoiceOutputSerializer(inv).data, message="Client invoice updated successfully.")

    @extend_schema(
        tags=['Receivables - Invoices Admin'],
        operation_id='admin_receivables_invoice_partial_update',
        summary='Partially update customer invoice',
        request=ClientInvoiceUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: ClientInvoiceOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def patch(self, request, invoice_id):
        return self.put(request, invoice_id)

    @extend_schema(
        tags=['Receivables - Invoices Admin'],
        operation_id='admin_receivables_invoice_delete',
        summary='Delete customer invoice',
        responses={
            status.HTTP_200_OK: dict,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def delete(self, request, invoice_id):
        if not request.user.has_permission_code('receivables:create'):
            return Response({'detail': 'Permission denied: receivables:create required'}, status=status.HTTP_403_FORBIDDEN)
        ReceivablesService.invoice_delete(invoice_id=invoice_id)
        return api_success(message="Client invoice deleted successfully.", status_code=status.HTTP_200_OK)


class AgingReportAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('receivables:read')(), CountryScopedAccess]

    @extend_schema(
        tags=['Receivables - Reports Admin'],
        operation_id='admin_receivables_aging_report',
        summary='Retrieve debtor aging report',
        description='Returns overdue debtor aging buckets (0-30, 31-60, 61-90, 90+ days), cached for performance.',
        parameters=[
            OpenApiParameter(name='country', description='Filter by country code (e.g. GH, CI)', required=False, type=str)
        ],
        responses={
            status.HTTP_200_OK: AgingReportOutputSerializer,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        report = aging_report_get(country_code=request.query_params.get('country'))
        return api_success(data=report, message="Aging report generated successfully.")


class ClientInvoiceIssueAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('receivables:create')()]

    @extend_schema(
        tags=['Receivables - Invoices Admin'],
        operation_id='admin_receivables_invoice_issue',
        summary='Issue customer invoice and post to General Ledger',
        description='Transitions draft customer invoice to ISSUED, computes finalized taxes/retentions, and generates Accounts Receivable double-entry journal lines in GL.',
        request=None,
        responses={
            status.HTTP_200_OK: ClientInvoiceOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request, invoice_id):
        inv = ReceivablesService.invoice_issue(invoice_id=str(invoice_id), user=request.user)
        return api_success(data=ClientInvoiceOutputSerializer(inv).data, message="Invoice issued and posted to General Ledger.")


from apps.receivables.selectors import payment_receipt_list, payment_receipt_detail, customer_statement_get
from apps.receivables.serializers import (
    PaymentReceiptOutputSerializer, PaymentReceiptCreateInputSerializer,
    CustomerStatementOutputSerializer
)


class PaymentReceiptListAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('receivables:read')()]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Receivables - Receipts Admin'],
        operation_id='admin_receivables_receipt_list',
        summary='List customer payment receipts',
        description='Retrieve paginated list of client payment receipts with optional filtering by client UUID and receipt status.',
        parameters=[
            OpenApiParameter(name='client_id', description='Filter by client UUID', required=False, type=str),
            OpenApiParameter(name='status', description='Filter by receipt status (DRAFT, CONFIRMED, CANCELLED)', required=False, type=str),
        ],
        responses={status.HTTP_200_OK: PaymentReceiptOutputSerializer(many=True)}
    )
    def get(self, request):
        client_id = request.query_params.get('client_id')
        r_status = request.query_params.get('status')
        receipts = payment_receipt_list(client_id=client_id, status=r_status)
        return paginate_queryset(receipts, request, PaymentReceiptOutputSerializer)

    @extend_schema(
        tags=['Receivables - Receipts Admin'],
        operation_id='admin_receivables_receipt_create',
        summary='Create and allocate payment receipt',
        description='Record incoming customer payment, allocate received amount across outstanding invoices, and post bank debit and accounts receivable credit entries to GL.',
        request=PaymentReceiptCreateInputSerializer,
        responses={
            status.HTTP_201_CREATED: PaymentReceiptOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        if not request.user.has_permission_code('receivables:create'):
            return Response({'detail': 'Permission denied: receivables:create required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = PaymentReceiptCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        receipt = ReceivablesService.receipt_create_and_allocate(
            receipt_number=data['receipt_number'],
            receipt_date=data.get('receipt_date'),
            client_id=data['client_id'],
            amount_received=data['amount_received'],
            payment_method=data.get('payment_method', 'BANK_TRANSFER'),
            bank_account_id=data['bank_account_id'],
            reference_number=data.get('reference_number', ''),
            description=data.get('description', ''),
            allocations_data=data.get('allocations'),
            user=request.user
        )
        return api_success(data=PaymentReceiptOutputSerializer(receipt).data, message="Payment receipt confirmed and posted to GL.", status_code=status.HTTP_201_CREATED)


class PaymentReceiptDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('receivables:read')()]

    @extend_schema(
        tags=['Receivables - Receipts Admin'],
        operation_id='admin_receivables_receipt_detail',
        summary='Retrieve payment receipt details',
        description='Fetch full payment receipt information including allocated invoice breakdowns and payment method.',
        responses={status.HTTP_200_OK: PaymentReceiptOutputSerializer}
    )
    def get(self, request, receipt_id):
        receipt = payment_receipt_detail(receipt_id=receipt_id)
        return api_success(data=PaymentReceiptOutputSerializer(receipt).data)


class CustomerStatementAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('receivables:read')()]

    @extend_schema(
        tags=['Receivables - Reports Admin'],
        operation_id='admin_receivables_customer_statement',
        summary='Retrieve customer account statement',
        description='Generate running customer ledger statement with opening balance, invoices, payments, and closing balance for a specified date range.',
        parameters=[
            OpenApiParameter(name='date_from', description='Start Date (YYYY-MM-DD)', required=False, type=str),
            OpenApiParameter(name='date_to', description='End Date (YYYY-MM-DD)', required=False, type=str),
        ],
        responses={status.HTTP_200_OK: CustomerStatementOutputSerializer}
    )
    def get(self, request, client_id):
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        statement = customer_statement_get(client_id=str(client_id), date_from=date_from, date_to=date_to)
        return api_success(data=statement, message="Customer statement generated successfully.")


class ClientInvoiceTemplateListAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('receivables:read')()]

    @extend_schema(
        tags=['Receivables - Invoice Builder'],
        operation_id='admin_receivables_invoice_template_list',
        summary='List invoice design templates and custom field configurations',
        description='Returns all invoice templates with header/line custom field definitions, colors, and layout styles. Filterable by client_id.',
        parameters=[
            OpenApiParameter(name='client_id', description='Filter templates for a specific client entity (also includes global defaults)', required=False, type=str)
        ],
        responses={
            status.HTTP_200_OK: ClientInvoiceTemplateOutputSerializer(many=True),
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        client_id = request.query_params.get('client_id')
        templates = client_invoice_template_list(client_id=client_id)
        return api_success(
            data=ClientInvoiceTemplateOutputSerializer(templates, many=True).data,
            message="Invoice templates retrieved successfully."
        )

    @extend_schema(
        tags=['Receivables - Invoice Builder'],
        operation_id='admin_receivables_invoice_template_create',
        summary='Create new custom invoice template / layout',
        description='Creates a custom invoice builder configuration with dynamic header custom fields, line custom fields, styling, and compliance toggles.',
        request=ClientInvoiceTemplateCreateInputSerializer,
        responses={
            status.HTTP_201_CREATED: ClientInvoiceTemplateOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        if not request.user.has_permission_code('receivables:create'):
            return Response({'detail': 'Permission denied: receivables:create required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ClientInvoiceTemplateCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tmpl = ReceivablesService.invoice_template_create(**serializer.validated_data)
        return api_success(
            data=ClientInvoiceTemplateOutputSerializer(tmpl).data,
            message=f"Invoice template '{tmpl.template_name}' created successfully.",
            status_code=status.HTTP_201_CREATED
        )


class ClientInvoiceTemplateDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('receivables:read')()]

    @extend_schema(
        tags=['Receivables - Invoice Builder'],
        operation_id='admin_receivables_invoice_template_detail',
        summary='Retrieve invoice template configuration',
        responses={
            status.HTTP_200_OK: ClientInvoiceTemplateOutputSerializer,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def get(self, request, template_id):
        tmpl = client_invoice_template_detail(template_id=template_id)
        return api_success(data=ClientInvoiceTemplateOutputSerializer(tmpl).data, message="Template retrieved successfully.")

    @extend_schema(
        tags=['Receivables - Invoice Builder'],
        operation_id='admin_receivables_invoice_template_update',
        summary='Update invoice template configuration',
        request=ClientInvoiceTemplateUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: ClientInvoiceTemplateOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def put(self, request, template_id):
        if not request.user.has_permission_code('receivables:create'):
            return Response({'detail': 'Permission denied: receivables:create required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ClientInvoiceTemplateUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tmpl = ReceivablesService.invoice_template_update(template_id=template_id, **serializer.validated_data)
        return api_success(data=ClientInvoiceTemplateOutputSerializer(tmpl).data, message="Template updated successfully.")

    @extend_schema(
        tags=['Receivables - Invoice Builder'],
        operation_id='admin_receivables_invoice_template_partial_update',
        summary='Partially update invoice template configuration',
        request=ClientInvoiceTemplateUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: ClientInvoiceTemplateOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def patch(self, request, template_id):
        return self.put(request, template_id)

    @extend_schema(
        tags=['Receivables - Invoice Builder'],
        operation_id='admin_receivables_invoice_template_delete',
        summary='Delete invoice template',
        responses={
            status.HTTP_200_OK: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def delete(self, request, template_id):
        if not request.user.has_permission_code('receivables:create'):
            return Response({'detail': 'Permission denied: receivables:create required'}, status=status.HTTP_403_FORBIDDEN)
        ReceivablesService.invoice_template_delete(template_id=template_id)
        return api_success(message="Template deleted successfully.")


class InvoiceTemplatePresetsAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('receivables:read')()]

    @extend_schema(
        tags=['Receivables - Invoice Builder'],
        operation_id='admin_receivables_invoice_template_presets_list',
        summary='List pre-built industry invoice presets',
        description='Returns pre-configured templates for Outsourced Workforce Staffing, Standard Corporate, Executive Recruitment, and Management Consulting.',
        responses={
            status.HTTP_200_OK: dict
        }
    )
    def get(self, request):
        presets = invoice_template_presets_list()
        return api_success(data=presets, message="Invoice presets retrieved successfully.")

    @extend_schema(
        tags=['Receivables - Invoice Builder'],
        operation_id='admin_receivables_invoice_template_preset_apply',
        summary='Apply a pre-built industry preset to a client or as global default',
        description='Creates a new template directly from an industry preset code (e.g. STAFFING_WORKFORCE, STANDARD_CORPORATE, RECRUITMENT_PLACEMENTS, CONSULTING_MANAGEMENT).',
        request=ApplyPresetInputSerializer,
        responses={
            status.HTTP_201_CREATED: ClientInvoiceTemplateOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict
        }
    )
    def post(self, request):
        if not request.user.has_permission_code('receivables:create'):
            return Response({'detail': 'Permission denied: receivables:create required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ApplyPresetInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tmpl = ReceivablesService.invoice_template_apply_preset(
            preset_code=serializer.validated_data['preset_code'],
            client_id=serializer.validated_data.get('client_id'),
            template_name=serializer.validated_data.get('template_name'),
            is_default=serializer.validated_data.get('is_default', False)
        )
        return api_success(
            data=ClientInvoiceTemplateOutputSerializer(tmpl).data,
            message=f"Preset '{serializer.validated_data['preset_code']}' applied successfully as '{tmpl.template_name}'.",
            status_code=status.HTTP_201_CREATED
        )


class InvoiceBuilderPreviewAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('receivables:read')()]

    @extend_schema(
        tags=['Receivables - Invoice Builder'],
        operation_id='admin_receivables_invoice_builder_preview',
        summary='Real-time interactive invoice builder preview',
        description='Renders a live styled preview packet for the frontend given any template configuration and optional sample invoice data.',
        request=InvoiceBuilderPreviewInputSerializer,
        responses={
            status.HTTP_200_OK: ClientInvoiceRenderOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict
        }
    )
    def post(self, request):
        serializer = InvoiceBuilderPreviewInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        template_data = serializer.validated_data.get('template')
        template_id = serializer.validated_data.get('template_id')
        if not template_data and template_id:
            tmpl = client_invoice_template_detail(template_id=template_id)
            template_data = ClientInvoiceTemplateOutputSerializer(tmpl).data
        elif not template_data:
            from apps.receivables.presets import get_preset_by_code
            template_data = get_preset_by_code('STAFFING_WORKFORCE')

        sample = serializer.validated_data.get('sample_invoice', {})
        preview_data = invoice_builder_preview_data(template_data=template_data, sample_invoice=sample)
        return api_success(data=preview_data, message="Invoice preview generated successfully.")


class ClientInvoiceRenderAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('receivables:read')()]

    @extend_schema(
        tags=['Receivables - Invoices Admin'],
        operation_id='admin_receivables_invoice_render',
        summary='Retrieve complete rendered invoice packet with template styling and custom fields',
        description='Fetches the full structured invoice packet formatted according to the client template, with custom header fields, custom line columns, company legal details, bank remittance accounts, and tax breakdowns.',
        responses={
            status.HTTP_200_OK: ClientInvoiceRenderOutputSerializer,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def get(self, request, invoice_id):
        render_data = client_invoice_render_data(invoice_id=invoice_id)
        return api_success(data=render_data, message="Rendered invoice data retrieved successfully.")



