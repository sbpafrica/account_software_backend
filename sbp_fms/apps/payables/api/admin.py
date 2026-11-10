from decimal import Decimal
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.responses import api_success
from apps.common.pagination import CustomPageNumberPagination, paginate_queryset
from apps.users.permissions import HasPermissionCode, CountryScopedAccess
from apps.payables.selectors import (
    supplier_list, supplier_detail,
    purchase_order_list, purchase_order_detail,
    goods_received_note_list, goods_received_note_detail,
    supplier_invoice_list, supplier_invoice_detail,
    expense_claim_list, expense_claim_detail
)
from apps.payables.services import PayablesService
from apps.payables.serializers import (
    SupplierOutputSerializer, SupplierCreateInputSerializer, SupplierUpdateInputSerializer,
    PurchaseOrderOutputSerializer, PurchaseOrderCreateInputSerializer, PurchaseOrderUpdateInputSerializer,
    GoodsReceivedNoteOutputSerializer, GoodsReceivedNoteCreateInputSerializer, GoodsReceivedNoteUpdateInputSerializer,
    SupplierInvoiceOutputSerializer, SupplierInvoiceCreateInputSerializer, SupplierInvoiceUpdateInputSerializer,
    ThreeWayMatchOutputSerializer,
    ExpenseClaimOutputSerializer, ExpenseClaimCreateInputSerializer, ExpenseClaimSettleInputSerializer
)


# ============================================================================
# 1. SUPPLIERS
# ============================================================================

class SupplierListAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:read')(), CountryScopedAccess]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Payables - Suppliers Admin'],
        operation_id='admin_payables_supplier_list',
        summary='List registered suppliers',
        description='Returns vendor profiles with tax identification numbers and withholding tax rates.',
        parameters=[
            OpenApiParameter(name='country', description='Two-letter country code filter (e.g. GH, CI)', required=False, type=str)
        ],
        responses={
            status.HTTP_200_OK: SupplierOutputSerializer(many=True),
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        suppliers = supplier_list(country_code=request.query_params.get('country'))
        return paginate_queryset(suppliers, request, SupplierOutputSerializer)

    @extend_schema(
        tags=['Payables - Suppliers Admin'],
        operation_id='admin_payables_supplier_create',
        summary='Create new supplier',
        description='Registers a new supplier/vendor profile.',
        request=SupplierCreateInputSerializer,
        responses={
            status.HTTP_201_CREATED: SupplierOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        if not request.user.has_permission_code('payables:create'):
            return Response({'detail': 'Permission denied: payables:create required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = SupplierCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        supplier = PayablesService.supplier_create(**serializer.validated_data)
        return api_success(
            data=SupplierOutputSerializer(supplier).data,
            message="Supplier registered successfully.",
            status_code=status.HTTP_201_CREATED
        )


class SupplierDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:read')()]

    @extend_schema(
        tags=['Payables - Suppliers Admin'],
        operation_id='admin_payables_supplier_detail',
        summary='Retrieve supplier profile',
        responses={
            status.HTTP_200_OK: SupplierOutputSerializer,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def get(self, request, supplier_id):
        supplier = supplier_detail(supplier_id=supplier_id)
        return api_success(data=SupplierOutputSerializer(supplier).data, message="Supplier profile retrieved successfully.")

    @extend_schema(
        tags=['Payables - Suppliers Admin'],
        operation_id='admin_payables_supplier_update',
        summary='Update supplier profile',
        request=SupplierUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: SupplierOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def put(self, request, supplier_id):
        if not request.user.has_permission_code('payables:create'):
            return Response({'detail': 'Permission denied: payables:create required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = SupplierUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        supplier = PayablesService.supplier_update(supplier_id=supplier_id, **serializer.validated_data)
        return api_success(data=SupplierOutputSerializer(supplier).data, message="Supplier profile updated successfully.")

    @extend_schema(
        tags=['Payables - Suppliers Admin'],
        operation_id='admin_payables_supplier_partial_update',
        summary='Partially update supplier profile',
        request=SupplierUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: SupplierOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def patch(self, request, supplier_id):
        return self.put(request, supplier_id)

    @extend_schema(
        tags=['Payables - Suppliers Admin'],
        operation_id='admin_payables_supplier_delete',
        summary='Delete supplier profile',
        responses={
            status.HTTP_200_OK: dict,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def delete(self, request, supplier_id):
        if not request.user.has_permission_code('payables:create'):
            return Response({'detail': 'Permission denied: payables:create required'}, status=status.HTTP_403_FORBIDDEN)
        PayablesService.supplier_delete(supplier_id=supplier_id)
        return api_success(message="Supplier deleted successfully.", status_code=status.HTTP_200_OK)


# ============================================================================
# 2. PURCHASE ORDERS
# ============================================================================

class PurchaseOrderListAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:read')()]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Payables - Purchase Orders Admin'],
        operation_id='admin_payables_po_list',
        summary='List purchase orders',
        parameters=[
            OpenApiParameter(name='supplier_id', description='Filter by supplier UUID', required=False, type=str)
        ],
        responses={
            status.HTTP_200_OK: PurchaseOrderOutputSerializer(many=True),
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        pos = purchase_order_list(supplier_id=request.query_params.get('supplier_id'))
        return paginate_queryset(pos, request, PurchaseOrderOutputSerializer)

    @extend_schema(
        tags=['Payables - Purchase Orders Admin'],
        operation_id='admin_payables_po_create',
        summary='Create purchase order',
        request=PurchaseOrderCreateInputSerializer,
        responses={
            status.HTTP_201_CREATED: PurchaseOrderOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        if not request.user.has_permission_code('payables:create'):
            return Response({'detail': 'Permission denied: payables:create required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = PurchaseOrderCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        po = PayablesService.purchase_order_create(
            po_number=data['po_number'],
            supplier_id=data['supplier_id'],
            total_approved_amount=data['total_approved_amount'],
            lines_data=data.get('lines', [])
        )
        return api_success(
            data=PurchaseOrderOutputSerializer(po).data,
            message="Purchase order created successfully.",
            status_code=status.HTTP_201_CREATED
        )


class PurchaseOrderDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:read')()]

    @extend_schema(
        tags=['Payables - Purchase Orders Admin'],
        operation_id='admin_payables_po_detail',
        summary='Retrieve purchase order',
        responses={
            status.HTTP_200_OK: PurchaseOrderOutputSerializer,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def get(self, request, po_id):
        po = purchase_order_detail(po_id=po_id)
        return api_success(data=PurchaseOrderOutputSerializer(po).data, message="Purchase order retrieved successfully.")

    @extend_schema(
        tags=['Payables - Purchase Orders Admin'],
        operation_id='admin_payables_po_update',
        summary='Update purchase order',
        request=PurchaseOrderUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: PurchaseOrderOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def put(self, request, po_id):
        if not request.user.has_permission_code('payables:create'):
            return Response({'detail': 'Permission denied: payables:create required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = PurchaseOrderUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        po = PayablesService.purchase_order_update(po_id=po_id, **serializer.validated_data)
        return api_success(data=PurchaseOrderOutputSerializer(po).data, message="Purchase order updated successfully.")

    @extend_schema(
        tags=['Payables - Purchase Orders Admin'],
        operation_id='admin_payables_po_partial_update',
        summary='Partially update purchase order',
        request=PurchaseOrderUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: PurchaseOrderOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def patch(self, request, po_id):
        return self.put(request, po_id)

    @extend_schema(
        tags=['Payables - Purchase Orders Admin'],
        operation_id='admin_payables_po_delete',
        summary='Delete purchase order',
        responses={
            status.HTTP_200_OK: dict,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def delete(self, request, po_id):
        if not request.user.has_permission_code('payables:create'):
            return Response({'detail': 'Permission denied: payables:create required'}, status=status.HTTP_403_FORBIDDEN)
        PayablesService.purchase_order_delete(po_id=po_id)
        return api_success(message="Purchase order deleted successfully.", status_code=status.HTTP_200_OK)



# ============================================================================
# 3. GOODS RECEIVED NOTES
# ============================================================================

class GoodsReceivedNoteListAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:read')()]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Payables - Goods Received Notes Admin'],
        operation_id='admin_payables_grn_list',
        summary='List goods received notes',
        parameters=[
            OpenApiParameter(name='po_id', description='Filter by Purchase Order UUID', required=False, type=str)
        ],
        responses={
            status.HTTP_200_OK: GoodsReceivedNoteOutputSerializer(many=True),
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        grns = goods_received_note_list(po_id=request.query_params.get('po_id'))
        return paginate_queryset(grns, request, GoodsReceivedNoteOutputSerializer)

    @extend_schema(
        tags=['Payables - Goods Received Notes Admin'],
        operation_id='admin_payables_grn_create',
        summary='Create goods received note',
        request=GoodsReceivedNoteCreateInputSerializer,
        responses={
            status.HTTP_201_CREATED: GoodsReceivedNoteOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        if not request.user.has_permission_code('payables:create'):
            return Response({'detail': 'Permission denied: payables:create required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = GoodsReceivedNoteCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        grn = PayablesService.grn_create(
            grn_number=data['grn_number'],
            po_id=data['po_id'],
            received_date=data['received_date'],
            lines_data=data.get('lines', [])
        )
        return api_success(
            data=GoodsReceivedNoteOutputSerializer(grn).data,
            message="Goods received note created successfully.",
            status_code=status.HTTP_201_CREATED
        )


class GoodsReceivedNoteDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:read')()]

    @extend_schema(
        tags=['Payables - Goods Received Notes Admin'],
        operation_id='admin_payables_grn_detail',
        summary='Retrieve goods received note',
        responses={
            status.HTTP_200_OK: GoodsReceivedNoteOutputSerializer,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def get(self, request, grn_id):
        grn = goods_received_note_detail(grn_id=grn_id)
        return api_success(data=GoodsReceivedNoteOutputSerializer(grn).data, message="Goods received note retrieved successfully.")

    @extend_schema(
        tags=['Payables - Goods Received Notes Admin'],
        operation_id='admin_payables_grn_update',
        summary='Update goods received note',
        request=GoodsReceivedNoteUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: GoodsReceivedNoteOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def put(self, request, grn_id):
        if not request.user.has_permission_code('payables:create'):
            return Response({'detail': 'Permission denied: payables:create required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = GoodsReceivedNoteUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        grn = PayablesService.grn_update(grn_id=grn_id, **serializer.validated_data)
        return api_success(data=GoodsReceivedNoteOutputSerializer(grn).data, message="Goods received note updated successfully.")

    @extend_schema(
        tags=['Payables - Goods Received Notes Admin'],
        operation_id='admin_payables_grn_partial_update',
        summary='Partially update goods received note',
        request=GoodsReceivedNoteUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: GoodsReceivedNoteOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def patch(self, request, grn_id):
        return self.put(request, grn_id)

    @extend_schema(
        tags=['Payables - Goods Received Notes Admin'],
        operation_id='admin_payables_grn_delete',
        summary='Delete goods received note',
        responses={
            status.HTTP_200_OK: dict,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def delete(self, request, grn_id):
        if not request.user.has_permission_code('payables:create'):
            return Response({'detail': 'Permission denied: payables:create required'}, status=status.HTTP_403_FORBIDDEN)
        PayablesService.grn_delete(grn_id=grn_id)
        return api_success(message="Goods received note deleted successfully.", status_code=status.HTTP_200_OK)


# ============================================================================
# 4. SUPPLIER INVOICES & 3-WAY MATCH
# ============================================================================

class SupplierInvoiceListAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:read')()]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Payables - Invoices Admin'],
        operation_id='admin_payables_invoice_list',
        summary='List supplier invoices',
        parameters=[
            OpenApiParameter(name='match_status', description='Filter by match status (e.g. PENDING, MATCHED, BLOCKED_DISCREPANCY, PAID)', required=False, type=str),
            OpenApiParameter(name='supplier_id', description='Filter by supplier UUID', required=False, type=str)
        ],
        responses={
            status.HTTP_200_OK: SupplierInvoiceOutputSerializer(many=True),
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        invoices = supplier_invoice_list(
            match_status=request.query_params.get('match_status'),
            supplier_id=request.query_params.get('supplier_id')
        )
        return paginate_queryset(invoices, request, SupplierInvoiceOutputSerializer)

    @extend_schema(
        tags=['Payables - Invoices Admin'],
        operation_id='admin_payables_invoice_create',
        summary='Create supplier invoice',
        request=SupplierInvoiceCreateInputSerializer,
        responses={
            status.HTTP_201_CREATED: SupplierInvoiceOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        if not request.user.has_permission_code('payables:create'):
            return Response({'detail': 'Permission denied: payables:create required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = SupplierInvoiceCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        inv = PayablesService.supplier_invoice_create(
            invoice_number=data['invoice_number'],
            supplier_id=data['supplier_id'],
            po_id=data['po_id'],
            grn_id=data['grn_id'],
            gross_amount=data['gross_amount'],
            lines_data=data.get('lines', [])
        )
        return api_success(
            data=SupplierInvoiceOutputSerializer(inv).data,
            message="Supplier invoice created successfully.",
            status_code=status.HTTP_201_CREATED
        )


class SupplierInvoiceDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:read')()]

    @extend_schema(
        tags=['Payables - Invoices Admin'],
        operation_id='admin_payables_invoice_detail',
        summary='Retrieve supplier invoice',
        responses={
            status.HTTP_200_OK: SupplierInvoiceOutputSerializer,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def get(self, request, invoice_id):
        invoice = supplier_invoice_detail(invoice_id=invoice_id)
        return api_success(data=SupplierInvoiceOutputSerializer(invoice).data, message="Supplier invoice retrieved successfully.")

    @extend_schema(
        tags=['Payables - Invoices Admin'],
        operation_id='admin_payables_invoice_update',
        summary='Update supplier invoice',
        request=SupplierInvoiceUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: SupplierInvoiceOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def put(self, request, invoice_id):
        if not request.user.has_permission_code('payables:create'):
            return Response({'detail': 'Permission denied: receivables:create required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = SupplierInvoiceUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inv = PayablesService.supplier_invoice_update(invoice_id=invoice_id, **serializer.validated_data)
        return api_success(data=SupplierInvoiceOutputSerializer(inv).data, message="Supplier invoice updated successfully.")

    @extend_schema(
        tags=['Payables - Invoices Admin'],
        operation_id='admin_payables_invoice_partial_update',
        summary='Partially update supplier invoice',
        request=SupplierInvoiceUpdateInputSerializer,
        responses={
            status.HTTP_200_OK: SupplierInvoiceOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_404_NOT_FOUND: dict
        }
    )
    def patch(self, request, invoice_id):
        return self.put(request, invoice_id)

    @extend_schema(
        tags=['Payables - Invoices Admin'],
        operation_id='admin_payables_invoice_delete',
        summary='Delete supplier invoice',
        responses={
            status.HTTP_200_OK: dict,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def delete(self, request, invoice_id):
        if not request.user.has_permission_code('payables:create'):
            return Response({'detail': 'Permission denied: payables:create required'}, status=status.HTTP_403_FORBIDDEN)
        PayablesService.supplier_invoice_delete(invoice_id=invoice_id)
        return api_success(message="Supplier invoice deleted successfully.", status_code=status.HTTP_200_OK)


class ThreeWayMatchRunAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:match')()]

    @extend_schema(
        tags=['Payables - Invoices Admin'],
        operation_id='admin_payables_invoice_match',
        summary='Execute automated 3-way match',
        description='Validates supplier invoice lines against purchase order and goods received note quantities and prices.',
        request=None,
        responses={
            status.HTTP_200_OK: ThreeWayMatchOutputSerializer,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request, invoice_id):
        success, message = PayablesService.execute_three_way_match(invoice_id=invoice_id)
        return api_success(data={'success': success, 'message': message}, message="3-way match executed.")


# ============================================================================
# 5. PAYMENT VOUCHERS & AP AGING / STATEMENTS
# ============================================================================

from apps.payables.selectors import (
    payment_voucher_list, payment_voucher_detail,
    ap_aging_report_get, supplier_statement_get
)
from apps.payables.serializers import (
    PaymentVoucherOutputSerializer, PaymentVoucherCreateInputSerializer,
    PaymentVoucherMarkPaidInputSerializer, PaymentVoucherRejectInputSerializer,
    APAgingReportOutputSerializer, SupplierStatementOutputSerializer,
    ExpenseClaimRejectInputSerializer
)


class PaymentVoucherListAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:read')()]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Payables - Payment Vouchers'],
        operation_id='admin_payables_voucher_list',
        summary='List payment vouchers',
        description='Retrieve paginated list of payment vouchers with optional filtering by supplier UUID and voucher status.',
        parameters=[
            OpenApiParameter(name='supplier_id', description='Filter by supplier UUID', required=False, type=str),
            OpenApiParameter(name='status', description='Filter by voucher status (DRAFT, PENDING_REVIEW, APPROVED, PAID, REJECTED)', required=False, type=str),
        ],
        responses={status.HTTP_200_OK: PaymentVoucherOutputSerializer(many=True)}
    )
    def get(self, request):
        supplier_id = request.query_params.get('supplier_id')
        v_status = request.query_params.get('status')
        vouchers = payment_voucher_list(supplier_id=supplier_id, status=v_status)
        return paginate_queryset(vouchers, request, PaymentVoucherOutputSerializer)

    @extend_schema(
        tags=['Payables - Payment Vouchers'],
        operation_id='admin_payables_voucher_create',
        summary='Create draft payment voucher',
        description='Create a new payment voucher draft with optional line allocations, linked bill, and withholding tax deduction.',
        request=PaymentVoucherCreateInputSerializer,
        responses={
            status.HTTP_201_CREATED: PaymentVoucherOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        if not request.user.has_permission_code('payables:create'):
            return Response({'detail': 'Permission denied: payables:create required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = PaymentVoucherCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        voucher = PayablesService.voucher_create_draft(
            voucher_number=data['voucher_number'],
            voucher_date=data['voucher_date'],
            payee_name=data['payee_name'],
            gross_amount=data['gross_amount'],
            payee_type=data.get('payee_type', 'SUPPLIER'),
            payment_method=data.get('payment_method', 'BANK_TRANSFER'),
            supplier_id=data.get('supplier_id'),
            supplier_invoice_id=data.get('supplier_invoice_id'),
            bank_account_id=data.get('bank_account_id'),
            wht_rate=data.get('wht_rate', Decimal('0.0000')),
            other_deductions=data.get('other_deductions', Decimal('0.0000')),
            description=data.get('description', ''),
            department=data.get('department', ''),
            cost_centre=data.get('cost_centre', ''),
            client_id=data.get('client_id'),
            lines_data=data.get('lines'),
            user=request.user
        )
        return api_success(data=PaymentVoucherOutputSerializer(voucher).data, message="Payment voucher draft created.", status_code=status.HTTP_201_CREATED)


class PaymentVoucherDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:read')()]

    @extend_schema(
        tags=['Payables - Payment Vouchers'],
        operation_id='admin_payables_voucher_detail',
        summary='Retrieve payment voucher details',
        description='Fetch full payment voucher details including line breakdowns, workflow audit stamps, and linked supplier bill.',
        responses={status.HTTP_200_OK: PaymentVoucherOutputSerializer}
    )
    def get(self, request, voucher_id):
        voucher = payment_voucher_detail(voucher_id=voucher_id)
        return api_success(data=PaymentVoucherOutputSerializer(voucher).data)


class PaymentVoucherSubmitAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:create')()]

    @extend_schema(
        tags=['Payables - Payment Vouchers'],
        operation_id='admin_payables_voucher_submit',
        summary='Submit payment voucher for review',
        description='Transitions a DRAFT payment voucher to PENDING_REVIEW status.',
        request=None,
        responses={
            status.HTTP_200_OK: PaymentVoucherOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request, voucher_id):
        voucher = PayablesService.voucher_submit(voucher_id=str(voucher_id))
        return api_success(data=PaymentVoucherOutputSerializer(voucher).data, message="Voucher submitted for review.")


class PaymentVoucherReviewAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:review')()]

    @extend_schema(
        tags=['Payables - Payment Vouchers'],
        operation_id='admin_payables_voucher_review',
        summary='Review payment voucher',
        description='Marks a payment voucher as reviewed and promotes it to PENDING_APPROVAL status.',
        request=None,
        responses={
            status.HTTP_200_OK: PaymentVoucherOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request, voucher_id):
        voucher = PayablesService.voucher_review(voucher_id=str(voucher_id), user=request.user)
        return api_success(data=PaymentVoucherOutputSerializer(voucher).data, message="Voucher reviewed.")


class PaymentVoucherApproveAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:approve')()]

    @extend_schema(
        tags=['Payables - Payment Vouchers'],
        operation_id='admin_payables_voucher_approve',
        summary='Approve payment voucher',
        description='Approves a reviewed payment voucher for final disbursement by treasury or accounts payable.',
        request=None,
        responses={
            status.HTTP_200_OK: PaymentVoucherOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request, voucher_id):
        voucher = PayablesService.voucher_approve(voucher_id=str(voucher_id), user=request.user)
        return api_success(data=PaymentVoucherOutputSerializer(voucher).data, message="Voucher approved for payment.")


class PaymentVoucherRejectAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:approve')()]

    @extend_schema(
        tags=['Payables - Payment Vouchers'],
        operation_id='admin_payables_voucher_reject',
        summary='Reject payment voucher',
        description='Rejects a payment voucher and records rejection reason notes.',
        request=PaymentVoucherRejectInputSerializer,
        responses={
            status.HTTP_200_OK: PaymentVoucherOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request, voucher_id):
        serializer = PaymentVoucherRejectInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        voucher = PayablesService.voucher_reject(voucher_id=str(voucher_id), user=request.user, reason=serializer.validated_data['reason'])
        return api_success(data=PaymentVoucherOutputSerializer(voucher).data, message="Voucher rejected.")


class PaymentVoucherMarkPaidAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:disburse')()]

    @extend_schema(
        tags=['Payables - Payment Vouchers'],
        operation_id='admin_payables_voucher_mark_paid',
        summary='Disburse payment and mark voucher as paid',
        description='Records final disbursement of funds from the bank account, updates voucher to PAID, and generates General Ledger double-entry lines.',
        request=PaymentVoucherMarkPaidInputSerializer,
        responses={
            status.HTTP_200_OK: PaymentVoucherOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request, voucher_id):
        serializer = PaymentVoucherMarkPaidInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        voucher = PayablesService.voucher_mark_paid(
            voucher_id=str(voucher_id),
            user=request.user,
            payment_date=data.get('payment_date'),
            bank_account_id=data.get('bank_account_id'),
            reference_number=data.get('reference_number')
        )
        return api_success(data=PaymentVoucherOutputSerializer(voucher).data, message="Voucher marked as paid and posted to GL.")


class APAgingReportAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:read')()]

    @extend_schema(
        tags=['Payables - Reports Admin'],
        operation_id='admin_payables_aging_report',
        summary='Retrieve Accounts Payable aging report',
        description='Generates Accounts Payable aging buckets (current, 30, 60, 90+ days) for unpaid supplier bills.',
        parameters=[
            OpenApiParameter(name='country', description='Two-letter country code filter (e.g. GH, NG, CI)', required=False, type=str)
        ],
        responses={
            status.HTTP_200_OK: APAgingReportOutputSerializer,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request):
        country = request.query_params.get('country')
        report = ap_aging_report_get(country_code=country)
        return api_success(data=report, message="AP Aging report retrieved.")


class SupplierStatementAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:read')()]

    @extend_schema(
        tags=['Payables - Reports Admin'],
        operation_id='admin_payables_supplier_statement',
        summary='Retrieve supplier account statement',
        description='Generates running supplier ledger statement with opening balance, bills, payments, and closing balance for a specified date range.',
        parameters=[
            OpenApiParameter(name='date_from', description='Start Date (YYYY-MM-DD)', required=False, type=str),
            OpenApiParameter(name='date_to', description='End Date (YYYY-MM-DD)', required=False, type=str),
        ],
        responses={
            status.HTTP_200_OK: SupplierStatementOutputSerializer,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def get(self, request, supplier_id):
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        statement = supplier_statement_get(supplier_id=str(supplier_id), date_from=date_from, date_to=date_to)
        return api_success(data=statement, message="Supplier statement retrieved.")


# ============================================================================
# 8. EMPLOYEE EXPENSE CLAIMS & ADVANCES
# ============================================================================

class ExpenseClaimListCreateAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:read')()]
    pagination_class = CustomPageNumberPagination

    @extend_schema(
        tags=['Payables - Expense Claims'],
        operation_id='admin_payables_expense_claim_list',
        summary='List employee expense claims',
        description='Retrieve paginated list of employee expense claims and petty cash advances with optional filtering by employee, status, and claim type.',
        parameters=[
            OpenApiParameter(name='employee_id', description='Filter by employee UUID', required=False, type=str),
            OpenApiParameter(name='status', description='Filter by claim status (DRAFT, SUBMITTED, APPROVED, REJECTED, SETTLED)', required=False, type=str),
            OpenApiParameter(name='claim_type', description='Filter by claim type (REIMBURSEMENT, ADVANCE)', required=False, type=str),
        ],
        responses={status.HTTP_200_OK: ExpenseClaimOutputSerializer(many=True)}
    )
    def get(self, request):
        employee_id = request.query_params.get('employee_id')
        claim_status = request.query_params.get('status')
        claim_type = request.query_params.get('claim_type')
        claims = expense_claim_list(employee_id=employee_id, status=claim_status, claim_type=claim_type)
        return paginate_queryset(claims, request, ExpenseClaimOutputSerializer)

    @extend_schema(
        tags=['Payables - Expense Claims'],
        operation_id='admin_payables_expense_claim_create',
        summary='Create draft expense claim',
        description='Create a new employee reimbursement claim or cash advance with line item category breakdowns.',
        request=ExpenseClaimCreateInputSerializer,
        responses={
            status.HTTP_201_CREATED: ExpenseClaimOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request):
        if not request.user.has_permission_code('payables:create'):
            return Response({'detail': 'Permission denied: payables:create required'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ExpenseClaimCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        claim = PayablesService.expense_claim_create(
            employee_id=str(data['employee_id']),
            claim_date=data['claim_date'],
            claim_type=data.get('claim_type', 'REIMBURSEMENT'),
            advance_amount=data.get('advance_amount', Decimal('0.0000')),
            department=data.get('department', ''),
            cost_centre=data.get('cost_centre', ''),
            notes=data.get('notes', ''),
            lines_data=data.get('lines'),
            country_code=data.get('country_code', 'GH'),
            user=request.user
        )
        return api_success(data=ExpenseClaimOutputSerializer(claim).data, message="Expense claim created as draft.", status_code=status.HTTP_201_CREATED)


class ExpenseClaimDetailAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:read')()]

    @extend_schema(
        tags=['Payables - Expense Claims'],
        operation_id='admin_payables_expense_claim_detail',
        summary='Retrieve expense claim details',
        description='Fetch full employee expense claim details including itemized expense lines, advance deductions, and settlement status.',
        responses={status.HTTP_200_OK: ExpenseClaimOutputSerializer}
    )
    def get(self, request, claim_id):
        claim = expense_claim_detail(claim_id=str(claim_id))
        return api_success(data=ExpenseClaimOutputSerializer(claim).data)


class ExpenseClaimSubmitAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:create')()]

    @extend_schema(
        tags=['Payables - Expense Claims'],
        operation_id='admin_payables_expense_claim_submit',
        summary='Submit expense claim for approval',
        description='Transitions a DRAFT expense claim to SUBMITTED status for manager/finance approval.',
        request=None,
        responses={
            status.HTTP_200_OK: ExpenseClaimOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request, claim_id):
        claim = PayablesService.expense_claim_submit(claim_id=str(claim_id), user=request.user)
        return api_success(data=ExpenseClaimOutputSerializer(claim).data, message="Expense claim submitted for approval.")


class ExpenseClaimApproveAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:approve')()]

    @extend_schema(
        tags=['Payables - Expense Claims'],
        operation_id='admin_payables_expense_claim_approve',
        summary='Approve expense claim',
        description='Approves an employee expense claim for settlement and disbursement.',
        request=None,
        responses={
            status.HTTP_200_OK: ExpenseClaimOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request, claim_id):
        claim = PayablesService.expense_claim_approve(claim_id=str(claim_id), user=request.user)
        return api_success(data=ExpenseClaimOutputSerializer(claim).data, message="Expense claim approved.")


class ExpenseClaimRejectAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:review')()]

    @extend_schema(
        tags=['Payables - Expense Claims'],
        operation_id='admin_payables_expense_claim_reject',
        summary='Reject expense claim',
        description='Rejects an employee expense claim with an explanatory note.',
        request=ExpenseClaimRejectInputSerializer,
        responses={
            status.HTTP_200_OK: ExpenseClaimOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request, claim_id):
        serializer = ExpenseClaimRejectInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get('reason', 'Rejected')
        claim = PayablesService.expense_claim_reject(claim_id=str(claim_id), reason=reason, user=request.user)
        return api_success(data=ExpenseClaimOutputSerializer(claim).data, message="Expense claim rejected.")


class ExpenseClaimSettleAdminApi(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode('payables:disburse')()]

    @extend_schema(
        tags=['Payables - Expense Claims'],
        operation_id='admin_payables_expense_claim_settle',
        summary='Settle expense claim and issue payment voucher',
        description='Settles approved expense claim by issuing a payment voucher and clearing employee advance or reimbursement liabilities.',
        request=ExpenseClaimSettleInputSerializer,
        responses={
            status.HTTP_200_OK: ExpenseClaimOutputSerializer,
            status.HTTP_400_BAD_REQUEST: dict,
            status.HTTP_403_FORBIDDEN: dict
        }
    )
    def post(self, request, claim_id):
        serializer = ExpenseClaimSettleInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        claim = PayablesService.expense_claim_settle(
            claim_id=str(claim_id),
            bank_account_id=serializer.validated_data.get('bank_account_id'),
            user=request.user
        )
        return api_success(data=ExpenseClaimOutputSerializer(claim).data, message="Expense claim settled and payment voucher issued.")



