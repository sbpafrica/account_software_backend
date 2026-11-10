import pytest
from decimal import Decimal
from datetime import date
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.ledger.models import Account, AccountType, JournalEntry, JournalEntryStatus
from apps.ledger.services import LedgerService


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
class TestLedgerCRUD:
    def test_account_crud_lifecycle(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        # 1. CREATE
        create_url = reverse("account-create-admin")
        create_data = {
            "code": "1090-PETTY-CASH-GH",
            "name": "Petty Cash Ghana",
            "account_type": AccountType.ASSET,
            "currency": "GHS",
            "country_code": "GH",
            "description": "Office petty cash box"
        }
        res = api_client.post(create_url, create_data, format="json")
        assert res.status_code == status.HTTP_201_CREATED
        account_id = res.data["data"]["id"]

        # 2. LIST (Admin & Public)
        list_url = reverse("account-list-admin")
        res_list = api_client.get(list_url)
        assert res_list.status_code == status.HTTP_200_OK
        assert any(a["id"] == account_id for a in res_list.data["data"])

        pub_list_url = reverse("account-list-public")
        res_pub = api_client.get(pub_list_url)
        assert res_pub.status_code == status.HTTP_200_OK

        # 3. RETRIEVE
        detail_url = reverse("account-detail-admin", kwargs={"account_id": account_id})
        res_detail = api_client.get(detail_url)
        assert res_detail.status_code == status.HTTP_200_OK
        assert res_detail.data["data"]["name"] == "Petty Cash Ghana"

        # 4. UPDATE (PUT & PATCH)
        update_data = {
            "name": "Petty Cash Accra HQ",
            "description": "Updated Accra HQ box"
        }
        res_put = api_client.put(detail_url, update_data, format="json")
        assert res_put.status_code == status.HTTP_200_OK
        assert res_put.data["data"]["name"] == "Petty Cash Accra HQ"

        # 5. DELETE
        res_delete = api_client.delete(detail_url)
        assert res_delete.status_code == status.HTTP_200_OK
        assert not Account.objects.filter(id=account_id).exists()

    def test_journal_entry_post_and_reverse(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        # Create two accounts
        cash = Account.objects.create(code="1001-CASH", name="Cash", account_type=AccountType.ASSET)
        capital = Account.objects.create(code="3001-EQUITY", name="Equity Capital", account_type=AccountType.EQUITY)

        # 1. Post balanced journal
        post_url = reverse("entry-post-admin")
        payload = {
            "entry_number": "JRNL-TEST-001",
            "posting_date": "2026-11-09",
            "description": "Capital contribution",
            "source_module": "EQUITY",
            "source_reference_id": "REF-001",
            "lines": [
                {"account_id": str(cash.id), "debit": 10000.0, "credit": 0.0, "country_code": "GH"},
                {"account_id": str(capital.id), "debit": 0.0, "credit": 10000.0, "country_code": "GH"},
            ]
        }
        res_post = api_client.post(post_url, payload, format="json")
        assert res_post.status_code == status.HTTP_201_CREATED
        entry_id = res_post.data["data"]["id"]

        # 2. List & Detail
        res_list = api_client.get(reverse("entry-list-admin"))
        assert res_list.status_code == status.HTTP_200_OK

        res_detail = api_client.get(reverse("entry-detail-admin", kwargs={"entry_id": entry_id}))
        assert res_detail.status_code == status.HTTP_200_OK
        assert res_detail.data["data"]["status"] == JournalEntryStatus.POSTED

        # 3. Trial Balance
        tb_res = api_client.get(reverse("trial-balance-admin"), {"country": "GH"})
        assert tb_res.status_code == status.HTTP_200_OK
        assert tb_res.data["data"]["is_balanced"] is True

        # 4. Reverse Journal
        rev_url = reverse("entry-reverse-admin", kwargs={"entry_id": entry_id})
        res_rev = api_client.post(rev_url, {"reason": "Test reversal"}, format="json")
        assert res_rev.status_code == status.HTTP_201_CREATED

    def test_company_profile_and_dimensions_lifecycle(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        # 1. Company Profile
        prof_url = reverse("company-profile-admin")
        res_prof = api_client.get(prof_url)
        assert res_prof.status_code == status.HTTP_200_OK

        res_update = api_client.put(prof_url, {
            "company_name": "SBP Africa Holdings Ltd",
            "tax_identification_number": "TIN-GH-00129",
            "invoice_prefix": "SBP-INV-"
        }, format="json")
        assert res_update.status_code == status.HTTP_200_OK
        assert res_update.data["data"]["company_name"] == "SBP Africa Holdings Ltd"

        # 2. Departments
        dept_url = reverse("department-list-create-admin")
        res_dept = api_client.post(dept_url, {"code": "FIN", "name": "Finance & Accounts"}, format="json")
        assert res_dept.status_code == status.HTTP_201_CREATED
        dept_id = res_dept.data["data"]["id"]

        res_depts = api_client.get(dept_url)
        assert res_depts.status_code == status.HTTP_200_OK
        assert any(d["code"] == "FIN" for d in res_depts.data["data"])

        # 3. Cost Centres
        cc_url = reverse("cost-centre-list-create-admin")
        res_cc = api_client.post(cc_url, {"code": "CC-ACCRA-HQ", "name": "Accra Headquarters", "department_id": dept_id}, format="json")
        assert res_cc.status_code == status.HTTP_201_CREATED

    def test_financial_statements_pnl_balance_sheet_cashflow_and_gl_statement(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        # 1. Setup Chart of Accounts
        cash_acc = Account.objects.create(code="1010-CASH", name="Cash at Hand", account_type=AccountType.ASSET, opening_balance=Decimal("50000.0000"))
        ar_acc = Account.objects.create(code="1100-AR-MAIN", name="Accounts Receivable", account_type=AccountType.ASSET)
        fa_acc = Account.objects.create(code="1500-EQUIP", name="Office Equipment", account_type=AccountType.ASSET)
        ap_acc = Account.objects.create(code="2000-AP-MAIN", name="Accounts Payable", account_type=AccountType.LIABILITY)
        equity_acc = Account.objects.create(code="3000-SHARE-CAPITAL", name="Share Capital", account_type=AccountType.EQUITY, opening_balance=Decimal("50000.0000"))
        rev_acc = Account.objects.create(code="4000-FEES", name="Accounting Fees", account_type=AccountType.REVENUE)
        cos_acc = Account.objects.create(code="5000-HOSTING", name="Cloud Hosting Costs", account_type=AccountType.DIRECT_COST)
        sal_acc = Account.objects.create(code="6000-SALARIES", name="Staff Salaries", account_type=AccountType.OPEX)

        # 2. Post Revenue (DR AR 20,000, CR Revenue 20,000)
        LedgerService.post_journal_entry(
            entry_number="JE-FIN-01",
            posting_date=date(2026, 11, 2),
            description="Client billing",
            source_module="billing",
            source_ref="INV-01",
            user=superuser,
            lines_data=[
                {"account": ar_acc, "debit": Decimal("20000.0000"), "credit": Decimal("0.0000")},
                {"account": rev_acc, "debit": Decimal("0.0000"), "credit": Decimal("20000.0000")}
            ]
        )

        # 3. Post Direct Cost (DR Cloud Hosting 3,000, CR AP 3,000)
        LedgerService.post_journal_entry(
            entry_number="JE-FIN-02",
            posting_date=date(2026, 11, 3),
            description="AWS Invoice",
            source_module="payables",
            source_ref="AWS-01",
            user=superuser,
            lines_data=[
                {"account": cos_acc, "debit": Decimal("3000.0000"), "credit": Decimal("0.0000")},
                {"account": ap_acc, "debit": Decimal("0.0000"), "credit": Decimal("3000.0000")}
            ]
        )

        # 4. Post OPEX (DR Staff Salaries 5,000, CR Cash 5,000)
        LedgerService.post_journal_entry(
            entry_number="JE-FIN-03",
            posting_date=date(2026, 11, 4),
            description="November payroll disbursement",
            source_module="payroll",
            source_ref="PAY-NOV",
            user=superuser,
            lines_data=[
                {"account": sal_acc, "debit": Decimal("5000.0000"), "credit": Decimal("0.0000")},
                {"account": cash_acc, "debit": Decimal("0.0000"), "credit": Decimal("5000.0000")}
            ]
        )

        # 5. TEST PROFIT & LOSS STATEMENT
        # Revenue = 20,000 | Cost of Sales = 3,000 | Gross Profit = 17,000 (85.00%) | OPEX = 5,000 | Net Profit = 12,000 (60.00%)
        pnl_url = reverse("profit-and-loss-admin")
        res_pnl = api_client.get(pnl_url, {"start_date": "2026-11-01", "end_date": "2026-11-10"})
        assert res_pnl.status_code == status.HTTP_200_OK
        pnl = res_pnl.data["data"]
        assert Decimal(str(pnl["total_revenue"])) == Decimal("20000.0000")
        assert Decimal(str(pnl["total_cost_of_sales"])) == Decimal("3000.0000")
        assert Decimal(str(pnl["gross_profit"])) == Decimal("17000.0000")
        assert Decimal(str(pnl["gross_profit_margin_pct"])) == Decimal("85.00")
        assert Decimal(str(pnl["total_operating_expenses"])) == Decimal("5000.0000")
        assert Decimal(str(pnl["net_profit"])) == Decimal("12000.0000")
        assert Decimal(str(pnl["net_margin_pct"])) == Decimal("60.00")

        # 6. TEST BALANCE SHEET STATEMENT
        # Assets: Cash 45,000 + AR 20,000 = 65,000
        # Liabilities: AP 3,000
        # Equity: Share Capital 50,000 + Net Profit 12,000 = 62,000
        # Total Liab & Equity = 3,000 + 62,000 = 65,000 (Difference: 0.0000, is_balanced: True)
        bs_url = reverse("balance-sheet-admin")
        res_bs = api_client.get(bs_url, {"as_of_date": "2026-11-10"})
        assert res_bs.status_code == status.HTTP_200_OK
        bs = res_bs.data["data"]
        assert Decimal(str(bs["total_assets"])) == Decimal("65000.0000")
        assert Decimal(str(bs["total_liabilities"])) == Decimal("3000.0000")
        assert Decimal(str(bs["total_equity"])) == Decimal("62000.0000")
        assert Decimal(str(bs["total_liabilities_and_equity"])) == Decimal("65000.0000")
        assert Decimal(str(bs["difference"])) == Decimal("0.0000")
        assert bs["is_balanced"] is True

        # 7. TEST CASH FLOW STATEMENT
        cf_url = reverse("cash-flow-admin")
        res_cf = api_client.get(cf_url, {"start_date": "2026-11-01", "end_date": "2026-11-10"})
        assert res_cf.status_code == status.HTTP_200_OK
        cf = res_cf.data["data"]
        assert Decimal(str(cf["net_income"])) == Decimal("12000.0000")
        assert Decimal(str(cf["beginning_cash"])) == Decimal("50000.0000")
        assert Decimal(str(cf["ending_cash"])) == Decimal("45000.0000")

        # 8. TEST GL ACCOUNT STATEMENT
        stmt_url = reverse("gl-account-statement-admin", kwargs={"account_id": str(cash_acc.id)})
        res_stmt = api_client.get(stmt_url, {"start_date": "2026-11-01", "end_date": "2026-11-10"})
        assert res_stmt.status_code == status.HTTP_200_OK
        stmt = res_stmt.data["data"]
        assert Decimal(str(stmt["opening_balance"])) == Decimal("50000.0000")
        assert Decimal(str(stmt["total_credits"])) == Decimal("5000.0000")
        assert Decimal(str(stmt["closing_balance"])) == Decimal("45000.0000")
        assert len(stmt["entries"]) == 1

        # 9. TEST CEO EXECUTIVE DASHBOARD
        ceo_url = reverse("ceo-dashboard-admin")
        res_ceo = api_client.get(ceo_url, {"as_of_date": "2026-11-10"})
        assert res_ceo.status_code == status.HTTP_200_OK
        ceo_data = res_ceo.data["data"]
        assert "liquidity" in ceo_data
        assert "receivables" in ceo_data
        assert "payables" in ceo_data
        assert "working_capital" in ceo_data
        assert "performance_ytd" in ceo_data
        assert "runway" in ceo_data
        assert Decimal(str(ceo_data["performance_ytd"]["revenue"])) == Decimal("20000.0000")
        assert Decimal(str(ceo_data["performance_ytd"]["net_profit"])) == Decimal("12000.0000")



