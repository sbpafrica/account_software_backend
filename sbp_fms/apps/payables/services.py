from decimal import Decimal
from django.db import transaction
from apps.common.cache import CacheManager
from .models import Supplier, SupplierInvoice, MatchStatus


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
