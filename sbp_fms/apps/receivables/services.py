from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.common.cache import CacheManager
from apps.ledger.services import LedgerService
from apps.ledger.models import Account, AccountType
from .models import (
    Client, ClientInvoice, ClientInvoiceStatus,
    ClientInvoiceLine, PaymentReceipt, PaymentReceiptStatus, ReceiptAllocation
)


def _get_or_create_account(code: str, name: str, acct_type: str, country_code: str = 'GH') -> Account:
    acct = Account.objects.filter(code=code).first()
    if not acct:
        acct, _ = Account.objects.get_or_create(
            code=code,
            defaults={'name': name, 'account_type': acct_type, 'currency': 'GHS', 'country_code': country_code}
        )
    return acct


class ReceivablesService:
    @staticmethod
    @transaction.atomic
    def client_create(*, name: str, code: str, country_code: str = 'GH',
                      credit_limit: Decimal = Decimal('50000.0000'), payment_terms_days: int = 30,
                      category: str = 'CORPORATE', tax_id: str = '', registration_number: str = '',
                      contact_person: str = '', telephone: str = '', email: str = '',
                      billing_address: str = '', opening_balance: Decimal = Decimal('0.0000')) -> Client:
        if Client.objects.filter(code=code).exists():
            raise ValidationError(f"Client code '{code}' already exists.")
        client = Client.objects.create(
            name=name,
            code=code,
            country_code=country_code,
            credit_limit=credit_limit,
            payment_terms_days=payment_terms_days,
            category=category,
            tax_id=tax_id,
            registration_number=registration_number,
            contact_person=contact_person,
            telephone=telephone,
            email=email,
            billing_address=billing_address,
            opening_balance=opening_balance
        )
        CacheManager.invalidate_receivables()
        return client

    @staticmethod
    @transaction.atomic
    def client_update(*, client_id, name: str = None, code: str = None,
                      country_code: str = None, credit_limit: Decimal = None,
                      payment_terms_days: int = None, **extra_fields) -> Client:
        client = Client.objects.select_for_update().get(id=client_id)
        if name is not None:
            client.name = name.strip()
        if code is not None:
            code = code.strip()
            if Client.objects.filter(code=code).exclude(id=client_id).exists():
                raise ValidationError(f"Client code '{code}' is already in use.")
            client.code = code
        if country_code is not None:
            client.country_code = country_code
        if credit_limit is not None:
            client.credit_limit = credit_limit
        if payment_terms_days is not None:
            client.payment_terms_days = payment_terms_days
        for k, v in extra_fields.items():
            if hasattr(client, k) and v is not None:
                setattr(client, k, v)
        client.save()
        CacheManager.invalidate_receivables()
        return client

    @staticmethod
    @transaction.atomic
    def client_delete(*, client_id) -> None:
        client = Client.objects.get(id=client_id)
        if client.invoices.exists():
            raise ValidationError(f"Cannot delete client '{client.name}' because invoices exist for this client.")
        client.delete()
        CacheManager.invalidate_receivables()

    @staticmethod
    @transaction.atomic
    def invoice_create(*, invoice_number: str, client: Client, issue_date, due_date,
                       total_amount: Decimal = None, lines_data: list = None,
                       status: str = ClientInvoiceStatus.ISSUED, user=None) -> ClientInvoice:
        if ClientInvoice.objects.filter(invoice_number=invoice_number).exists():
            raise ValidationError(f"Invoice number '{invoice_number}' already exists.")

        subtotal = Decimal('0.0000')
        tax_total = Decimal('0.0000')
        discount_total = Decimal('0.0000')

        if lines_data:
            for line in lines_data:
                qty = Decimal(str(line.get('quantity', 1)))
                unit_price = Decimal(str(line.get('unit_price', 0)))
                disc = Decimal(str(line.get('discount', 0)))
                rate = Decimal(str(line.get('tax_rate', 0)))
                line_sub = (qty * unit_price) - disc
                line_tax = (line_sub * rate).quantize(Decimal('0.0001'))
                subtotal += line_sub
                tax_total += line_tax
                discount_total += disc
            calc_total = subtotal + tax_total
        else:
            calc_total = total_amount if total_amount is not None else Decimal('0.0000')
            subtotal = calc_total

        inv = ClientInvoice.objects.create(
            invoice_number=invoice_number,
            client=client,
            issue_date=issue_date,
            due_date=due_date,
            subtotal=subtotal,
            tax_amount=tax_total,
            discount_amount=discount_total,
            total_amount=calc_total,
            status=status,
            created_by=user
        )

        if lines_data:
            for line in lines_data:
                qty = Decimal(str(line.get('quantity', 1)))
                unit_price = Decimal(str(line.get('unit_price', 0)))
                disc = Decimal(str(line.get('discount', 0)))
                rate = Decimal(str(line.get('tax_rate', 0)))
                line_sub = (qty * unit_price) - disc
                line_tax = (line_sub * rate).quantize(Decimal('0.0001'))
                ClientInvoiceLine.objects.create(
                    invoice=inv,
                    description=line.get('description', 'Service Item'),
                    quantity=qty,
                    unit_of_measurement=line.get('unit_of_measurement', 'Unit'),
                    unit_price=unit_price,
                    discount=disc,
                    tax_code=line.get('tax_code', 'EXEMPT'),
                    tax_rate=rate,
                    tax_amount=line_tax,
                    line_total=line_sub + line_tax
                )

        if status == ClientInvoiceStatus.ISSUED:
            ReceivablesService._post_invoice_gl(inv, user=user)
            from .tasks import send_invoice_email_task
            inv_id = str(inv.id)
            transaction.on_commit(lambda: send_invoice_email_task.delay(inv_id))

        CacheManager.invalidate_receivables()
        return inv

    @staticmethod
    def _post_invoice_gl(inv: ClientInvoice, user=None):
        if inv.journal_entry:
            return

        ar_acct = _get_or_create_account('1100-AR-GH', 'Accounts Receivable (Clients)', AccountType.ASSET, inv.client.country_code)
        rev_acct = _get_or_create_account('4010-EOR-FEES-GH', 'EOR & HR Management Fee Revenue', AccountType.REVENUE, inv.client.country_code)

        gl_lines = [
            {'account': ar_acct, 'debit': inv.total_amount, 'credit': Decimal('0'), 'client_id': inv.client.id, 'country_code': inv.client.country_code}
        ]

        if inv.tax_amount > Decimal('0'):
            tax_acct = _get_or_create_account('2020-TAX-PAYABLE-GH', 'Statutory Tax Payable (GRA/SSNIT)', AccountType.LIABILITY, inv.client.country_code)
            gl_lines.append({'account': rev_acct, 'debit': Decimal('0'), 'credit': inv.subtotal, 'client_id': inv.client.id, 'country_code': inv.client.country_code})
            gl_lines.append({'account': tax_acct, 'debit': Decimal('0'), 'credit': inv.tax_amount, 'client_id': inv.client.id, 'country_code': inv.client.country_code})
        else:
            gl_lines.append({'account': rev_acct, 'debit': Decimal('0'), 'credit': inv.total_amount, 'client_id': inv.client.id, 'country_code': inv.client.country_code})

        journal = LedgerService.post_journal_entry(
            entry_number=f"INV-{inv.invoice_number}",
            posting_date=inv.issue_date,
            description=f"Client Invoice {inv.invoice_number} to {inv.client.name}",
            source_module="RECEIVABLES",
            source_ref=str(inv.id),
            user=user or inv.created_by,
            lines_data=gl_lines
        )
        inv.journal_entry = journal
        inv.save(update_fields=['journal_entry'])

    @staticmethod
    @transaction.atomic
    def invoice_issue(*, invoice_id: str, user=None) -> ClientInvoice:
        inv = ClientInvoice.objects.select_for_update().get(id=invoice_id)
        if inv.status == ClientInvoiceStatus.ISSUED:
            return inv
        inv.status = ClientInvoiceStatus.ISSUED
        ReceivablesService._post_invoice_gl(inv, user=user)
        inv.save(update_fields=['status'])
        CacheManager.invalidate_receivables()

        from .tasks import send_invoice_email_task
        inv_id = str(inv.id)
        transaction.on_commit(lambda: send_invoice_email_task.delay(inv_id))

        return inv

    @staticmethod
    @transaction.atomic
    def invoice_update(*, invoice_id, issue_date=None, due_date=None,
                       total_amount: Decimal = None, amount_paid: Decimal = None,
                       status: str = None) -> ClientInvoice:
        inv = ClientInvoice.objects.select_for_update().get(id=invoice_id)
        if issue_date is not None:
            inv.issue_date = issue_date
        if due_date is not None:
            inv.due_date = due_date
        if total_amount is not None:
            inv.total_amount = total_amount
        if amount_paid is not None:
            inv.amount_paid = amount_paid
            if inv.amount_paid >= inv.total_amount:
                inv.status = ClientInvoiceStatus.PAID
            elif inv.amount_paid > Decimal('0.0000'):
                inv.status = ClientInvoiceStatus.PARTIALLY_PAID
        if status is not None:
            inv.status = status
        inv.save()
        CacheManager.invalidate_receivables()
        return inv

    @staticmethod
    @transaction.atomic
    def invoice_delete(*, invoice_id) -> None:
        inv = ClientInvoice.objects.get(id=invoice_id)
        if inv.status in [ClientInvoiceStatus.PAID, ClientInvoiceStatus.PARTIALLY_PAID]:
            raise ValidationError("Cannot delete an invoice that has payments allocated to it.")
        if inv.journal_entry:
            raise ValidationError("Cannot delete an invoice that has posted accounting journals.")
        inv.delete()
        CacheManager.invalidate_receivables()

    @staticmethod
    @transaction.atomic
    def receipt_create_and_allocate(*, receipt_number: str, client_id, amount_received: Decimal,
                                    bank_account_id, receipt_date=None, payment_method: str = 'BANK_TRANSFER',
                                    reference_number: str = '', description: str = '',
                                    allocations_data: list = None, user=None) -> PaymentReceipt:
        if PaymentReceipt.objects.filter(receipt_number=receipt_number).exists():
            raise ValidationError(f"Receipt number '{receipt_number}' already exists.")

        client = Client.objects.get(id=client_id)
        from apps.treasury.models import BankAccount
        bank_account = BankAccount.objects.get(id=bank_account_id)

        receipt = PaymentReceipt.objects.create(
            receipt_number=receipt_number,
            receipt_date=receipt_date or timezone.now().date(),
            client=client,
            amount_received=amount_received,
            payment_method=payment_method,
            bank_account=bank_account,
            reference_number=reference_number,
            description=description,
            unallocated_amount=amount_received,
            status=PaymentReceiptStatus.CONFIRMED,
            created_by=user
        )

        total_allocated = Decimal('0.0000')
        if allocations_data:
            for item in allocations_data:
                inv = ClientInvoice.objects.select_for_update().get(id=item['invoice_id'])
                alloc_amt = Decimal(str(item['amount']))
                if alloc_amt > inv.balance_due:
                    raise ValidationError(f"Allocated amount {alloc_amt} exceeds balance due {inv.balance_due} for invoice {inv.invoice_number}")
                ReceiptAllocation.objects.create(
                    receipt=receipt,
                    invoice=inv,
                    amount_allocated=alloc_amt
                )
                inv.amount_paid += alloc_amt
                if inv.amount_paid >= inv.total_amount:
                    inv.status = ClientInvoiceStatus.PAID
                else:
                    inv.status = ClientInvoiceStatus.PARTIALLY_PAID
                inv.save(update_fields=['amount_paid', 'status'])
                total_allocated += alloc_amt

        unallocated = amount_received - total_allocated
        receipt.unallocated_amount = unallocated
        receipt.save(update_fields=['unallocated_amount'])

        # Post Receipt Double Entry to GL
        ar_acct = _get_or_create_account('1100-AR-GH', 'Accounts Receivable (Clients)', AccountType.ASSET, client.country_code)
        bank_gl = bank_account.gl_account

        gl_lines = [
            {'account': bank_gl, 'debit': amount_received, 'credit': Decimal('0'), 'client_id': client.id, 'country_code': client.country_code}
        ]

        if total_allocated > Decimal('0'):
            gl_lines.append({'account': ar_acct, 'debit': Decimal('0'), 'credit': total_allocated, 'client_id': client.id, 'country_code': client.country_code})

        if unallocated > Decimal('0'):
            unearned_acct = _get_or_create_account('2150-CUSTOMER-ADVANCES', 'Customer Advances / Unearned Revenue', AccountType.LIABILITY, client.country_code)
            gl_lines.append({'account': unearned_acct, 'debit': Decimal('0'), 'credit': unallocated, 'client_id': client.id, 'country_code': client.country_code})

        journal = LedgerService.post_journal_entry(
            entry_number=f"REC-{receipt.receipt_number}",
            posting_date=receipt.receipt_date,
            description=f"Payment Receipt {receipt.receipt_number} from {client.name}",
            source_module="RECEIVABLES",
            source_ref=str(receipt.id),
            user=user,
            lines_data=gl_lines
        )
        receipt.journal_entry = journal
        receipt.save(update_fields=['journal_entry'])

        CacheManager.invalidate_receivables()
        CacheManager.invalidate_treasury()

        from .tasks import send_payment_receipt_email_task
        rec_id = str(receipt.id)
        transaction.on_commit(lambda: send_payment_receipt_email_task.delay(rec_id))

        return receipt

