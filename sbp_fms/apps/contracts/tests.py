import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.receivables.models import Client, ClientInvoice, ClientInvoiceStatus
from apps.payables.models import PaymentVoucher, PaymentVoucherStatus
from apps.ledger.models import Account, AccountType


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
class TestContractsCRUD:
    def test_contract_crud_and_profitability_analysis(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        client = Client.objects.create(name="Enterprise Global Ltd", tax_id="TIN-ENT-888", country_code="GH")

        # 1. Create Contract
        create_url = reverse("contract-list-create-admin")
        payload = {
            "contract_number": "CON-2026-ENG-01",
            "client_id": str(client.id),
            "title": "Cloud Infrastructure Architecture & Support",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "total_contract_value": 200000.0,
            "cost_centre": "CC-ENG-GLOBAL",
            "notes": "Annual enterprise engineering retainer"
        }
        res_create = api_client.post(create_url, payload, format="json")
        assert res_create.status_code == status.HTTP_201_CREATED
        contract_id = res_create.data["data"]["id"]
        assert Decimal(str(res_create.data["data"]["total_contract_value"])) == Decimal("200000.0000")

        # 2. List & Detail
        res_list = api_client.get(create_url)
        assert res_list.status_code == status.HTTP_200_OK
        assert any(c["id"] == contract_id for c in res_list.data["data"])

        detail_url = reverse("contract-detail-admin", kwargs={"contract_id": contract_id})
        res_detail = api_client.get(detail_url)
        assert res_detail.status_code == status.HTTP_200_OK
        assert res_detail.data["data"]["contract_number"] == "CON-2026-ENG-01"

        # 3. Add Client Invoices (Billed Revenue)
        # 100,000 subtotal, 21,900 tax, 121,900 total
        ClientInvoice.objects.create(
            client=client,
            invoice_number="INV-CON-001",
            issue_date="2026-02-01",
            due_date="2026-02-28",
            subtotal=Decimal("100000.0000"),
            tax_amount=Decimal("21900.0000"),
            total_amount=Decimal("121900.0000"),
            amount_paid=Decimal("121900.0000"),
            status=ClientInvoiceStatus.PAID
        )

        # 4. Add Payment Voucher for direct project expense (e.g. 25,000 GHS software licenses)
        PaymentVoucher.objects.create(
            voucher_number="PV-CON-LIC-001",
            voucher_date="2026-02-10",
            payee_name="AWS Cloud Services",
            client_id=client.id,
            cost_centre="CC-ENG-GLOBAL",
            gross_amount=Decimal("25000.0000"),
            net_amount=Decimal("25000.0000"),
            status=PaymentVoucherStatus.PAID,
            description="Dedicated Cloud compute for contract"
        )

        # 5. Check Contract Profitability Analysis:
        # Billed Revenue: 100,000
        # Direct Expenses: 25,000
        # Gross Profit: 75,000
        # Gross Margin %: 75.00%
        # Realization %: 100,000 / 200,000 = 50.00%
        prof_url = reverse("contract-profitability-admin", kwargs={"contract_id": contract_id})
        res_prof = api_client.get(prof_url)
        assert res_prof.status_code == status.HTTP_200_OK
        prof_data = res_prof.data["data"]
        assert Decimal(str(prof_data["billed_revenue"])) == Decimal("100000.0000")
        assert Decimal(str(prof_data["direct_expenses"])) == Decimal("25000.0000")
        assert Decimal(str(prof_data["gross_profit"])) == Decimal("75000.0000")
        assert Decimal(str(prof_data["gross_margin_pct"])) == Decimal("75.00")
        assert Decimal(str(prof_data["contract_realization_pct"])) == Decimal("50.00")
        assert prof_data["is_profitable"] is True
