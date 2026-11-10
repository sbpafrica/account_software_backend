from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.common.cache import CacheManager
from .models import TaxRule
from .engines import GhanaTaxEngine


class TaxationService:
    @staticmethod
    def calculate_statutory_taxes(*, country_code: str, gross_salary: Decimal) -> dict:
        if country_code == 'GH':
            return GhanaTaxEngine.calculate_ssnit(gross_salary)
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
