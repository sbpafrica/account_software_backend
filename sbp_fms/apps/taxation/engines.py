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
        """
        Ghana Statutory National Pension Calculations (National Pensions Act, 2008 - Act 766):
        - Employee Contribution: 5.5% (Deducted from basic/gross pay, tax exempt)
        - Employer Contribution: 13.0% (Borne by employer)
        - Total Statutory Rate: 18.5%

        Remittance Tiers:
        - Tier 1 (First Tier Mandatory Basic Social Security): 13.5% remitted directly to SSNIT
        - Tier 2 (Second Tier Mandatory Occupational Pension Scheme): 5.0% remitted to licensed Private Trustee
        """
        gross_salary = Decimal(str(gross_salary))
        employee_share = (gross_salary * Decimal('0.055')).quantize(Decimal('0.01'))
        employer_share = (gross_salary * Decimal('0.130')).quantize(Decimal('0.01'))
        total_liability = employee_share + employer_share

        tier_1_ssnit = (gross_salary * Decimal('0.135')).quantize(Decimal('0.01'))
        tier_2_trustee = (gross_salary * Decimal('0.050')).quantize(Decimal('0.01'))

        return {
            'employee_ssnit': employee_share,
            'employer_ssnit': employer_share,
            'total_ssnit_liability': total_liability,
            'tier_1_ssnit': tier_1_ssnit,
            'tier_2_trustee': tier_2_trustee,
            'employee_rate_pct': Decimal('5.50'),
            'employer_rate_pct': Decimal('13.00'),
            'total_rate_pct': Decimal('18.50'),
            'tier_1_rate_pct': Decimal('13.50'),
            'tier_2_rate_pct': Decimal('5.00'),
        }

    @staticmethod
    def generate_ssnit_monthly_schedule(
        *,
        employer_name: str,
        employer_ssnit_id: str,
        month: int,
        year: int,
        employees: list[dict]
    ) -> dict:
        """
        Generates the Ghana SSNIT Monthly Contribution Return Schedule.
        Under Act 766, contributions are due by the 14th day of the following month.
        """
        import datetime
        from django.utils import timezone

        # Calculate statutory deadline: 14th of following month
        if month == 12:
            next_month = 1
            next_year = year + 1
        else:
            next_month = month + 1
            next_year = year
        deadline_date = datetime.date(next_year, next_month, 14)
        today = timezone.now().date()
        days_until_deadline = (deadline_date - today).days

        schedule_items = []
        total_gross = Decimal('0.00')
        total_employee = Decimal('0.00')
        total_employer = Decimal('0.00')
        total_tier_1 = Decimal('0.00')
        total_tier_2 = Decimal('0.00')
        total_contributions = Decimal('0.00')

        for idx, emp in enumerate(employees, start=1):
            gross = Decimal(str(emp.get('gross_salary', 0.0)))
            calc = GhanaTaxEngine.calculate_ssnit(gross)

            item = {
                'serial_no': idx,
                'employee_name': emp.get('employee_name', f"Employee {idx}"),
                'ssnit_number': emp.get('ssnit_number', ''),
                'ghana_card_number': emp.get('ghana_card_number', ''),
                'gross_salary': gross.quantize(Decimal('0.01')),
                'employee_contribution': calc['employee_ssnit'],
                'employer_contribution': calc['employer_ssnit'],
                'total_contribution': calc['total_ssnit_liability'],
                'tier_1_ssnit': calc['tier_1_ssnit'],
                'tier_2_trustee': calc['tier_2_trustee'],
            }
            schedule_items.append(item)

            total_gross += gross
            total_employee += calc['employee_ssnit']
            total_employer += calc['employer_ssnit']
            total_tier_1 += calc['tier_1_ssnit']
            total_tier_2 += calc['tier_2_trustee']
            total_contributions += calc['total_ssnit_liability']

        month_names = ["January", "February", "March", "April", "May", "June",
                       "July", "August", "September", "October", "November", "December"]
        period_label = f"{month_names[month - 1]} {year}" if 1 <= month <= 12 else f"{month}/{year}"

        return {
            'employer_name': employer_name,
            'employer_ssnit_number': employer_ssnit_id,
            'period_month': month,
            'period_year': year,
            'period_label': period_label,
            'submission_deadline': deadline_date.isoformat(),
            'days_until_deadline': days_until_deadline,
            'is_overdue': days_until_deadline < 0,
            'statutory_penalty_clause': "Under Act 766 Section 64, late remittances attract a 3% compound monthly penalty.",
            'total_employees': len(schedule_items),
            'total_gross_salaries': total_gross.quantize(Decimal('0.01')),
            'total_employee_contribution': total_employee.quantize(Decimal('0.01')),
            'total_employer_contribution': total_employer.quantize(Decimal('0.01')),
            'total_tier_1_payable_to_ssnit': total_tier_1.quantize(Decimal('0.01')),
            'total_tier_2_payable_to_trustee': total_tier_2.quantize(Decimal('0.01')),
            'grand_total_contributions': total_contributions.quantize(Decimal('0.01')),
            'schedule': schedule_items,
        }

    @staticmethod
    def export_ssnit_schedule_csv(report_data: dict) -> str:
        """
        Exports the SSNIT Monthly Contribution Return Schedule as CSV string.
        """
        import io
        import csv

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["SSNIT MONTHLY CONTRIBUTION RETURN (ACT 766)"])
        writer.writerow(["Employer Name:", report_data.get('employer_name', '')])
        writer.writerow(["Employer SSNIT Number:", report_data.get('employer_ssnit_number', '')])
        writer.writerow(["Contribution Period:", report_data.get('period_label', '')])
        writer.writerow(["Submission Deadline:", report_data.get('submission_deadline', '')])
        writer.writerow([])

        writer.writerow([
            "Item No",
            "SSNIT Number",
            "Employee Full Name",
            "Ghana Card Number",
            "Basic/Gross Salary (GHS)",
            "Employee Share (5.5%)",
            "Employer Share (13.0%)",
            "Total Contribution (18.5%)",
            "Tier 1 to SSNIT (13.5%)",
            "Tier 2 to Trustee (5.0%)",
        ])

        for item in report_data.get('schedule', []):
            writer.writerow([
                item['serial_no'],
                item['ssnit_number'],
                item['employee_name'],
                item['ghana_card_number'],
                f"{Decimal(str(item['gross_salary'])):.2f}",
                f"{Decimal(str(item['employee_contribution'])):.2f}",
                f"{Decimal(str(item['employer_contribution'])):.2f}",
                f"{Decimal(str(item['total_contribution'])):.2f}",
                f"{Decimal(str(item['tier_1_ssnit'])):.2f}",
                f"{Decimal(str(item['tier_2_trustee'])):.2f}",
            ])

        writer.writerow([])
        writer.writerow([
            "TOTALS",
            "",
            f"{report_data.get('total_employees', 0)} Employees",
            "",
            f"{Decimal(str(report_data.get('total_gross_salaries', 0))):.2f}",
            f"{Decimal(str(report_data.get('total_employee_contribution', 0))):.2f}",
            f"{Decimal(str(report_data.get('total_employer_contribution', 0))):.2f}",
            f"{Decimal(str(report_data.get('grand_total_contributions', 0))):.2f}",
            f"{Decimal(str(report_data.get('total_tier_1_payable_to_ssnit', 0))):.2f}",
            f"{Decimal(str(report_data.get('total_tier_2_payable_to_trustee', 0))):.2f}",
        ])

        return output.getvalue()

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
