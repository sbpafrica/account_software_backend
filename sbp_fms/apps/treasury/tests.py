import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.ledger.models import Account, AccountType
from apps.treasury.models import BankAccount, BankTransaction


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
class TestTreasuryCRUD:
    def test_bank_account_and_transaction_lifecycle(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        gl_acc = Account.objects.create(
            code="1020-STANBIC-GH",
            name="Stanbic Bank Operating Account",
            account_type=AccountType.ASSET,
            currency="GHS",
            country_code="GH"
        )

        # 1. CREATE BANK ACCOUNT
        acct_url = reverse("bank-account-list-admin")
        acct_data = {
            "bank_name": "Stanbic Bank Ghana",
            "account_number": "9040001234567",
            "currency": "GHS",
            "country_code": "GH",
            "gl_account_id": str(gl_acc.id)
        }
        res_acct = api_client.post(acct_url, acct_data, format="json")
        assert res_acct.status_code == status.HTTP_201_CREATED
        bank_acct_id = res_acct.data["data"]["id"]

        # 2. CREATE TRANSACTION
        tx_url = reverse("bank-transactions-admin")
        tx_data = {
            "bank_account_id": bank_acct_id,
            "transaction_date": "2026-11-08",
            "bank_reference": "TXN-STANBIC-001",
            "description": "Incoming client remittance",
            "amount": 25000.0
        }
        res_tx = api_client.post(tx_url, tx_data, format="json")
        assert res_tx.status_code == status.HTTP_201_CREATED
        tx_id = res_tx.data["data"]["id"]

        # 3. RECONCILE TRANSACTION
        rec_url = reverse("bank-transaction-reconcile-admin", kwargs={"transaction_id": tx_id})
        res_rec = api_client.post(rec_url, format="json")
        assert res_rec.status_code == status.HTTP_200_OK
        assert res_rec.data["data"]["is_reconciled"] is True

        # 4. CASH FORECAST
        fc_url = reverse("cash-forecast-admin")
        res_fc = api_client.get(fc_url)
        assert res_fc.status_code == status.HTTP_200_OK
        assert "forecast_30_days" in res_fc.data["data"]

        # 5. PUBLIC WEBHOOK
        wb_url = reverse("bank-webhook-public")
        res_wb = api_client.post(wb_url, {"event": "PING"}, format="json")
        assert res_wb.status_code == status.HTTP_200_OK
        assert res_wb.data["data"]["status"] == "RECEIVED"
