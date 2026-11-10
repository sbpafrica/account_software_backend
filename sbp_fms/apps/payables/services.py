from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.common.cache import CacheManager
from .models import (
    Supplier, PurchaseOrder, POLine,
    GoodsReceivedNote, GRNLine,
    SupplierInvoice, InvoiceLine, MatchStatus
)


class PayablesService:
    @staticmethod
    @transaction.atomic
    def supplier_create(*, name: str, tax_id: str, country_code: str = 'GH',
                        wht_rate: Decimal = Decimal('0.0750'), bank_account_number: str = '', bank_name: str = '') -> Supplier:
        supplier = Supplier.objects.create(
            name=name,
            tax_id=tax_id,
            country_code=country_code,
            withholding_tax_rate=wht_rate,
            bank_account_number=bank_account_number,
            bank_name=bank_name
        )
        CacheManager.invalidate_payables()
        return supplier

    @staticmethod
    @transaction.atomic
    def supplier_update(*, supplier_id, name: str = None, tax_id: str = None,
                        country_code: str = None, wht_rate: Decimal = None,
                        bank_account_number: str = None, bank_name: str = None) -> Supplier:
        supplier = Supplier.objects.select_for_update().get(id=supplier_id)
        if name is not None:
            supplier.name = name.strip()
        if tax_id is not None:
            supplier.tax_id = tax_id.strip()
        if country_code is not None:
            supplier.country_code = country_code
        if wht_rate is not None:
            supplier.withholding_tax_rate = wht_rate
        if bank_account_number is not None:
            supplier.bank_account_number = bank_account_number
        if bank_name is not None:
            supplier.bank_name = bank_name
        supplier.save()
        CacheManager.invalidate_payables()
        return supplier

    @staticmethod
    @transaction.atomic
    def supplier_delete(*, supplier_id) -> None:
        supplier = Supplier.objects.get(id=supplier_id)
        if supplier.invoices.exists() or supplier.purchase_orders.exists():
            raise ValidationError(f"Cannot delete supplier '{supplier.name}' because related purchase orders or bills exist.")
        supplier.delete()
        CacheManager.invalidate_payables()

    @staticmethod
    @transaction.atomic
    def purchase_order_create(*, po_number: str, supplier_id, total_approved_amount: Decimal,
                              lines_data: list = None) -> PurchaseOrder:
        if PurchaseOrder.objects.filter(po_number=po_number).exists():
            raise ValidationError(f"Purchase order '{po_number}' already exists.")
        supplier = Supplier.objects.get(id=supplier_id)
        po = PurchaseOrder.objects.create(
            po_number=po_number,
            supplier=supplier,
            total_approved_amount=total_approved_amount,
            is_approved=True
        )
        if lines_data:
            for l in lines_data:
                POLine.objects.create(
                    po=po,
                    item_code=l['item_code'],
                    quantity=l['quantity'],
                    approved_unit_price=l['approved_unit_price']
                )
        CacheManager.invalidate_payables()
        return po

    @staticmethod
    @transaction.atomic
    def purchase_order_update(*, po_id, total_approved_amount: Decimal = None,
                              is_approved: bool = None) -> PurchaseOrder:
        po = PurchaseOrder.objects.select_for_update().get(id=po_id)
        if total_approved_amount is not None:
            po.total_approved_amount = total_approved_amount
        if is_approved is not None:
            po.is_approved = is_approved
        po.save()
        CacheManager.invalidate_payables()
        return po

    @staticmethod
    @transaction.atomic
    def purchase_order_delete(*, po_id) -> None:
        po = PurchaseOrder.objects.get(id=po_id)
        if po.invoices.exists() or po.grns.exists():
            raise ValidationError(f"Cannot delete PO '{po.po_number}' with linked GRNs or invoices.")
        po.delete()
        CacheManager.invalidate_payables()

    @staticmethod
    @transaction.atomic
    def grn_create(*, grn_number: str, po_id, received_date, lines_data: list = None) -> GoodsReceivedNote:
        if GoodsReceivedNote.objects.filter(grn_number=grn_number).exists():
            raise ValidationError(f"GRN '{grn_number}' already exists.")
        po = PurchaseOrder.objects.get(id=po_id)
        grn = GoodsReceivedNote.objects.create(
            grn_number=grn_number,
            po=po,
            received_date=received_date
        )
        if lines_data:
            for l in lines_data:
                GRNLine.objects.create(
                    grn=grn,
                    item_code=l['item_code'],
                    received_quantity=l['received_quantity']
                )
        CacheManager.invalidate_payables()
        return grn

    @staticmethod
    @transaction.atomic
    def grn_update(*, grn_id, received_date=None) -> GoodsReceivedNote:
        grn = GoodsReceivedNote.objects.select_for_update().get(id=grn_id)
        if received_date is not None:
            grn.received_date = received_date
        grn.save()
        CacheManager.invalidate_payables()
        return grn

    @staticmethod
    @transaction.atomic
    def grn_delete(*, grn_id) -> None:
        grn = GoodsReceivedNote.objects.get(id=grn_id)
        if grn.invoices.exists():
            raise ValidationError(f"Cannot delete GRN '{grn.grn_number}' linked to supplier invoices.")
        grn.delete()
        CacheManager.invalidate_payables()

    @staticmethod
    @transaction.atomic
    def supplier_invoice_create(*, invoice_number: str, supplier_id, po_id, grn_id,
                                gross_amount: Decimal, lines_data: list = None) -> SupplierInvoice:
        supplier = Supplier.objects.get(id=supplier_id)
        po = PurchaseOrder.objects.get(id=po_id)
        grn = GoodsReceivedNote.objects.get(id=grn_id)

        if SupplierInvoice.objects.filter(supplier=supplier, invoice_number=invoice_number).exists():
            raise ValidationError(f"Invoice '{invoice_number}' already exists for supplier '{supplier.name}'.")

        rate = supplier.withholding_tax_rate
        wht = (gross_amount * rate).quantize(Decimal('0.0001'))
        net_payable = gross_amount - wht

        invoice = SupplierInvoice.objects.create(
            invoice_number=invoice_number,
            supplier=supplier,
            po=po,
            grn=grn,
            gross_amount=gross_amount,
            wht_amount=wht,
            net_payable_amount=net_payable,
            match_status=MatchStatus.PENDING
        )
        if lines_data:
            for l in lines_data:
                InvoiceLine.objects.create(
                    invoice=invoice,
                    item_code=l['item_code'],
                    billed_quantity=l['billed_quantity'],
                    billed_unit_price=l['billed_unit_price']
                )
        CacheManager.invalidate_payables()
        return invoice

    @staticmethod
    @transaction.atomic
    def supplier_invoice_update(*, invoice_id, gross_amount: Decimal = None,
                                match_status: str = None) -> SupplierInvoice:
        invoice = SupplierInvoice.objects.select_for_update().get(id=invoice_id)
        if gross_amount is not None:
            invoice.gross_amount = gross_amount
            rate = invoice.supplier.withholding_tax_rate
            invoice.wht_amount = (gross_amount * rate).quantize(Decimal('0.0001'))
            invoice.net_payable_amount = gross_amount - invoice.wht_amount
        if match_status is not None:
            invoice.match_status = match_status
        invoice.save()
        CacheManager.invalidate_payables()
        return invoice

    @staticmethod
    @transaction.atomic
    def supplier_invoice_delete(*, invoice_id) -> None:
        invoice = SupplierInvoice.objects.get(id=invoice_id)
        if invoice.match_status == MatchStatus.PAID:
            raise ValidationError("Cannot delete an invoice that has already been paid.")
        invoice.delete()
        CacheManager.invalidate_payables()

    @staticmethod
    @transaction.atomic
    def execute_three_way_match(*, invoice_id: str) -> tuple[bool, str]:
        invoice = SupplierInvoice.objects.select_for_update().prefetch_related('lines', 'po__lines', 'grn__lines').get(id=invoice_id)
        po = invoice.po
        grn = invoice.grn

        discrepancies = []
        for line in invoice.lines.all():
            po_line = po.lines.filter(item_code=line.item_code).first()
            grn_line = grn.lines.filter(item_code=line.item_code).first()

            if not po_line or not grn_line:
                discrepancies.append(f"Item {line.item_code} was not found on PO or GRN.")
                continue

            if line.billed_quantity > grn_line.received_quantity:
                discrepancies.append(
                    f"Item {line.item_code}: Billed qty ({line.billed_quantity}) exceeds delivered qty ({grn_line.received_quantity})."
                )

            if line.billed_unit_price > po_line.approved_unit_price:
                discrepancies.append(
                    f"Item {line.item_code}: Billed price ({line.billed_unit_price}) exceeds approved price ({po_line.approved_unit_price})."
                )

        if discrepancies:
            invoice.match_status = MatchStatus.BLOCKED_DISCREPANCY
            invoice.discrepancy_log = "\n".join(discrepancies)
            invoice.save(update_fields=['match_status', 'discrepancy_log'])
            CacheManager.invalidate_payables()
            return False, invoice.discrepancy_log

        rate = invoice.supplier.withholding_tax_rate
        wht = (invoice.gross_amount * rate).quantize(Decimal('0.0001'))
        net_payable = invoice.gross_amount - wht

        invoice.wht_amount = wht
        invoice.net_payable_amount = net_payable
        invoice.match_status = MatchStatus.MATCHED
        invoice.discrepancy_log = "3-Way Match Passed Successfully."
        invoice.save(update_fields=['wht_amount', 'net_payable_amount', 'match_status', 'discrepancy_log'])
        CacheManager.invalidate_payables()
        return True, "Match Succeeded"
