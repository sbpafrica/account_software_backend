from decimal import Decimal
from datetime import datetime
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.common.cache import CacheManager
from .models import (
    Supplier, PurchaseOrder, POLine,
    GoodsReceivedNote, GRNLine,
    SupplierInvoice, InvoiceLine, MatchStatus,
    PayeeType, PaymentMethod, PaymentVoucherStatus,
    PaymentVoucher, VoucherLine,
    ExpenseClaim, ExpenseClaimLine, ExpenseClaimStatus, ExpenseClaimType
)
from apps.treasury.models import BankAccount


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

        # Automatically post GL entry for matched bill
        PayablesService._post_supplier_bill_gl(invoice)

        invoice.save(update_fields=['wht_amount', 'net_payable_amount', 'match_status', 'discrepancy_log', 'journal_entry'])
        CacheManager.invalidate_payables()
        return True, "Match Succeeded"

    @staticmethod
    def _post_supplier_bill_gl(invoice: SupplierInvoice, user=None):
        if invoice.journal_entry:
            return

        from apps.ledger.services import LedgerService
        from apps.ledger.models import Account, AccountType

        def get_or_create(code, name, acct_type):
            acct = Account.objects.filter(code=code).first()
            if not acct:
                acct, _ = Account.objects.get_or_create(
                    code=code,
                    defaults={'name': name, 'account_type': acct_type, 'currency': 'GHS', 'country_code': invoice.supplier.country_code}
                )
            return acct

        ap_acct = get_or_create('2010-AP-GH', 'Accounts Payable (Suppliers)', AccountType.LIABILITY)
        expense_acct = get_or_create('5010-DIRECT-WORKFORCE-GH', 'Direct Workforce Delivery Expense', AccountType.DIRECT_COST)

        gl_lines = [
            {'account': expense_acct, 'debit': invoice.gross_amount, 'credit': Decimal('0'), 'country_code': invoice.supplier.country_code},
            {'account': ap_acct, 'debit': Decimal('0'), 'credit': invoice.net_payable_amount, 'country_code': invoice.supplier.country_code}
        ]

        if invoice.wht_amount > Decimal('0'):
            wht_acct = get_or_create('2020-TAX-PAYABLE-GH', 'Statutory Tax Payable (GRA/SSNIT)', AccountType.LIABILITY)
            gl_lines.append({'account': wht_acct, 'debit': Decimal('0'), 'credit': invoice.wht_amount, 'country_code': invoice.supplier.country_code})

        from django.utils import timezone
        from django.contrib.auth import get_user_model
        posting_user = user
        if not posting_user or not hasattr(posting_user, 'pk'):
            User = get_user_model()
            posting_user = User.objects.filter(is_superuser=True).first() or User.objects.first()

        posting_date = getattr(invoice, 'bill_date', None) or timezone.now().date()
        journal = LedgerService.post_journal_entry(
            entry_number=f"BILL-{invoice.supplier.id.hex[:4]}-{invoice.invoice_number}",
            posting_date=posting_date,
            description=f"Supplier Bill {invoice.invoice_number} from {invoice.supplier.name}",
            source_module="PAYABLES",
            source_ref=str(invoice.id),
            user=posting_user,
            lines_data=gl_lines
        )
        invoice.journal_entry = journal

    # -------------------------------------------------------------------------
    # PAYMENT VOUCHER LIFECYCLE
    # -------------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def voucher_create_draft(*, voucher_number: str, voucher_date, payee_name: str,
                             gross_amount: Decimal, payee_type: str = PayeeType.SUPPLIER,
                             payment_method: str = PaymentMethod.BANK_TRANSFER,
                             supplier_id=None, supplier_invoice_id=None, bank_account_id=None,
                             wht_rate: Decimal = Decimal('0.0000'), other_deductions: Decimal = Decimal('0.0000'),
                             description: str = '', department: str = '', cost_centre: str = '',
                             client_id=None, lines_data: list = None, user=None) -> PaymentVoucher:
        if PaymentVoucher.objects.filter(voucher_number=voucher_number).exists():
            raise ValidationError(f"Payment Voucher '{voucher_number}' already exists.")

        supplier = Supplier.objects.get(id=supplier_id) if supplier_id else None
        inv = SupplierInvoice.objects.get(id=supplier_invoice_id) if supplier_invoice_id else None
       
        bank_account = BankAccount.objects.get(id=bank_account_id) if bank_account_id else None

        gross_amount = Decimal(str(gross_amount))
        wht_rate = Decimal(str(wht_rate))
        other_deductions = Decimal(str(other_deductions))

        wht_amt = (gross_amount * wht_rate).quantize(Decimal('0.0001'))
        net_amt = gross_amount - wht_amt - other_deductions

        voucher = PaymentVoucher.objects.create(
            voucher_number=voucher_number,
            voucher_date=voucher_date,
            payee_name=payee_name,
            payee_type=payee_type,
            supplier=supplier,
            supplier_invoice=inv,
            payment_method=payment_method,
            bank_account=bank_account,
            description=description,
            gross_amount=gross_amount,
            wht_rate=wht_rate,
            wht_amount=wht_amt,
            other_deductions=other_deductions,
            net_amount=net_amt,
            department=department,
            cost_centre=cost_centre,
            client_id=client_id,
            status=PaymentVoucherStatus.DRAFT,
            prepared_by=user
        )

        if lines_data:
            from apps.ledger.models import Account
            for l in lines_data:
                acct = Account.objects.get(id=l['account_id'])
                VoucherLine.objects.create(
                    voucher=voucher,
                    account=acct,
                    description=l.get('description', description),
                    amount=Decimal(str(l['amount']))
                )

        CacheManager.invalidate_payables()
        return voucher

    @staticmethod
    @transaction.atomic
    def voucher_submit(*, voucher_id: str) -> PaymentVoucher:
        voucher = PaymentVoucher.objects.select_for_update().get(id=voucher_id)
        if voucher.status != PaymentVoucherStatus.DRAFT:
            raise ValidationError(f"Cannot submit voucher in '{voucher.status}' status.")
        voucher.status = PaymentVoucherStatus.SUBMITTED
        voucher.save(update_fields=['status'])
        CacheManager.invalidate_payables()

        from .tasks import send_payment_voucher_approval_alert_task
        v_id = str(voucher.id)
        transaction.on_commit(lambda: send_payment_voucher_approval_alert_task.delay(v_id))

        return voucher

    @staticmethod
    @transaction.atomic
    def voucher_review(*, voucher_id: str, user) -> PaymentVoucher:
        voucher = PaymentVoucher.objects.select_for_update().get(id=voucher_id)
        if voucher.status != PaymentVoucherStatus.SUBMITTED:
            raise ValidationError(f"Cannot review voucher in '{voucher.status}' status.")
        voucher.status = PaymentVoucherStatus.REVIEWED
        voucher.reviewed_by = user
        voucher.save(update_fields=['status', 'reviewed_by'])
        CacheManager.invalidate_payables()
        return voucher

    @staticmethod
    @transaction.atomic
    def voucher_approve(*, voucher_id: str, user) -> PaymentVoucher:
        voucher = PaymentVoucher.objects.select_for_update().get(id=voucher_id)
        if voucher.status not in [PaymentVoucherStatus.SUBMITTED, PaymentVoucherStatus.REVIEWED]:
            raise ValidationError(f"Cannot approve voucher in '{voucher.status}' status.")
        if voucher.prepared_by and voucher.prepared_by == user and not getattr(user, 'is_superuser', False):
            raise ValidationError("Segregation of duties violation: Preparer cannot approve their own payment voucher.")
        voucher.status = PaymentVoucherStatus.APPROVED
        voucher.approved_by = user
        voucher.save(update_fields=['status', 'approved_by'])
        CacheManager.invalidate_payables()
        return voucher

    @staticmethod
    @transaction.atomic
    def voucher_reject(*, voucher_id: str, user, reason: str) -> PaymentVoucher:
        voucher = PaymentVoucher.objects.select_for_update().get(id=voucher_id)
        if voucher.status in [PaymentVoucherStatus.PAID, PaymentVoucherStatus.REVERSED]:
            raise ValidationError(f"Cannot reject voucher in '{voucher.status}' status.")
        voucher.status = PaymentVoucherStatus.REJECTED
        voucher.rejection_reason = reason
        voucher.save(update_fields=['status', 'rejection_reason'])
        CacheManager.invalidate_payables()
        return voucher

    @staticmethod
    @transaction.atomic
    def voucher_mark_paid(*, voucher_id: str, user, payment_date=None, bank_account_id=None, reference_number: str = None) -> PaymentVoucher:
        voucher = PaymentVoucher.objects.select_for_update().get(id=voucher_id)
        if voucher.status == PaymentVoucherStatus.PAID:
            raise ValidationError("Voucher has already been paid and posted.")
        if voucher.status != PaymentVoucherStatus.APPROVED:
            raise ValidationError(f"Voucher must be APPROVED before payment. Current status: '{voucher.status}'.")

        from apps.treasury.models import BankAccount
        from apps.ledger.services import LedgerService
        from apps.ledger.models import Account, AccountType
        from django.utils import timezone

        if bank_account_id:
            voucher.bank_account = BankAccount.objects.get(id=bank_account_id)
        if not voucher.bank_account:
            raise ValidationError("Payment voucher must specify a bank account for payment execution.")

        if payment_date:
            voucher.payment_date = payment_date
        else:
            voucher.payment_date = timezone.now().date()

        if reference_number:
            voucher.reference_number = reference_number

        def get_or_create(code, name, acct_type):
            acct = Account.objects.filter(code=code).first()
            if not acct:
                acct, _ = Account.objects.get_or_create(
                    code=code,
                    defaults={'name': name, 'account_type': acct_type, 'currency': 'GHS', 'country_code': 'GH'}
                )
            return acct

        bank_gl = voucher.bank_account.gl_account

        # Build GL lines
        if voucher.supplier_invoice:
            # Settling an existing supplier bill
            ap_acct = get_or_create('2010-AP-GH', 'Accounts Payable (Suppliers)', AccountType.LIABILITY)
            gl_lines = [
                {'account': ap_acct, 'debit': voucher.net_amount, 'credit': Decimal('0'), 'cost_centre': voucher.cost_centre},
                {'account': bank_gl, 'debit': Decimal('0'), 'credit': voucher.net_amount, 'cost_centre': voucher.cost_centre}
            ]
            # Update invoice paid balance
            inv = voucher.supplier_invoice
            inv.amount_paid += voucher.net_amount
            if inv.amount_paid >= inv.net_payable_amount:
                inv.match_status = MatchStatus.PAID
            inv.save(update_fields=['amount_paid', 'match_status'])
        else:
            # Direct expense payment or disbursement
            lines = list(voucher.lines.all())
            if lines:
                gl_lines = [
                    {'account': l.account, 'debit': l.amount, 'credit': Decimal('0'), 'cost_centre': voucher.cost_centre}
                    for l in lines
                ]
                gl_lines.append(
                    {'account': bank_gl, 'debit': Decimal('0'), 'credit': voucher.net_amount, 'cost_centre': voucher.cost_centre}
                )
            else:
                exp_acct = voucher.expense_account or get_or_create('6010-OFFICE-RENT-GH', 'Operating Expense', AccountType.OPEX)
                gl_lines = [
                    {'account': exp_acct, 'debit': voucher.gross_amount, 'credit': Decimal('0'), 'cost_centre': voucher.cost_centre},
                    {'account': bank_gl, 'debit': Decimal('0'), 'credit': voucher.net_amount, 'cost_centre': voucher.cost_centre}
                ]
            if voucher.wht_amount > Decimal('0'):
                wht_acct = get_or_create('2020-TAX-PAYABLE-GH', 'Statutory Tax Payable (GRA/SSNIT)', AccountType.LIABILITY)
                gl_lines.append({'account': wht_acct, 'debit': Decimal('0'), 'credit': voucher.wht_amount, 'cost_centre': voucher.cost_centre})

        journal = LedgerService.post_journal_entry(
            entry_number=f"PV-{voucher.voucher_number}",
            posting_date=voucher.payment_date,
            description=f"Payment Voucher {voucher.voucher_number}: {voucher.description}",
            source_module="PAYABLES",
            source_ref=str(voucher.id),
            user=user,
            lines_data=gl_lines
        )

        voucher.status = PaymentVoucherStatus.PAID
        voucher.journal_entry = journal
        voucher.save(update_fields=['status', 'payment_date', 'reference_number', 'bank_account', 'journal_entry'])

        CacheManager.invalidate_payables()
        CacheManager.invalidate_treasury()

        from .tasks import send_remittance_advice_email_task
        v_id = str(voucher.id)
        transaction.on_commit(lambda: send_remittance_advice_email_task.delay(v_id))

        return voucher

    # ========================================================================
    # EMPLOYEE EXPENSE CLAIMS & ADVANCE RETIREMENT
    # ========================================================================

    @staticmethod
    @transaction.atomic
    def expense_claim_create(*, employee_id: str, claim_date,
                             claim_type: str = ExpenseClaimType.REIMBURSEMENT,
                             advance_amount: Decimal = Decimal('0.0000'),
                             department: str = '', cost_centre: str = '',
                             notes: str = '', lines_data: list = None,
                             country_code: str = 'GH', user=None) -> ExpenseClaim:
        from apps.users.models import User
        employee = User.objects.get(id=employee_id)
        claim_number = f"EXP-{employee.email.split('@')[0].upper()[:4]}-{claim_date.strftime('%Y%m%d')}-{datetime.now().strftime('%H%M%S')}"

        advance_amount = Decimal(str(advance_amount))
        claim = ExpenseClaim.objects.create(
            claim_number=claim_number,
            claim_date=claim_date,
            employee=employee,
            claim_type=claim_type,
            advance_amount=advance_amount,
            status=ExpenseClaimStatus.DRAFT,
            department=department,
            cost_centre=cost_centre,
            notes=notes,
            country_code=country_code
        )

        total_exp = Decimal('0.0000')
        created_lines = []
        if lines_data:
            from apps.ledger.models import Account
            for row in lines_data:
                amt = Decimal(str(row['amount']))
                exp_acc = Account.objects.get(id=row['expense_account_id'])
                created_lines.append(
                    ExpenseClaimLine(
                        claim=claim,
                        expense_date=row.get('expense_date', claim_date),
                        category=row.get('category', 'General Expense'),
                        expense_account=exp_acc,
                        description=row.get('description', ''),
                        amount=amt,
                        receipt_reference=row.get('receipt_reference', '')
                    )
                )
                total_exp += amt

        ExpenseClaimLine.objects.bulk_create(created_lines)

        if claim_type == ExpenseClaimType.REIMBURSEMENT:
            net_payable = total_exp
        elif claim_type == ExpenseClaimType.CASH_ADVANCE:
            net_payable = advance_amount
        else:  # RETIREMENT
            net_payable = total_exp - advance_amount

        claim.total_expenses = total_exp
        claim.net_payable_to_employee = net_payable
        claim.save(update_fields=['total_expenses', 'net_payable_to_employee'])

        CacheManager.invalidate_payables()
        return claim

    @staticmethod
    @transaction.atomic
    def expense_claim_submit(*, claim_id: str, user) -> ExpenseClaim:
        claim = ExpenseClaim.objects.select_for_update().get(id=claim_id)
        if claim.status != ExpenseClaimStatus.DRAFT:
            raise ValidationError(f"Cannot submit claim with status {claim.status}.")
        claim.status = ExpenseClaimStatus.SUBMITTED
        claim.save(update_fields=['status'])
        CacheManager.invalidate_payables()
        return claim

    @staticmethod
    @transaction.atomic
    def expense_claim_approve(*, claim_id: str, user) -> ExpenseClaim:
        claim = ExpenseClaim.objects.select_for_update().get(id=claim_id)
        if claim.status != ExpenseClaimStatus.SUBMITTED:
            raise ValidationError(f"Cannot approve claim with status {claim.status}.")
        # Segregation of duties: Employee cannot approve their own claim!
        if claim.employee == user and not user.is_superuser:
            raise ValidationError("Segregation of duties violation: You cannot approve your own expense claim.")

        claim.status = ExpenseClaimStatus.APPROVED
        claim.approved_by = user
        claim.save(update_fields=['status', 'approved_by'])
        CacheManager.invalidate_payables()
        return claim

    @staticmethod
    @transaction.atomic
    def expense_claim_reject(*, claim_id: str, reason: str, user) -> ExpenseClaim:
        claim = ExpenseClaim.objects.select_for_update().get(id=claim_id)
        claim.status = ExpenseClaimStatus.REJECTED
        claim.notes = f"{claim.notes}\nRejection reason: {reason}".strip()
        claim.save(update_fields=['status', 'notes'])
        CacheManager.invalidate_payables()
        return claim

    @staticmethod
    @transaction.atomic
    def expense_claim_settle(*, claim_id: str, bank_account_id: str = None, user=None) -> ExpenseClaim:
        """
        Settles approved expense claim by generating a payment voucher or posting retirement entries.
        """
        claim = ExpenseClaim.objects.select_for_update().get(id=claim_id)
        if claim.status != ExpenseClaimStatus.APPROVED:
            raise ValidationError("Only approved claims can be settled.")

        # Create Payment Voucher for disbursement
        if claim.net_payable_to_employee > Decimal('0.0000'):
            v_number = f"PV-EXP-{claim.claim_number}"
            lines_data = [
                {
                    'account_id': str(line.expense_account_id),
                    'description': line.description,
                    'amount': line.amount
                }
                for line in claim.lines.all()
            ]
            voucher = PayablesService.voucher_create_draft(
                voucher_number=v_number,
                voucher_date=timezone.now().date(),
                payee_name=f"{claim.employee.first_name} {claim.employee.last_name} ({claim.employee.email})",
                gross_amount=claim.net_payable_to_employee,
                payee_type=PayeeType.EMPLOYEE,
                bank_account_id=bank_account_id,
                description=f"Settlement of Expense Claim {claim.claim_number}",
                department=claim.department,
                cost_centre=claim.cost_centre,
                lines_data=lines_data if lines_data else None,
                user=claim.employee
            )
            # Mark submitted, reviewed, approved and paid if bank provided
            PayablesService.voucher_submit(voucher_id=voucher.id)
            PayablesService.voucher_review(voucher_id=voucher.id, user=user)
            PayablesService.voucher_approve(voucher_id=voucher.id, user=user)
            if bank_account_id:
                PayablesService.voucher_mark_paid(
                    voucher_id=voucher.id,
                    bank_account_id=bank_account_id,
                    reference_number=f"EXP-DISB-{claim.id.hex[:6]}",
                    user=user
                )
            claim.settlement_voucher = voucher

        claim.status = ExpenseClaimStatus.PAID
        claim.save(update_fields=['status', 'settlement_voucher'])
        CacheManager.invalidate_payables()
        return claim


