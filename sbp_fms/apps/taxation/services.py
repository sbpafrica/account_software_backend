from decimal import Decimal
from .engines import GhanaTaxEngine

class TaxationService:
    @staticmethod
    def calculate_statutory_taxes(*, country_code: str, gross_salary: Decimal) -> dict:
        if country_code == 'GH':
            return GhanaTaxEngine.calculate_ssnit(gross_salary)
        raise NotImplementedError(f"Tax calculation engine for '{country_code}' is currently in roadmap.")
