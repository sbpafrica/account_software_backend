import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.ledger.models import Account, AccountType
from apps.ledger.services import LedgerService
from apps.budgeting.models import BudgetStatus


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
class TestBudgetingCRUD:
    def test_budget_lifecycle_and_pre_commitment_check(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        gl_office = Account.objects.create(
            code="6010-OFFICE-RENT",
            name="Office Rent Expense",
            account_type=AccountType.OPEX,
            currency="GHS",
            country_code="GH"
        )
        gl_travel = Account.objects.create(
            code="6020-STAFF-TRAVEL",
            name="Staff Travel & Flights",
            account_type=AccountType.OPEX,
            currency="GHS",
            country_code="GH"
        )

        # 1. Create Budget Draft
        create_url = reverse("budget-list-create-admin")
        budget_payload = {
            "name": "FY2026 Operations Budget",
            "financial_year": 2026,
            "department": "Operations",
            "cost_centre": "CC-ACCRA-HQ",
            "notes": "Annual operating plan",
            "lines": [
                {
                    "account_id": str(gl_office.id),
                    "planned_amount": 50000.0,
                    "notes": "Annual Office Rent"
                },
                {
                    "account_id": str(gl_travel.id),
                    "planned_amount": 20000.0,
                    "notes": "Client Site Travel"
                }
            ]
        }
        res_create = api_client.post(create_url, budget_payload, format="json")
        assert res_create.status_code == status.HTTP_201_CREATED
        budget_id = res_create.data["data"]["id"]
        assert Decimal(str(res_create.data["data"]["total_budget"])) == Decimal("70000.0000")
        assert res_create.data["data"]["status"] == BudgetStatus.DRAFT

        # 2. Submit Budget
        sub_url = reverse("budget-submit-admin", kwargs={"budget_id": budget_id})
        res_sub = api_client.post(sub_url, format="json")
        assert res_sub.status_code == status.HTTP_200_OK
        assert res_sub.data["data"]["status"] == BudgetStatus.SUBMITTED

        # 3. Approve Budget
        app_url = reverse("budget-approve-admin", kwargs={"budget_id": budget_id})
        res_app = api_client.post(app_url, format="json")
        assert res_app.status_code == status.HTTP_200_OK
        assert res_app.data["data"]["status"] == BudgetStatus.APPROVED

        # 4. Incur Actual GL Expense against Travel (e.g. 5,000 GHS)
        bank_gl = Account.objects.create(code="1020-BANK", name="Main Bank", account_type=AccountType.ASSET)
        LedgerService.post_journal_entry(
            entry_number="JE-TRV-001",
            posting_date="2026-03-15",
            description="Q1 Travel ticket purchase",
            source_module="PAYABLES",
            source_ref="V-001",
            user=superuser,
            lines_data=[
                {"account": gl_travel, "debit": Decimal("5000.0000"), "credit": Decimal("0.0000"), "cost_centre": "CC-ACCRA-HQ", "country_code": "GH"},
                {"account": bank_gl, "debit": Decimal("0.0000"), "credit": Decimal("5000.0000"), "cost_centre": "CC-ACCRA-HQ", "country_code": "GH"}
            ]
        )

        # 5. Check Budget Variance Report
        var_url = reverse("budget-variance-admin", kwargs={"budget_id": budget_id})
        res_var = api_client.get(var_url)
        assert res_var.status_code == status.HTTP_200_OK
        var_data = res_var.data["data"]
        assert Decimal(str(var_data["total_planned"])) == Decimal("70000.0000")
        assert Decimal(str(var_data["total_actual"])) == Decimal("5000.0000")
        assert Decimal(str(var_data["net_available_balance"])) == Decimal("65000.0000")
        assert var_data["is_healthy"] is True

        # 6. Execute Pre-Commitment Check (Amount within remaining budget: 10,000 GHS < 15,000 remaining)
        check_url = reverse("budget-pre-commitment-check-admin")
        res_check_ok = api_client.post(check_url, {
            "account_id": str(gl_travel.id),
            "amount": 10000.0,
            "department": "Operations",
            "cost_centre": "CC-ACCRA-HQ",
            "financial_year": 2026
        }, format="json")
        assert res_check_ok.status_code == status.HTTP_200_OK
        assert res_check_ok.data["data"]["allowed"] is True
        assert Decimal(str(res_check_ok.data["data"]["projected_available_balance"])) == Decimal("5000.0000")

        # 7. Execute Pre-Commitment Check (Amount exceeding remaining budget: 20,000 GHS > 15,000 remaining)
        res_check_fail = api_client.post(check_url, {
            "account_id": str(gl_travel.id),
            "amount": 20000.0,
            "department": "Operations",
            "cost_centre": "CC-ACCRA-HQ",
            "financial_year": 2026
        }, format="json")
        assert res_check_fail.status_code == status.HTTP_200_OK
        assert res_check_fail.data["data"]["allowed"] is False
        assert "Budget breach" in res_check_fail.data["data"]["message"]
