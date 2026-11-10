import csv
import io
import hashlib
from decimal import Decimal
from datetime import datetime, date
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.common.cache import CacheManager
from apps.ledger.models import Account, JournalLine, JournalEntryStatus
from apps.ledger.services import LedgerService
from .models import (
    BankAccount, BankTransaction,
    BankStatement, BankStatementLine,
    BankReconciliation, ReconciliationStatus
)


class TreasuryService:
    @staticmethod
    @transaction.atomic
    def bank_account_create(*, bank_name: str, account_number: str, gl_account_id,
                            currency: str = 'GHS', country_code: str = 'GH',
                            branch_name: str = '', swift_code: str = '') -> BankAccount:
        if BankAccount.objects.filter(account_number=account_number).exists():
            raise ValidationError(f"Bank account '{account_number}' already exists.")
        gl_account = Account.objects.get(id=gl_account_id)
        if hasattr(gl_account, 'bank_account'):
            raise ValidationError(f"GL Account '{gl_account.code}' is already linked to a bank account.")
        account = BankAccount.objects.create(
            bank_name=bank_name.strip(),
            account_number=account_number.strip(),
            branch_name=branch_name.strip(),
            swift_code=swift_code.strip(),
            currency=currency.strip().upper(),
            country_code=country_code.strip().upper(),
            gl_account=gl_account
        )
        CacheManager.invalidate_treasury()
        return account

    @staticmethod
    @transaction.atomic
    def bank_account_update(*, account_id, bank_name: str = None,
                            branch_name: str = None, swift_code: str = None,
                            currency: str = None, country_code: str = None,
                            is_active: bool = None) -> BankAccount:
        account = BankAccount.objects.select_for_update().get(id=account_id)
        if bank_name is not None:
            account.bank_name = bank_name.strip()
        if branch_name is not None:
            account.branch_name = branch_name.strip()
        if swift_code is not None:
            account.swift_code = swift_code.strip()
        if currency is not None:
            account.currency = currency.strip().upper()
        if country_code is not None:
            account.country_code = country_code.strip().upper()
        if is_active is not None:
            account.is_active = is_active
        account.save()
        CacheManager.invalidate_treasury()
        return account

    @staticmethod
    @transaction.atomic
    def bank_account_delete(*, account_id) -> None:
        account = BankAccount.objects.get(id=account_id)
        if account.transactions.exists() or account.statement_lines.exists():
            raise ValidationError(f"Cannot delete bank account '{account.account_number}' with recorded transactions or statements.")
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
            amount=Decimal(str(amount)),
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
            tx.amount = Decimal(str(amount))
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

    # ========================================================================
    # BANK STATEMENT IMPORT & PARSING
    # ========================================================================

    @staticmethod
    @transaction.atomic
    def bank_statement_import(*, bank_account_id: str, file_name: str = '',
                              statement_date: date = None, csv_content: str = None,
                              lines_data: list = None, opening_balance: Decimal = Decimal('0.0000'),
                              closing_balance: Decimal = Decimal('0.0000'), user=None) -> BankStatement:
        bank_account = BankAccount.objects.get(id=bank_account_id)

        parsed_rows = []
        if lines_data:
            parsed_rows = lines_data
        elif csv_content:
            reader = csv.DictReader(io.StringIO(csv_content))
            for row in reader:
                # normalize keys (lower and strip)
                norm_row = {k.strip().lower(): v.strip() for k, v in row.items() if k}
                # support various common header variations
                t_date_str = norm_row.get('date') or norm_row.get('transaction_date') or norm_row.get('trans_date')
                val_date_str = norm_row.get('value_date') or t_date_str
                ref = norm_row.get('reference') or norm_row.get('ref') or norm_row.get('cheque_no') or ''
                desc = norm_row.get('description') or norm_row.get('narration') or norm_row.get('particulars') or ''

                debit = Decimal(norm_row.get('debit', '0') or '0')
                credit = Decimal(norm_row.get('credit', '0') or '0')
                amt_str = norm_row.get('amount')
                if amt_str:
                    amt = Decimal(amt_str)
                    if amt > 0 and debit == 0:
                        debit = amt
                    elif amt < 0 and credit == 0:
                        credit = abs(amt)

                bal_str = norm_row.get('balance')
                running_bal = Decimal(bal_str) if bal_str else None

                t_date = datetime.strptime(t_date_str, '%Y-%m-%d').date() if '-' in t_date_str else datetime.strptime(t_date_str, '%d/%m/%Y').date()
                val_date = t_date
                if val_date_str and '-' in val_date_str:
                    val_date = datetime.strptime(val_date_str, '%Y-%m-%d').date()

                parsed_rows.append({
                    'transaction_date': t_date,
                    'value_date': val_date,
                    'reference': ref,
                    'description': desc,
                    'debit': debit,
                    'credit': credit,
                    'running_balance': running_bal
                })

        if not parsed_rows:
            raise ValidationError("No valid statement line records found in the import.")

        min_date = min(r['transaction_date'] for r in parsed_rows)
        max_date = max(r['transaction_date'] for r in parsed_rows)
        if not statement_date:
            statement_date = max_date

        statement = BankStatement.objects.create(
            bank_account=bank_account,
            statement_date=statement_date,
            start_date=min_date,
            end_date=max_date,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            file_name=file_name,
            total_lines=len(parsed_rows),
            imported_by=user
        )

        created_lines = []
        for r in parsed_rows:
            t_date = r['transaction_date']
            ref = r.get('reference', '')
            desc = r.get('description', '')
            debit = Decimal(str(r.get('debit', '0.0000')))
            credit = Decimal(str(r.get('credit', '0.0000')))
            net_amt = debit - credit
            running_bal = r.get('running_balance')

            # Calculate unique hash to prevent duplicate line imports
            raw_hash = f"{bank_account.id}:{t_date}:{net_amt}:{ref}:{desc}"
            tx_hash = hashlib.sha256(raw_hash.encode('utf-8')).hexdigest()

            if BankStatementLine.objects.filter(transaction_hash=tx_hash).exists():
                # Duplicate line within or across imports: skip or handle gracefully
                continue

            stmt_line = BankStatementLine(
                statement=statement,
                bank_account=bank_account,
                transaction_date=t_date,
                value_date=r.get('value_date', t_date),
                reference=ref,
                description=desc,
                debit=debit,
                credit=credit,
                amount=net_amt,
                running_balance=running_bal,
                transaction_hash=tx_hash
            )
            created_lines.append(stmt_line)

        BankStatementLine.objects.bulk_create(created_lines)
        statement.total_lines = len(created_lines)
        statement.save(update_fields=['total_lines'])

        CacheManager.invalidate_treasury()
        return statement

    # ========================================================================
    # TWO-WAY RECONCILIATION MATCHING ENGINE
    # ========================================================================

    @staticmethod
    @transaction.atomic
    def reconciliation_auto_match(*, bank_account_id: str, tolerance_days: int = 3, user=None) -> dict:
        """
        Scans unmatched bank statement lines and unmatched General Ledger journal lines
        for the bank GL account and matches pairs with identical amounts and close dates.
        """
        bank_account = BankAccount.objects.get(id=bank_account_id)
        gl_account = bank_account.gl_account

        # Unmatched statement lines
        unmatched_stmt_lines = list(BankStatementLine.objects.filter(
            bank_account=bank_account,
            is_reconciled=False
        ).order_by('transaction_date'))

        # Unmatched GL lines for this account
        unmatched_gl_lines = list(JournalLine.objects.filter(
            account=gl_account,
            entry__status=JournalEntryStatus.POSTED,
            reconciled_statement_lines__isnull=True
        ).select_related('entry').order_by('entry__posting_date'))

        matched_count = 0
        total_matched_amount = Decimal('0.0000')
        gl_matched_ids = set()

        for s_line in unmatched_stmt_lines:
            for g_line in unmatched_gl_lines:
                if g_line.id in gl_matched_ids:
                    continue

                # Check date difference
                date_diff = abs((s_line.transaction_date - g_line.entry.posting_date).days)
                if date_diff > tolerance_days:
                    continue

                # Check amount match:
                # Statement debit (receipt) matches GL debit
                # Statement credit (payment) matches GL credit
                is_deposit_match = (s_line.debit > 0 and s_line.debit == g_line.debit)
                is_payment_match = (s_line.credit > 0 and s_line.credit == g_line.credit)

                if is_deposit_match or is_payment_match:
                    s_line.is_reconciled = True
                    s_line.matched_journal_line = g_line
                    s_line.reconciled_at = timezone.now()
                    s_line.reconciled_by = user
                    s_line.save()

                    gl_matched_ids.add(g_line.id)
                    matched_count += 1
                    total_matched_amount += (s_line.debit if is_deposit_match else s_line.credit)
                    break

        CacheManager.invalidate_treasury()
        return {
            'matched_count': matched_count,
            'total_matched_amount': total_matched_amount
        }

    @staticmethod
    @transaction.atomic
    def reconciliation_manual_match(*, statement_line_id: str, journal_line_id: str, user=None) -> BankStatementLine:
        s_line = BankStatementLine.objects.select_for_update().get(id=statement_line_id)
        g_line = JournalLine.objects.select_for_update().get(id=journal_line_id)

        if s_line.is_reconciled:
            raise ValidationError("Statement line is already reconciled.")
        if g_line.reconciled_statement_lines.exists():
            raise ValidationError("Journal line is already linked to another statement line.")

        # Amount validation:
        is_deposit = (s_line.debit > 0 and s_line.debit == g_line.debit)
        is_payment = (s_line.credit > 0 and s_line.credit == g_line.credit)
        if not (is_deposit or is_payment):
            raise ValidationError(
                f"Amounts do not match! Statement line (DR:{s_line.debit}, CR:{s_line.credit}) vs Journal line (DR:{g_line.debit}, CR:{g_line.credit})"
            )

        s_line.is_reconciled = True
        s_line.matched_journal_line = g_line
        s_line.reconciled_at = timezone.now()
        s_line.reconciled_by = user
        s_line.save()

        CacheManager.invalidate_treasury()
        return s_line

    @staticmethod
    @transaction.atomic
    def reconciliation_manual_unmatch(*, statement_line_id: str, user=None) -> BankStatementLine:
        s_line = BankStatementLine.objects.select_for_update().get(id=statement_line_id)
        if not s_line.is_reconciled:
            raise ValidationError("Statement line is not reconciled.")

        s_line.is_reconciled = False
        s_line.matched_journal_line = None
        s_line.reconciled_at = None
        s_line.reconciled_by = None
        s_line.save()

        CacheManager.invalidate_treasury()
        return s_line

    @staticmethod
    @transaction.atomic
    def reconciliation_create_adjustment_journal(*, statement_line_id: str, offset_account_id: str,
                                                 user, description: str = '') -> JournalLine:
        """
        Creates an immediate GL adjustment entry for statement lines (e.g. bank charges, interest)
        and automatically marks the statement line reconciled.
        """
        s_line = BankStatementLine.objects.select_for_update().get(id=statement_line_id)
        if s_line.is_reconciled:
            raise ValidationError("Statement line is already reconciled.")

        bank_acc = s_line.bank_account
        gl_bank_acc = bank_acc.gl_account
        offset_acc = Account.objects.get(id=offset_account_id)

        entry_number = f"ADJ-BANK-{datetime.now().strftime('%Y%m%d%H%M%S')}-{s_line.id.hex[:6].upper()}"
        journal_desc = description.strip() or f"Bank adjustment for {s_line.description} ({s_line.reference})"

        lines_data = []
        if s_line.credit > 0:
            # Bank charge / fee withdrawal:
            # DR Expense (offset_acc)
            # CR Bank GL Account (gl_bank_acc)
            lines_data = [
                {'account': offset_acc, 'debit': s_line.credit, 'credit': Decimal('0.0000')},
                {'account': gl_bank_acc, 'debit': Decimal('0.0000'), 'credit': s_line.credit}
            ]
        elif s_line.debit > 0:
            # Interest income / deposit:
            # DR Bank GL Account (gl_bank_acc)
            # CR Income (offset_acc)
            lines_data = [
                {'account': gl_bank_acc, 'debit': s_line.debit, 'credit': Decimal('0.0000')},
                {'account': offset_acc, 'debit': Decimal('0.0000'), 'credit': s_line.debit}
            ]
        else:
            raise ValidationError("Statement line has zero amount; cannot post adjustment.")

        entry = LedgerService.post_journal_entry(
            entry_number=entry_number,
            posting_date=s_line.transaction_date,
            description=journal_desc,
            source_module='treasury_adjustment',
            source_ref=str(s_line.id),
            user=user,
            lines_data=lines_data
        )

        bank_journal_line = entry.lines.get(account=gl_bank_acc)

        s_line.is_reconciled = True
        s_line.matched_journal_line = bank_journal_line
        s_line.reconciled_at = timezone.now()
        s_line.reconciled_by = user
        s_line.save()

        CacheManager.invalidate_treasury()
        return bank_journal_line

    @staticmethod
    @transaction.atomic
    def reconciliation_record_save(*, bank_account_id: str, statement_date: date,
                                   summary_data: dict, user, notes: str = '') -> BankReconciliation:
        bank_acc = BankAccount.objects.get(id=bank_account_id)
        rec_number = f"REC-{bank_acc.bank_name[:3].upper()}-{statement_date.strftime('%Y%m')}-{datetime.now().strftime('%H%M%S')}"

        rec = BankReconciliation.objects.create(
            reconciliation_number=rec_number,
            bank_account=bank_acc,
            statement_date=statement_date,
            statement_ending_balance=summary_data['statement_ending_balance'],
            gl_book_balance=summary_data['gl_book_balance'],
            deposits_in_transit=summary_data['deposits_in_transit_total'],
            outstanding_cheques=summary_data['outstanding_cheques_total'],
            unrecorded_bank_credits=summary_data['unrecorded_bank_credits_total'],
            unrecorded_bank_debits=summary_data['unrecorded_bank_debits_total'],
            reconciled_difference=summary_data['reconciled_difference'],
            status=ReconciliationStatus.DRAFT,
            reconciled_by=user,
            notes=notes
        )
        CacheManager.invalidate_treasury()
        return rec

    @staticmethod
    @transaction.atomic
    def reconciliation_finalize(*, reconciliation_id: str, user) -> BankReconciliation:
        rec = BankReconciliation.objects.select_for_update().get(id=reconciliation_id)
        if rec.status == ReconciliationStatus.COMPLETED:
            raise ValidationError("Reconciliation is already finalized.")

        if rec.reconciled_difference != Decimal('0.0000'):
            raise ValidationError(
                f"Cannot finalize bank reconciliation. Unreconciled difference is {rec.reconciled_difference} (must be 0.0000)."
            )

        rec.status = ReconciliationStatus.COMPLETED
        rec.completed_at = timezone.now()
        rec.reconciled_by = user
        rec.save()

        CacheManager.invalidate_treasury()
        return rec
