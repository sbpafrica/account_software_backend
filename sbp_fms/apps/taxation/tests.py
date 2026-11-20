import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.taxation.models import TaxRule, TaxType


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        email="superadmin@sbp-africa.com",
        password="SuperPassword123!",
        first_name="Super",
        last_name="Admin"
    )


@pytest.mark.django_db
class TestTaxationCRUD:
    def test_tax_rule_crud_lifecycle(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        # 1. CREATE RULE
        create_url = reverse("tax-rule-list-admin")
        rule_data = {
            "country_code": "GH",
            "tax_type": TaxType.PAYE,
            "bracket_min": 0.0,
            "bracket_max": 490.0,
            "rate": 0.0,
            "effective_from": "2026-01-01"
        }
        res_create = api_client.post(create_url, rule_data, format="json")
        assert res_create.status_code == status.HTTP_201_CREATED
        rule_id = res_create.data["data"]["id"]

        # 2. LIST RULES
        res_list = api_client.get(create_url, {"country": "GH"})
        assert res_list.status_code == status.HTTP_200_OK
        assert any(r["id"] == rule_id for r in res_list.data["data"])

        # 3. RETRIEVE
        detail_url = reverse("tax-rule-detail-admin", kwargs={"rule_id": rule_id})
        res_detail = api_client.get(detail_url)
        assert res_detail.status_code == status.HTTP_200_OK
        assert res_detail.data["data"]["country_code"] == "GH"

        # 4. UPDATE
        res_up = api_client.patch(detail_url, {"bracket_max": 500.0}, format="json")
        assert res_up.status_code == status.HTTP_200_OK
        assert Decimal(str(res_up.data["data"]["bracket_max"])) == Decimal("500.0000")

        # 5. DELETE
        res_del = api_client.delete(detail_url)
        assert res_del.status_code == status.HTTP_200_OK
        assert not TaxRule.objects.filter(id=rule_id).exists()

    def test_public_tax_calculator(self, api_client):
        calc_url = reverse("tax-calculate-public")

        # 1. Test calculation with gross salary (calculates SSNIT, Taxable Income, PAYE, and Net Pay)
        payload = {
            "country_code": "GH",
            "gross_salary": 10000.0
        }
        res = api_client.post(calc_url, payload, format="json")
        assert res.status_code == status.HTTP_200_OK
        data = res.data["data"]
        assert "employee_ssnit" in data
        assert "employer_ssnit" in data
        assert "taxable_income" in data
        assert "paye_tax" in data
        assert "net_salary" in data
        assert "paye_breakdown" in data
        # Gross = 10,000 -> Employee SSNIT (5.5%) = 550.00 -> Taxable Income = 9,450.00
        assert Decimal(str(data["employee_ssnit"])) == Decimal("550.00")
        assert Decimal(str(data["taxable_income"])) == Decimal("9450.00")

        # 2. Test direct calculation with taxable income (W2)
        payload_w2 = {
            "country_code": "GH",
            "taxable_income": 10000.0
        }
        res_w2 = api_client.post(calc_url, payload_w2, format="json")
        assert res_w2.status_code == status.HTTP_200_OK
        data_w2 = res_w2.data["data"]
        # W2 = 10,000 -> PAYE = 2,104.50 (Matches Excel formula exactly!)
        assert Decimal(str(data_w2["paye_tax"])) == Decimal("2104.50")
        assert Decimal(str(data_w2["effective_paye_rate_pct"])) == Decimal("21.04")

    def test_indirect_tax_calculator_and_vat_return_summary(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        # 1. Test Ghana Indirect Tax cascading engine:
        # 1,000.00 GHS base:
        # NHIL = 2.5% = 25.00
        # GETFund = 2.5% = 25.00
        # COVID = 1.0% = 10.00
        # Total Levies = 60.00
        # VAT Base = 1,060.00
        # VAT 15% = 159.00
        # Total Tax = 219.00 (21.90% effective rate)
        # Grand Total = 1,219.00 GHS
        calc_url = reverse("indirect-tax-calculate-admin")
        res_calc = api_client.post(calc_url, {"taxable_value": 1000.0, "include_covid_levy": True}, format="json")
        assert res_calc.status_code == status.HTTP_200_OK
        tax_data = res_calc.data["data"]
        assert Decimal(str(tax_data["nhil_amount"])) == Decimal("25.00")
        assert Decimal(str(tax_data["getfund_amount"])) == Decimal("25.00")
        assert Decimal(str(tax_data["covid_levy_amount"])) == Decimal("10.00")
        assert Decimal(str(tax_data["total_levies"])) == Decimal("60.00")
        assert Decimal(str(tax_data["vat_base"])) == Decimal("1060.00")
        assert Decimal(str(tax_data["vat_amount"])) == Decimal("159.00")
        assert Decimal(str(tax_data["total_tax"])) == Decimal("219.00")
        assert Decimal(str(tax_data["grand_total"])) == Decimal("1219.00")
        assert Decimal(str(tax_data["effective_tax_rate_pct"])) == Decimal("21.90")

        # 2. Test VAT Return Summary
        from apps.receivables.models import Client, ClientInvoice, ClientInvoiceStatus
        client = Client.objects.create(name="Tax Test Client", tax_id="TIN-CL-001", country_code="GH")
        ClientInvoice.objects.create(
            client=client,
            invoice_number="INV-TAX-001",
            issue_date="2026-11-05",
            due_date="2026-11-20",
            total_amount=Decimal("1219.0000"),
            tax_amount=Decimal("219.0000"),
            status=ClientInvoiceStatus.ISSUED
        )

        vat_url = reverse("vat-return-summary-admin")
        res_vat = api_client.get(vat_url, {"start_date": "2026-11-01", "end_date": "2026-11-30", "country": "GH"})
        assert res_vat.status_code == status.HTTP_200_OK
        vat_data = res_vat.data["data"]
        assert Decimal(str(vat_data["taxable_supplies_sales"])) == Decimal("1000.0000")
        assert Decimal(str(vat_data["output_tax_total"])) == Decimal("219.0000")
        assert Decimal(str(vat_data["net_vat_payable"])) == Decimal("219.0000")

    def test_ghana_paye_graduated_brackets_match_excel_formula(self):
        from apps.taxation.engines import GhanaTaxEngine

        # Excel formula:
        # =ROUND(IF(W2<588,0,IF(W2<668,5%*(W2-588),IF(W2<768,10%*(W2-668)+4,
        #        IF(W2<3668,17.5%*(W2-768)+14,IF(W2<19668,25%*(W2-3668)+521.5,
        #        IF(W2<50000,30%*(W2-19668)+4521.5,35%*(W2-50000)+13621.1)))))), 2)

        # 1. Below 588 -> 0 tax
        res1 = GhanaTaxEngine.calculate_paye(Decimal("500.00"))
        assert res1["paye_tax"] == Decimal("0.00")

        # 2. Between 588 and 668: W2 = 600 -> 5% * (600 - 588) = 0.60
        res2 = GhanaTaxEngine.calculate_paye(Decimal("600.00"))
        assert res2["paye_tax"] == Decimal("0.60")

        # 3. Between 668 and 768: W2 = 700 -> 10% * (700 - 668) + 4 = 3.20 + 4 = 7.20
        res3 = GhanaTaxEngine.calculate_paye(Decimal("700.00"))
        assert res3["paye_tax"] == Decimal("7.20")

        # 4. Between 768 and 3668: W2 = 1000 -> 17.5% * (1000 - 768) + 14 = 40.60 + 14 = 54.60
        res4 = GhanaTaxEngine.calculate_paye(Decimal("1000.00"))
        assert res4["paye_tax"] == Decimal("54.60")

        # 5. Between 3668 and 19668: W2 = 10000 -> 25% * (10000 - 3668) + 521.5 = 1583 + 521.5 = 2104.50
        res5 = GhanaTaxEngine.calculate_paye(Decimal("10000.00"))
        assert res5["paye_tax"] == Decimal("2104.50")

        # 6. Between 19668 and 50000: W2 = 30000 -> 30% * (30000 - 19668) + 4521.5 = 3099.60 + 4521.5 = 7621.10
        res6 = GhanaTaxEngine.calculate_paye(Decimal("30000.00"))
        assert res6["paye_tax"] == Decimal("7621.10")

        # 7. Exceeding 50000: W2 = 60000 -> 35% * (60000 - 50000) + 13621.1 = 3500 + 13621.1 = 17121.10
        res7 = GhanaTaxEngine.calculate_paye(Decimal("60000.00"))
        assert res7["paye_tax"] == Decimal("17121.10")

    def test_ssnit_tier_calculations_and_schedule_reports(self, api_client, superuser):
        from apps.taxation.engines import GhanaTaxEngine

        api_client.force_authenticate(user=superuser)

        # 1. Test calculation engine (Act 766)
        # Gross = 10,000.00 GHS
        # Employee 5.5% = 550.00
        # Employer 13.0% = 1,300.00
        # Total 18.5% = 1,850.00
        # Tier 1 to SSNIT (13.5%) = 1,350.00
        # Tier 2 to Trustee (5.0%) = 500.00
        calc = GhanaTaxEngine.calculate_ssnit(Decimal("10000.00"))
        assert calc["employee_ssnit"] == Decimal("550.00")
        assert calc["employer_ssnit"] == Decimal("1300.00")
        assert calc["total_ssnit_liability"] == Decimal("1850.00")
        assert calc["tier_1_ssnit"] == Decimal("1350.00")
        assert calc["tier_2_trustee"] == Decimal("500.00")

        # 2. Test SSNIT Return Summary API
        summary_url = reverse("ssnit-return-summary-admin")
        res_sum = api_client.get(summary_url, {"month": 10, "year": 2026})
        assert res_sum.status_code == status.HTTP_200_OK
        data = res_sum.data["data"]
        assert "period_label" in data
        assert "submission_deadline" in data
        assert "statutory_penalty_clause" in data
        assert "tier_1_payable_ssnit" in data
        assert "tier_2_payable_trustee" in data

        # 3. Test SSNIT Itemized Schedule Generation API
        schedule_url = reverse("ssnit-schedule-generate-admin")
        payload = {
            "employer_name": "SBP Africa Technologies Ltd",
            "employer_ssnit_number": "SSNIT-GH-829102",
            "month": 10,
            "year": 2026,
            "employees": [
                {
                    "employee_name": "Kofi Mensah",
                    "ssnit_number": "C10048291039",
                    "ghana_card_number": "GHA-721948291-3",
                    "gross_salary": 8000.0
                },
                {
                    "employee_name": "Ama Serwaa",
                    "ssnit_number": "C20094819283",
                    "ghana_card_number": "GHA-849102948-1",
                    "gross_salary": 12000.0
                }
            ]
        }
        res_sched = api_client.post(schedule_url, payload, format="json")
        assert res_sched.status_code == status.HTTP_200_OK
        sched_data = res_sched.data["data"]
        assert sched_data["total_employees"] == 2
        # Gross = 20,000.00
        # Employee 5.5% = 1,100.00
        # Employer 13.0% = 2,600.00
        # Total 18.5% = 3,700.00
        # Tier 1 = 2,700.00 (13.5%)
        # Tier 2 = 1,000.00 (5.0%)
        assert Decimal(str(sched_data["total_gross_salaries"])) == Decimal("20000.00")
        assert Decimal(str(sched_data["total_employee_contribution"])) == Decimal("1100.00")
        assert Decimal(str(sched_data["total_employer_contribution"])) == Decimal("2600.00")
        assert Decimal(str(sched_data["total_tier_1_payable_to_ssnit"])) == Decimal("2700.00")
        assert Decimal(str(sched_data["total_tier_2_payable_to_trustee"])) == Decimal("1000.00")
        assert Decimal(str(sched_data["grand_total_contributions"])) == Decimal("3700.00")
        assert len(sched_data["schedule"]) == 2

        # 4. Test SSNIT CSV Report Export API
        export_url = reverse("ssnit-report-export-admin")
        res_exp = api_client.post(export_url, payload, format="json")
        assert res_exp.status_code == status.HTTP_200_OK
        assert "text/csv" in res_exp["Content-Type"]
        assert "attachment; filename=" in res_exp["Content-Disposition"]
        csv_text = res_exp.content.decode("utf-8")
        assert "SSNIT MONTHLY CONTRIBUTION RETURN (ACT 766)" in csv_text
        assert "Kofi Mensah" in csv_text
        assert "Ama Serwaa" in csv_text
        assert "TOTALS" in csv_text




