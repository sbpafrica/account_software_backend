from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.common.cache import CacheManager
from apps.ledger.services import LedgerService
from apps.ledger.models import Account
from .models import PayrollBatch, PayrollBatchStatus
from .selectors import client_escrow_balance_get


class PayrollEscrowService:
    @staticmethod
    @transaction.atomic
    def payroll_batch_create(*, batch_code: str, client_id, client_name: str,
                             country_code: str, month: int, year: int,
                             total_net_salaries: Decimal, total_statutory_taxes: Decimal,
                             total_management_fee: Decimal) -> PayrollBatch:
        batch = PayrollBatch.objects.create(
            batch_code=batch_code,
            client_id=client_id,
            client_name=client_name,
            country_code=country_code,
            month=month,
            year=year,
            total_net_salaries=total_net_salaries,
            total_statutory_taxes=total_statutory_taxes,
            total_management_fee=total_management_fee,
            status=PayrollBatchStatus.DRAFT
        )
        CacheManager.invalidate_payroll()
        return batch

    @staticmethod
    @transaction.atomic
    def payroll_batch_update(*, batch_id, client_name: str = None, month: int = None,
                             year: int = None, total_net_salaries: Decimal = None,
                             total_statutory_taxes: Decimal = None,
                             total_management_fee: Decimal = None,
                             status: str = None) -> PayrollBatch:
        batch = PayrollBatch.objects.select_for_update().get(id=batch_id)
        if batch.status == PayrollBatchStatus.DISBURSED:
            raise ValidationError("Cannot modify a disbursed payroll batch.")
        if client_name is not None:
            batch.client_name = client_name.strip()
        if month is not None:
            batch.month = month
        if year is not None:
            batch.year = year
        if total_net_salaries is not None:
            batch.total_net_salaries = total_net_salaries
        if total_statutory_taxes is not None:
            batch.total_statutory_taxes = total_statutory_taxes
        if total_management_fee is not None:
            batch.total_management_fee = total_management_fee
        if status is not None:
            batch.status = status
        batch.save()
        CacheManager.invalidate_payroll()
        return batch

    @staticmethod
    @transaction.atomic
    def payroll_batch_delete(*, batch_id) -> None:
        batch = PayrollBatch.objects.get(id=batch_id)
        if batch.status == PayrollBatchStatus.DISBURSED:
            raise ValidationError("Cannot delete a disbursed payroll batch.")
        batch.delete()
        CacheManager.invalidate_payroll()


    @staticmethod
    @transaction.atomic
    def disburse_payroll_batch(*, batch_id: str, user) -> PayrollBatch:
        batch = PayrollBatch.objects.select_for_update().get(id=batch_id)
        if batch.status == PayrollBatchStatus.DISBURSED:
            raise ValidationError("This payroll batch has already been disbursed.")

        available = client_escrow_balance_get(client_id=batch.client_id, country_code=batch.country_code)
        required = batch.total_funding_required

        if available < required:
            batch.status = PayrollBatchStatus.BLOCKED_SHORTFALL
            batch.save(update_fields=['status'])
            CacheManager.invalidate_payroll()
            shortfall = required - available
            raise ValidationError(
                f"PAYROLL BLOCKED: Client escrow balance ({available} GHS) is insufficient. Required: {required} GHS. Shortfall: {shortfall} GHS."
            )

        escrow_acct = Account.objects.get(code='2100-ESCROW-GH')
        bank_payout_acct = Account.objects.get(code='1010-FNB-PAYROLL-GH')
        statutory_acct = Account.objects.get(code='2020-TAX-PAYABLE-GH')
        revenue_acct = Account.objects.get(code='4010-EOR-FEES-GH')

        ledger_lines = [
            {'account': escrow_acct, 'debit': required, 'credit': 0, 'client_id': batch.client_id},
            {'account': bank_payout_acct, 'debit': 0, 'credit': batch.total_net_salaries, 'client_id': batch.client_id},
            {'account': statutory_acct, 'debit': 0, 'credit': batch.total_statutory_taxes, 'client_id': batch.client_id},
            {'account': revenue_acct, 'debit': 0, 'credit': batch.total_management_fee, 'client_id': batch.client_id},
        ]

        entry = LedgerService.post_journal_entry(
            entry_number=f"PAY-{batch.batch_code}",
            posting_date=timezone.now().date(),
            description=f"Payroll Payout for {batch.client_name} - Batch {batch.batch_code}",
            source_module="PAYROLL",
            source_ref=str(batch.id),
            user=user,
            lines_data=ledger_lines
        )

        batch.status = PayrollBatchStatus.DISBURSED
        batch.journal_entry = entry
        batch.save(update_fields=['status', 'journal_entry'])

        # Invalidate Escrow & Cash Forecast Cache!
        CacheManager.invalidate_escrow(client_id=batch.client_id, country_code=batch.country_code)
        return batch
