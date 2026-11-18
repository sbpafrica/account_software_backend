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
