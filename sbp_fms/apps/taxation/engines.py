from decimal import Decimal

class GhanaTaxEngine:
    """
    [DEVELOPER NOTE]: Ghana GRA & SSNIT Statutory Calculations.
    - Tier 1 & 2 Social Security: Employee pays 5.5%, Employer pays 13.0%.
    - Withholding Tax: Standard 7.5% on services, 3% on goods.
    """
    @staticmethod
    def calculate_ssnit(gross_salary: Decimal) -> dict:
        employee_share = (gross_salary * Decimal('0.055')).quantize(Decimal('0.01'))
        employer_share = (gross_salary * Decimal('0.130')).quantize(Decimal('0.01'))
        return {
            'employee_ssnit': employee_share,
            'employer_ssnit': employer_share,
            'total_ssnit_liability': employee_share + employer_share
        }

    @staticmethod
    def calculate_vendor_wht(service_amount: Decimal, is_goods=False) -> Decimal:
        rate = Decimal('0.03') if is_goods else Decimal('0.075')
        return (service_amount * rate).quantize(Decimal('0.01'))
