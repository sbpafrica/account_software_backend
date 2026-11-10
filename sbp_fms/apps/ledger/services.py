from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.common.cache import CacheManager
from .models import JournalEntry, JournalLine, JournalEntryStatus, Account

class LedgerService:
    @staticmethod
    @transaction.atomic
    def account_create(*, code: str, name: str, account_type: str, currency: str = 'GHS',
                       country_code: str = 'GH', description: str = '') -> Account:
        if Account.objects.filter(code=code).exists():
            raise ValidationError(f"Account code '{code}' already exists.")
        account = Account.objects.create(
            code=code,
            name=name,
            account_type=account_type,
            currency=currency,
            country_code=country_code,
            description=description
        )
        CacheManager.delete_pattern("fms:accounts:")
        return account

    @staticmethod

    @transaction.atomic
    def account_update(*, account_id, name: str = None, account_type: str = None,
                       currency: str = None, country_code: str = None,
                       is_active: bool = None, description: str = None) -> Account:
        account = Account.objects.select_for_update().get(id=account_id)
        if name is not None:
            account.name = name.strip()
        if account_type is not None:
            account.account_type = account_type
        if currency is not None:
            account.currency = currency
        if country_code is not None:
            account.country_code = country_code
        if is_active is not None:
            account.is_active = is_active
        if description is not None:
            account.description = description
        account.save()
        CacheManager.delete_pattern("fms:accounts:")
        return account

    @staticmethod
    @transaction.atomic
    def account_delete(*, account_id) -> None:
        account = Account.objects.get(id=account_id)
        if account.journal_lines.exists():
            raise ValidationError(f"Cannot delete account '{account.code}' because it has journal entries.")
        account.delete()
        CacheManager.delete_pattern("fms:accounts:")

    @staticmethod
    @transaction.atomic
    def journal_entry_delete(*, entry_id) -> None:
        entry = JournalEntry.objects.get(id=entry_id)
        if entry.status == JournalEntryStatus.POSTED:
            raise ValidationError("Posted journal entries cannot be deleted. Use reverse instead.")
        entry.delete()
        CacheManager.invalidate_ledger()


    @staticmethod
    @transaction.atomic
    def post_journal_entry(*, entry_number: str, posting_date, description: str,
                           source_module: str, source_ref: str, user, lines_data: list) -> JournalEntry:
        if not lines_data or len(lines_data) < 2:
            raise ValidationError("A valid journal entry requires at least two lines.")

        total_debits = sum(Decimal(str(line.get('debit', 0))) for line in lines_data)
        total_credits = sum(Decimal(str(line.get('credit', 0))) for line in lines_data)

        if total_debits != total_credits:
            diff = total_debits - total_credits
            raise ValidationError(
                f"Double-entry balance check failed! Debits ({total_debits}) != Credits ({total_credits}). Imbalance: {diff}"
            )

        entry = JournalEntry.objects.create(
            entry_number=entry_number,
            posting_date=posting_date,
            description=description,
            source_module=source_module,
            source_reference_id=source_ref,
            created_by=user,
            approved_by=user,
            status=JournalEntryStatus.POSTED
        )

        lines = [
            JournalLine(
                entry=entry,
                account=line['account'],
                debit=Decimal(str(line.get('debit', 0))),
                credit=Decimal(str(line.get('credit', 0))),
                client_id=line.get('client_id'),
                cost_centre=line.get('cost_centre'),
                country_code=line.get('country_code', 'GH')
            )
            for line in lines_data
        ]
        JournalLine.objects.bulk_create(lines)

        # Cache Invalidation: Invalidate all trial balance and cash forecast caches!
        CacheManager.invalidate_ledger()
        return entry

    @staticmethod
    @transaction.atomic
    def reverse_journal_entry(*, entry_id: str, user, reason: str) -> JournalEntry:
        original = JournalEntry.objects.select_for_update().get(id=entry_id)
        if original.status != JournalEntryStatus.POSTED:
            raise ValidationError("Only POSTED entries can be reversed.")

        reversal_lines = [
            {
                'account': line.account,
                'debit': line.credit,
                'credit': line.debit,
                'client_id': line.client_id,
                'cost_centre': line.cost_centre,
                'country_code': line.country_code
            }
            for line in original.lines.all()
        ]

        reversal_entry = LedgerService.post_journal_entry(
            entry_number=f"REV-{original.entry_number}",
            posting_date=timezone.now().date(),
            description=f"Reversal of {original.entry_number}: {reason}",
            source_module="REVERSAL",
            source_ref=str(original.id),
            user=user,
            lines_data=reversal_lines
        )

        original.status = JournalEntryStatus.REVERSED
        original.save(update_fields=['status'])

        # Cache Invalidation
        CacheManager.invalidate_ledger()
        return reversal_entry
