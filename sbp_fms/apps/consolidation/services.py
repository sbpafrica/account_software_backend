from decimal import Decimal
from django.db import models, transaction
from django.db.models import Sum
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.common.cache import CacheManager
from apps.ledger.models import Account, AccountType, JournalLine
from apps.ledger.services import LedgerService
from .models import ExchangeRate, FXRevaluationRun, RateType
from .selectors import exchange_rate_get_latest


class ConsolidationService:
    @staticmethod
    @transaction.atomic
    def exchange_rate_create(*, from_currency: str, to_currency: str = 'GHS',
                             rate_date, rate: Decimal, rate_type: str = RateType.CLOSING) -> ExchangeRate:
        from_curr = from_currency.strip().upper()
        to_curr = to_currency.strip().upper()
        rate_val = Decimal(str(rate))
        if rate_val <= 0:
            raise ValidationError("Exchange rate must be strictly greater than 0.")

        rate_obj, _ = ExchangeRate.objects.update_or_create(
            from_currency=from_curr,
            to_currency=to_curr,
            rate_date=rate_date,
            rate_type=rate_type,
            defaults={'rate': rate_val}
        )
        CacheManager.invalidate_consolidation()
        return rate_obj

    @staticmethod
    @transaction.atomic
    def fx_revaluation_post(*, revaluation_date, reporting_currency: str = 'GHS',
                            user, notes: str = '') -> FXRevaluationRun:
        """
        Executes month-end / period-end foreign exchange revaluation.
        Revalues foreign currency monetary assets (Bank/Cash) and liabilities.
        Calculates unrealized FX gain or loss and posts automated balancing journal entries.
        """
        rep_curr = reporting_currency.upper()

        # Find foreign currency monetary accounts (ASSET or LIABILITY where currency != reporting_currency)
        foreign_accounts = Account.objects.filter(
            is_active=True,
            account_type__in=[AccountType.ASSET, AccountType.LIABILITY]
        ).exclude(currency=rep_curr)

        if not foreign_accounts.exists():
            # Nothing to revalue
            run = FXRevaluationRun.objects.create(
                revaluation_date=revaluation_date,
                reporting_currency=rep_curr,
                total_gain_loss=Decimal('0.0000'),
                created_by=user,
                notes="No foreign currency monetary accounts found for revaluation."
            )
            return run

        def get_or_create_account(code, name, acct_type):
            acct = Account.objects.filter(code=code).first()
            if not acct:
                acct = Account.objects.create(
                    code=code,
                    name=name,
                    account_type=acct_type,
                    currency=rep_curr,
                    country_code='GH'
                )
            return acct

        fx_gain_account = get_or_create_account('7010-UNREALIZED-FX-GAIN', 'Unrealized Foreign Exchange Gain', AccountType.REVENUE)
        fx_loss_account = get_or_create_account('8010-UNREALIZED-FX-LOSS', 'Unrealized Foreign Exchange Loss', AccountType.OPEX)

        gl_lines = []
        total_net_gain_loss = Decimal('0.0000')

        for acct in foreign_accounts:
            lines = JournalLine.objects.filter(
                account=acct,
                entry__status='POSTED',
                entry__posting_date__lte=revaluation_date
            )
            # Net balance in foreign currency
            totals = lines.aggregate(
                total_debit=models.Sum('debit'),
                total_credit=models.Sum('credit')
            )
            d = totals['total_debit'] or Decimal('0.0000')
            c = totals['total_credit'] or Decimal('0.0000')
            net_foreign = d - c if acct.account_type == AccountType.ASSET else c - d

            if net_foreign == 0:
                continue

            # Fetch closing rate
            closing_rate = exchange_rate_get_latest(
                from_currency=acct.currency,
                to_currency=rep_curr,
                as_of_date=revaluation_date
            )

            # Target revalued amount in reporting currency
            revalued_amount = (net_foreign * closing_rate).quantize(Decimal('0.0001'))

            # For asset: if revalued > original book balance, Gain!
            # Book balance recorded in GL lines is already in GHS base or foreign; calculate diff:
            diff = revalued_amount - net_foreign

            if diff == 0:
                continue

            total_net_gain_loss += diff

            if acct.account_type == AccountType.ASSET:
                if diff > 0:
                    # Gain: DR Asset, CR FX Gain
                    gl_lines.append({'account': acct, 'debit': diff, 'credit': Decimal('0'), 'country_code': acct.country_code})
                    gl_lines.append({'account': fx_gain_account, 'debit': Decimal('0'), 'credit': diff, 'country_code': acct.country_code})
                else:
                    # Loss: DR FX Loss, CR Asset
                    loss_amt = abs(diff)
                    gl_lines.append({'account': fx_loss_account, 'debit': loss_amt, 'credit': Decimal('0'), 'country_code': acct.country_code})
                    gl_lines.append({'account': acct, 'debit': Decimal('0'), 'credit': loss_amt, 'country_code': acct.country_code})
            else:
                # Liability
                if diff > 0:
                    # Liability increased in reporting currency: Loss!
                    gl_lines.append({'account': fx_loss_account, 'debit': diff, 'credit': Decimal('0'), 'country_code': acct.country_code})
                    gl_lines.append({'account': acct, 'debit': Decimal('0'), 'credit': diff, 'country_code': acct.country_code})
                else:
                    # Liability decreased: Gain!
                    gain_amt = abs(diff)
                    gl_lines.append({'account': acct, 'debit': gain_amt, 'credit': Decimal('0'), 'country_code': acct.country_code})
                    gl_lines.append({'account': fx_gain_account, 'debit': Decimal('0'), 'credit': gain_amt, 'country_code': acct.country_code})

        journal = None
        if gl_lines:
            entry_number = f"FX-REV-{revaluation_date.strftime('%Y%m%d')}-{rep_curr}"
            journal = LedgerService.post_journal_entry(
                entry_number=entry_number,
                posting_date=revaluation_date,
                description=f"Month-End FX Revaluation as of {revaluation_date} ({rep_curr})",
                source_module="CONSOLIDATION",
                source_ref=f"REV-{revaluation_date}",
                user=user,
                lines_data=gl_lines
            )

        run = FXRevaluationRun.objects.create(
            revaluation_date=revaluation_date,
            reporting_currency=rep_curr,
            total_gain_loss=total_net_gain_loss,
            journal_entry=journal,
            created_by=user,
            notes=notes or f"FX Revaluation completed. Net Gain/Loss: {total_net_gain_loss} {rep_curr}"
        )
        CacheManager.invalidate_consolidation()
        CacheManager.invalidate_ledger()
        return run


