import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.receivables.models import Client, ClientInvoice, ClientInvoiceStatus


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
class TestReceivablesCRUD:
    def test_client_crud_lifecycle(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        # 1. CREATE
        url_create = reverse("client-list-admin")
        client_data = {
            "name": "Global Tech Logistics Ltd",
            "code": "CL-GTL-001",
            "country_code": "GH",
            "credit_limit": 75000.0,
            "payment_terms_days": 45
        }
        res_create = api_client.post(url_create, client_data, format="json")
        assert res_create.status_code == status.HTTP_201_CREATED
        client_id = res_create.data["data"]["id"]

        # 2. LIST
        res_list = api_client.get(url_create)
        assert res_list.status_code == status.HTTP_200_OK
        assert any(c["id"] == client_id for c in res_list.data["data"])

        # 3. RETRIEVE
        detail_url = reverse("client-detail-admin", kwargs={"client_id": client_id})
        res_detail = api_client.get(detail_url)
        assert res_detail.status_code == status.HTTP_200_OK
        assert res_detail.data["data"]["name"] == "Global Tech Logistics Ltd"

        # 4. UPDATE
        res_update = api_client.put(detail_url, {"name": "Global Tech Group Ltd"}, format="json")
        assert res_update.status_code == status.HTTP_200_OK
        assert res_update.data["data"]["name"] == "Global Tech Group Ltd"

        # 5. DELETE
        res_del = api_client.delete(detail_url)
        assert res_del.status_code == status.HTTP_200_OK
        assert not Client.objects.filter(id=client_id).exists()

    def test_client_invoice_crud_lifecycle(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        client = Client.objects.create(name="Acme Corp", code="CL-ACME", country_code="GH")

        # 1. CREATE INVOICE
        url_inv = reverse("client-invoice-list-admin")
        inv_data = {
            "invoice_number": "INV-2026-001",
            "client_id": str(client.id),
            "issue_date": "2026-11-01",
            "due_date": "2026-11-30",
            "total_amount": 12500.0
        }
        res_create = api_client.post(url_inv, inv_data, format="json")
        assert res_create.status_code == status.HTTP_201_CREATED
        inv_id = res_create.data["data"]["id"]

        # 2. RETRIEVE
        detail_url = reverse("client-invoice-detail-admin", kwargs={"invoice_id": inv_id})
        res_get = api_client.get(detail_url)
        assert res_get.status_code == status.HTTP_200_OK
        assert Decimal(str(res_get.data["data"]["balance_due"])) == Decimal("12500.0000")

        # 3. PUBLIC STATEMENT
        pub_url = reverse("client-invoices-public", kwargs={"client_id": str(client.id)})
        res_pub = api_client.get(pub_url)
        assert res_pub.status_code == status.HTTP_200_OK

        # 4. AGING REPORT
        aging_url = reverse("receivables-aging-report-admin")
        res_aging = api_client.get(aging_url, {"country": "GH"})
        assert res_aging.status_code == status.HTTP_200_OK

        # 5. UPDATE INVOICE
        res_up = api_client.patch(detail_url, {"amount_paid": 5000.0}, format="json")
        assert res_up.status_code == status.HTTP_200_OK
        assert Decimal(str(res_up.data["data"]["balance_due"])) == Decimal("7500.0000")

        # 6. DELETE INVOICE
        res_del = api_client.delete(detail_url)
        assert res_del.status_code == status.HTTP_400_BAD_REQUEST  # Cannot delete with payment

    def test_invoice_lines_and_payment_receipt_allocation_lifecycle(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        client = Client.objects.create(name="Beta Logistics", code="CL-BETA", country_code="GH")
        from apps.ledger.models import Account, AccountType
        from apps.treasury.models import BankAccount
        gl_bank = Account.objects.create(code="1025-FNB-TEST", name="FNB Bank Test", account_type=AccountType.ASSET)
        bank_acc = BankAccount.objects.create(bank_name="FNB Ghana", account_number="987654321", gl_account=gl_bank)

        # 1. Create invoice with line items
        url_inv = reverse("client-invoice-list-admin")
        inv_payload = {
            "invoice_number": "INV-LINE-001",
            "client_id": str(client.id),
            "issue_date": "2026-11-01",
            "due_date": "2026-11-30",
            "lines": [
                {
                    "description": "HR Outsourcing Services",
                    "quantity": 10.0,
                    "unit_of_measurement": "Man-Days",
                    "unit_price": 500.0,
                    "discount": 0.0,
                    "tax_code": "VAT",
                    "tax_rate": 0.15
                }
            ]
        }
        res_inv = api_client.post(url_inv, inv_payload, format="json")
        assert res_inv.status_code == status.HTTP_201_CREATED
        inv_data = res_inv.data["data"]
        inv_id = inv_data["id"]
        # Subtotal: 5000, Tax (15%): 750, Total: 5750
        assert Decimal(str(inv_data["subtotal"])) == Decimal("5000.0000")
        assert Decimal(str(inv_data["tax_amount"])) == Decimal("750.0000")
        assert Decimal(str(inv_data["total_amount"])) == Decimal("5750.0000")
        assert inv_data["journal_entry"] is not None  # Automatically posted GL!

        # 2. Record Payment Receipt allocating partial amount
        rec_url = reverse("payment-receipt-list-admin")
        rec_payload = {
            "receipt_number": "REC-2026-001",
            "receipt_date": "2026-11-10",
            "client_id": str(client.id),
            "bank_account_id": str(bank_acc.id),
            "amount_received": 5750.0,
            "payment_method": "BANK_TRANSFER",
            "allocations": [
                {
                    "invoice_id": inv_id,
                    "amount": 5750.0
                }
            ]
        }
        res_rec = api_client.post(rec_url, rec_payload, format="json")
        assert res_rec.status_code == status.HTTP_201_CREATED
        assert res_rec.data["data"]["journal_entry"] is not None

        # Verify invoice is now PAID
        inv_detail_url = reverse("client-invoice-detail-admin", kwargs={"invoice_id": inv_id})
        res_chk = api_client.get(inv_detail_url)
        assert res_chk.data["data"]["status"] == ClientInvoiceStatus.PAID
        assert Decimal(str(res_chk.data["data"]["balance_due"])) == Decimal("0.0000")

        # 3. Customer Statement
        stmt_url = reverse("customer-statement-admin", kwargs={"client_id": str(client.id)})
        res_stmt = api_client.get(stmt_url)
        assert res_stmt.status_code == status.HTTP_200_OK
        assert len(res_stmt.data["data"]["transactions"]) == 2
        assert Decimal(str(res_stmt.data["data"]["closing_balance"])) == Decimal("0.0000")

