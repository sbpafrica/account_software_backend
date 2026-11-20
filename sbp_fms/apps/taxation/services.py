from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.common.cache import CacheManager
from .models import TaxRule
from .engines import GhanaTaxEngine


class TaxationService:
    @staticmethod
    def calculate_statutory_taxes(*, country_code: str = 'GH', gross_salary: Decimal = None,
                                  taxable_income: Decimal = None) -> dict:
        country_code = country_code.strip().upper() if country_code else 'GH'
        if country_code == 'GH':
            if gross_salary is not None:
                gross = Decimal(str(gross_salary))
                ssnit = GhanaTaxEngine.calculate_ssnit(gross)
                emp_ssnit = ssnit['employee_ssnit']
                empr_ssnit = ssnit['employer_ssnit']
                w2 = gross - emp_ssnit
                paye_res = GhanaTaxEngine.calculate_paye(w2)
                net = gross - emp_ssnit - paye_res['paye_tax']
                return {
                    'country_code': 'GH',
                    'gross_salary': gross,
                    'employee_ssnit': emp_ssnit,
                    'employer_ssnit': empr_ssnit,
                    'total_ssnit_liability': ssnit['total_ssnit_liability'],
                    'taxable_income': w2,
                    'paye_tax': paye_res['paye_tax'],
                    'net_salary': net,
                    'effective_paye_rate_pct': paye_res['effective_rate_pct'],
                    'paye_breakdown': paye_res['breakdown'],
                }
            elif taxable_income is not None:
                w2 = Decimal(str(taxable_income))
                paye_res = GhanaTaxEngine.calculate_paye(w2)
                return {
                    'country_code': 'GH',
                    'taxable_income': w2,
                    'paye_tax': paye_res['paye_tax'],
                    'effective_paye_rate_pct': paye_res['effective_rate_pct'],
                    'paye_breakdown': paye_res['breakdown'],
                }
        raise NotImplementedError(f"Tax calculation engine for '{country_code}' is currently in roadmap.")

    @staticmethod
    @transaction.atomic
    def tax_rule_create(*, country_code: str, tax_type: str, bracket_min: Decimal,
                        bracket_max: Decimal = None, rate: Decimal = Decimal('0.0000'),
                        effective_from = None) -> TaxRule:
        rule = TaxRule.objects.create(
            country_code=country_code.strip().upper(),
            tax_type=tax_type,
            bracket_min=bracket_min,
            bracket_max=bracket_max,
            rate=rate,
            effective_from=effective_from
        )
        CacheManager.invalidate_taxation()
        return rule

    @staticmethod
    @transaction.atomic
    def tax_rule_update(*, rule_id, country_code: str = None, tax_type: str = None,
                        bracket_min: Decimal = None, bracket_max: Decimal = None,
                        rate: Decimal = None, effective_from = None) -> TaxRule:
        rule = TaxRule.objects.select_for_update().get(id=rule_id)
        if country_code is not None:
            rule.country_code = country_code.strip().upper()
        if tax_type is not None:
            rule.tax_type = tax_type
        if bracket_min is not None:
            rule.bracket_min = bracket_min
        if bracket_max is not None:
            rule.bracket_max = bracket_max
        if rate is not None:
            rule.rate = rate
        if effective_from is not None:
            rule.effective_from = effective_from
        rule.save()
        CacheManager.invalidate_taxation()
        return rule

    @staticmethod
    @transaction.atomic
    def tax_rule_delete(*, rule_id) -> None:
        rule = TaxRule.objects.get(id=rule_id)
        rule.delete()
        CacheManager.invalidate_taxation()

    @staticmethod
    @transaction.atomic
    def create_ssnit_statutory_payment_voucher(*, month: int, year: int,
                                               remittance_type: str = 'TIER_1_SSNIT',
                                               client_id = None, bank_account_id = None,
                                               trustee_name: str = '', user = None,
                                               notes: str = '') -> 'PaymentVoucher':
        """
        Creates an Accounts Payable statutory disbursement voucher (PaymentVoucher)
        for SSNIT Tier 1 (13.5%), Tier 2 (5.0%), or Combined pension contributions.
        Follows Ghana Act 766 compliance and SBP Africa's multi-client HR disbursement workflow.
        """
        import uuid
        from django.utils import timezone
        from apps.payables.models import PaymentVoucher, PayeeType, PaymentMethod, VoucherLine
        from apps.payables.services import PayablesService
        from apps.ledger.models import Account, AccountType
        from apps.taxation.selectors import ssnit_return_summary_get

        summary = ssnit_return_summary_get(month=month, year=year, client_id=client_id)

        # Determine statutory liability amount and payee
        if remittance_type == 'TIER_1_SSNIT':
            payee_name = "Social Security and National Insurance Trust (SSNIT)"
            amount = summary['tier_1_payable_ssnit']
            type_label = "Tier 1 (13.5% SSNIT)"
        elif remittance_type == 'TIER_2_TRUSTEE':
            p_trustee = trustee_name.strip() if trustee_name else "Mandatory Occupational Pension Trustee"
            payee_name = f"Corporate Pension Trustee - {p_trustee}"
            amount = summary['tier_2_payable_trustee']
            type_label = f"Tier 2 (5.0% {p_trustee})"
        elif remittance_type == 'COMBINED':
            payee_name = "SSNIT & Registered Corporate Pension Trustees"
            amount = summary['total_statutory_pension_liability']
            type_label = "Tier 1 & Tier 2 Combined (18.5%)"
        else:
            raise ValidationError(f"Invalid statutory remittance type: '{remittance_type}'.")

        if amount <= Decimal('0.00'):
            raise ValidationError(f"Cannot generate statutory voucher for zero or negative amount ({amount} GHS).")

        uid_suffix = uuid.uuid4().hex[:6].upper()
        voucher_num = f"PV-SSNIT-{year}{month:02d}-{uid_suffix}"
        period_lbl = summary.get('period_label', f"{month}/{year}")
        employer = summary.get('employer_name', 'Client Employer')

        desc = f"Statutory {type_label} pension remittance for {employer} - Period: {period_lbl}"
        if notes:
            desc = f"{desc} | {notes}"

        # Get or create GL Account for statutory tax & pension payable
        acct, _ = Account.objects.get_or_create(
            code='2020-TAX-PAYABLE-GH',
            defaults={
                'name': 'Statutory Tax & Pension Payable (GRA/SSNIT)',
                'account_type': AccountType.LIABILITY,
                'currency': 'GHS',
                'country_code': 'GH'
            }
        )

        lines_data = [
            {
                'account_id': str(acct.id),
                'description': f"Statutory {type_label} contribution remittance",
                'amount': amount
            }
        ]

        voucher = PayablesService.voucher_create_draft(
            voucher_number=voucher_num,
            voucher_date=timezone.now().date(),
            payee_name=payee_name,
            payee_type=PayeeType.GOVERNMENT,
            payment_method=PaymentMethod.BANK_TRANSFER,
            bank_account_id=bank_account_id,
            gross_amount=amount,
            wht_rate=Decimal('0.0000'),
            other_deductions=Decimal('0.0000'),
            description=desc,
            client_id=client_id,
            lines_data=lines_data,
            user=user
        )

        return voucher
