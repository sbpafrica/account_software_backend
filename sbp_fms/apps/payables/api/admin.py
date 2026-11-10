from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.responses import api_success
from apps.common.pagination import CustomPageNumberPagination, paginate_queryset
from apps.users.permissions import HasPermissionCode, CountryScopedAccess
from apps.payables.selectors import (
    supplier_list, supplier_detail,
    purchase_order_list, purchase_order_detail,
    goods_received_note_list, goods_received_note_detail,
    supplier_invoice_list, supplier_invoice_detail
)
from apps.payables.services import PayablesService
from apps.payables.serializers import (
    SupplierOutputSerializer, SupplierCreateInputSerializer, SupplierUpdateInputSerializer,
    PurchaseOrderOutputSerializer, PurchaseOrderCreateInputSerializer, PurchaseOrderUpdateInputSerializer,
    GoodsReceivedNoteOutputSerializer, GoodsReceivedNoteCreateInputSerializer, GoodsReceivedNoteUpdateInputSerializer,
    SupplierInvoiceOutputSerializer, SupplierInvoiceCreateInputSerializer, SupplierInvoiceUpdateInputSerializer,
    ThreeWayMatchOutputSerializer
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

