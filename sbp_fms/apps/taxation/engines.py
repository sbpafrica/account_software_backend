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
    def calculate_paye(taxable_income: Decimal) -> dict:
        """
        Ghana GRA Graduated Progressive PAYE Calculation.
        Direct programmatic equivalent of the Excel formula:
        =ROUND(IF(W2<588,0,IF(W2<668,5%*(W2-588),IF(W2<768,10%*(W2-668)+4,
               IF(W2<3668,17.5%*(W2-768)+14,IF(W2<19668,25%*(W2-3668)+521.5,
               IF(W2<50000,30%*(W2-19668)+4521.5,35%*(W2-50000)+13621.1)))))), 2)
        """
        income = Decimal(str(taxable_income))
        if income <= Decimal('0.00'):
            return {
                'taxable_income': Decimal('0.00'),
                'paye_tax': Decimal('0.00'),
                'effective_rate_pct': Decimal('0.00'),
                'breakdown': []
            }

        brackets = [
            (Decimal('0.00'), Decimal('588.00'), Decimal('0.0000'), "First GHS 588 @ 0%"),
            (Decimal('588.00'), Decimal('668.00'), Decimal('0.0500'), "Next GHS 80 @ 5%"),
            (Decimal('668.00'), Decimal('768.00'), Decimal('0.1000'), "Next GHS 100 @ 10%"),
            (Decimal('768.00'), Decimal('3668.00'), Decimal('0.1750'), "Next GHS 2,900 @ 17.5%"),
            (Decimal('3668.00'), Decimal('19668.00'), Decimal('0.2500'), "Next GHS 16,000 @ 25%"),
            (Decimal('19668.00'), Decimal('50000.00'), Decimal('0.3000'), "Next GHS 30,332 @ 30%"),
            (Decimal('50000.00'), None, Decimal('0.3500'), "Exceeding GHS 50,000 @ 35%"),
        ]

        total_tax = Decimal('0.00')
        breakdown = []

        for b_min, b_max, rate, label in brackets:
            if income <= b_min:
                break

            taxable_slice_max = min(income, b_max) if b_max is not None else income
            slice_amount = taxable_slice_max - b_min
            tier_tax = (slice_amount * rate).quantize(Decimal('0.0001'))
            total_tax += tier_tax

            breakdown.append({
                'tier': label,
                'bracket_min': b_min,
                'bracket_max': b_max,
                'rate': rate,
                'taxable_amount': slice_amount.quantize(Decimal('0.01')),
                'tax_charged': tier_tax.quantize(Decimal('0.01')),
            })

        rounded_tax = total_tax.quantize(Decimal('0.01'))
        effective_rate = ((rounded_tax / income) * Decimal('100.00')).quantize(Decimal('0.01')) if income > 0 else Decimal('0.00')

        return {
            'taxable_income': income.quantize(Decimal('0.01')),
            'paye_tax': rounded_tax,
            'effective_rate_pct': effective_rate,
            'breakdown': breakdown
        }

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
    def calculate_ghana_indirect_tax(taxable_value: Decimal, include_covid_levy: bool = False) -> dict:
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
