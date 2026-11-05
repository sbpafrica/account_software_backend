from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.common.cache import CacheManager
from .models import Client, ClientInvoice, ClientInvoiceStatus

class ReceivablesService:
    @staticmethod
    @transaction.atomic
    def client_create(*, name: str, code: str, country_code: str = 'GH',
                      credit_limit: Decimal = Decimal('50000.0000'), payment_terms_days: int = 30) -> Client:
        return Client.objects.create(
            name=name,
            code=code,
            country_code=country_code,
            credit_limit=credit_limit,
            payment_terms_days=payment_terms_days
        )

    @staticmethod
    @transaction.atomic
    def invoice_create(*, invoice_number: str, client: Client, issue_date, due_date, total_amount: Decimal) -> ClientInvoice:
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
