from decimal import Decimal
from django.db import transaction
from apps.common.cache import CacheManager
from .models import BankTransaction


class TreasuryService:
    @staticmethod
    @transaction.atomic
    def reconcile_transaction(*, transaction_id: str) -> BankTransaction:
        tx = BankTransaction.objects.select_for_update().get(id=transaction_id)
        tx.is_reconciled = True
        tx.save(update_fields=['is_reconciled'])
        CacheManager.invalidate_treasury()
        return tx
