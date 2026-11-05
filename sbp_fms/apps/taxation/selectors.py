from django.db.models import QuerySet
from .models import TaxRule

def tax_rule_list(*, country_code=None, tax_type=None) -> QuerySet[TaxRule]:
    qs = TaxRule.objects.all()
    if country_code:
        qs = qs.filter(country_code=country_code)
    if tax_type:
        qs = qs.filter(tax_type=tax_type)
    return qs
