from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.common.cache import CacheManager
from .models import Client, ClientInvoice, ClientInvoiceStatus


class ReceivablesService:
    @staticmethod
    @transaction.atomic
    def client_create(*, name: str, code: str, country_code: str = 'GH',
                      credit_limit: Decimal = Decimal('50000.0000'), payment_terms_days: int = 30) -> Client:
        if Client.objects.filter(code=code).exists():
            raise ValidationError(f"Client code '{code}' already exists.")
        client = Client.objects.create(
            name=name,
            code=code,
            country_code=country_code,
            credit_limit=credit_limit,
            payment_terms_days=payment_terms_days
        )
        CacheManager.invalidate_receivables()
        return client

    @staticmethod
    @transaction.atomic
    def client_update(*, client_id, name: str = None, code: str = None,
                      country_code: str = None, credit_limit: Decimal = None,
                      payment_terms_days: int = None) -> Client:
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
    def invoice_create(*, invoice_number: str, client: Client, issue_date, due_date, total_amount: Decimal) -> ClientInvoice:
        if ClientInvoice.objects.filter(invoice_number=invoice_number).exists():
            raise ValidationError(f"Invoice number '{invoice_number}' already exists.")
        inv = ClientInvoice.objects.create(
            invoice_number=invoice_number,
            client=client,
            issue_date=issue_date,
            due_date=due_date,
            total_amount=total_amount,
            status=ClientInvoiceStatus.ISSUED
        )
        CacheManager.invalidate_receivables()
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
        inv.delete()
        CacheManager.invalidate_receivables()
