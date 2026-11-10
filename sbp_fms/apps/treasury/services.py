from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.common.cache import CacheManager
from apps.ledger.models import Account
from .models import BankAccount, BankTransaction


class TreasuryService:
    @staticmethod
    @transaction.atomic
    def bank_account_create(*, bank_name: str, account_number: str, gl_account_id,
                            currency: str = 'GHS', country_code: str = 'GH') -> BankAccount:
        if BankAccount.objects.filter(account_number=account_number).exists():
            raise ValidationError(f"Bank account '{account_number}' already exists.")
        gl_account = Account.objects.get(id=gl_account_id)
        if hasattr(gl_account, 'bank_account'):
            raise ValidationError(f"GL Account '{gl_account.code}' is already linked to a bank account.")
        account = BankAccount.objects.create(
            bank_name=bank_name.strip(),
            account_number=account_number.strip(),
            currency=currency.strip().upper(),
            country_code=country_code.strip().upper(),
            gl_account=gl_account
        )
        CacheManager.invalidate_treasury()
        return account

    @staticmethod
    @transaction.atomic
    def bank_account_update(*, account_id, bank_name: str = None,
                            currency: str = None, country_code: str = None) -> BankAccount:
        account = BankAccount.objects.select_for_update().get(id=account_id)
        if bank_name is not None:
            account.bank_name = bank_name.strip()
        if currency is not None:
            account.currency = currency.strip().upper()
        if country_code is not None:
            account.country_code = country_code.strip().upper()
        account.save()
        CacheManager.invalidate_treasury()
        return account

    @staticmethod
    @transaction.atomic
    def bank_account_delete(*, account_id) -> None:
        account = BankAccount.objects.get(id=account_id)
        if account.transactions.exists():
            raise ValidationError(f"Cannot delete bank account '{account.account_number}' with recorded transactions.")
        account.delete()
        CacheManager.invalidate_treasury()

    @staticmethod
    @transaction.atomic
    def bank_transaction_create(*, bank_account_id, transaction_date, bank_reference: str,
                                description: str, amount: Decimal, is_reconciled: bool = False) -> BankTransaction:
        bank_account = BankAccount.objects.get(id=bank_account_id)
        tx = BankTransaction.objects.create(
            bank_account=bank_account,
            transaction_date=transaction_date,
            bank_reference=bank_reference.strip(),
            description=description.strip(),
            amount=amount,
            is_reconciled=is_reconciled
        )
        CacheManager.invalidate_treasury()
        return tx

    @staticmethod
    @transaction.atomic
    def bank_transaction_update(*, transaction_id, transaction_date=None,
                                description: str = None, amount: Decimal = None,
                                is_reconciled: bool = None) -> BankTransaction:
        tx = BankTransaction.objects.select_for_update().get(id=transaction_id)
        if transaction_date is not None:
            tx.transaction_date = transaction_date
        if description is not None:
            tx.description = description.strip()
        if amount is not None:
            tx.amount = amount
        if is_reconciled is not None:
            tx.is_reconciled = is_reconciled
        tx.save()
        CacheManager.invalidate_treasury()
        return tx

    @staticmethod
    @transaction.atomic
    def bank_transaction_delete(*, transaction_id) -> None:
        tx = BankTransaction.objects.get(id=transaction_id)
        if tx.is_reconciled:
            raise ValidationError("Cannot delete a reconciled bank transaction.")
        tx.delete()
        CacheManager.invalidate_treasury()

    @staticmethod
    @transaction.atomic
    def reconcile_transaction(*, transaction_id: str) -> BankTransaction:
        tx = BankTransaction.objects.select_for_update().get(id=transaction_id)
        tx.is_reconciled = True
        tx.save(update_fields=['is_reconciled'])
        CacheManager.invalidate_treasury()
        return tx
