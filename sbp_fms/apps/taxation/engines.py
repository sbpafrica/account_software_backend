from decimal import Decimal


class GhanaTaxEngine:
    """
    Ghana GRA Statutory Calculations Engine:
    1. Social Security (SSNIT):
       - Tier 1 & 2: Employee pays 5.5%, Employer pays 13.0%.
    2. Withholding Tax (WHT):
       - Goods: 3.0%
       - Works: 5.0%
       - Services: 7.5%
       - Technical / Management: 15.0%
    3. Indirect Tax (VAT & Statutory Levies):
       - National Health Insurance Levy (NHIL): 2.5%
       - Ghana Education Trust Fund (GETFund): 2.5%
       - COVID-19 Health Recovery Levy: 1.0%
       - Standard Value Added Tax (VAT): 15.0% applied on (Taxable Value + Statutory Levies)
       - Total Effective Compound Tax Rate: 21.9%
    """

    @staticmethod
    def calculate_ssnit(gross_salary: Decimal) -> dict:
        gross_salary = Decimal(str(gross_salary))
        employee_share = (gross_salary * Decimal('0.055')).quantize(Decimal('0.01'))
        employer_share = (gross_salary * Decimal('0.130')).quantize(Decimal('0.01'))
        return {
            'employee_ssnit': employee_share,
            'employer_ssnit': employer_share,
            'total_ssnit_liability': employee_share + employer_share
        }

    @staticmethod
    def calculate_vendor_wht(service_amount: Decimal, category: str = 'SERVICES') -> dict:
        amount = Decimal(str(service_amount))
        rates = {
            'GOODS': Decimal('0.0300'),
            'WORKS': Decimal('0.0500'),
            'SERVICES': Decimal('0.0750'),
            'TECHNICAL': Decimal('0.1500'),
        }
        rate = rates.get(category.upper(), Decimal('0.0750'))
        wht_amount = (amount * rate).quantize(Decimal('0.01'))
        net_payable = amount - wht_amount
        return {
            'category': category.upper(),
            'gross_amount': amount,
            'wht_rate': rate,
            'wht_amount': wht_amount,
            'net_payable': net_payable
        }

    @staticmethod
    def calculate_ghana_indirect_tax(taxable_value: Decimal, include_covid_levy: bool = True) -> dict:
        """
        Computes Ghana GRA statutory indirect tax cascading formula:
        Base Taxable Value = V
        NHIL = 2.5% * V
        GETFund = 2.5% * V
        COVID = 1.0% * V (if applicable)
        Total Levies = NHIL + GETFund + COVID
        VAT Base = V + Total Levies
        VAT = 15.0% * VAT Base
        Total Tax = Total Levies + VAT
        Grand Total (Gross Invoice Amount) = V + Total Tax
        """
        v = Decimal(str(taxable_value))
        nhil = (v * Decimal('0.025')).quantize(Decimal('0.01'))
        getfund = (v * Decimal('0.025')).quantize(Decimal('0.01'))
        covid = (v * Decimal('0.010')).quantize(Decimal('0.01')) if include_covid_levy else Decimal('0.00')

        total_levies = nhil + getfund + covid
        vat_base = v + total_levies
        vat = (vat_base * Decimal('0.150')).quantize(Decimal('0.01'))

        total_tax = total_levies + vat
        grand_total = v + total_tax

        return {
            'taxable_value': v,
            'nhil_rate': Decimal('0.0250'),
            'nhil_amount': nhil,
            'getfund_rate': Decimal('0.0250'),
            'getfund_amount': getfund,
            'covid_levy_rate': Decimal('0.0100') if include_covid_levy else Decimal('0.0000'),
            'covid_levy_amount': covid,
            'total_levies': total_levies,
            'vat_base': vat_base,
            'vat_rate': Decimal('0.1500'),
            'vat_amount': vat,
            'total_tax': total_tax,
            'grand_total': grand_total,
            'effective_tax_rate_pct': ((total_tax / v * Decimal('100.0')).quantize(Decimal('0.01'))) if v > 0 else Decimal('0.00')
        }
