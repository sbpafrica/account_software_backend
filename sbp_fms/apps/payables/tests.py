import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.payables.models import Supplier, PurchaseOrder, GoodsReceivedNote, SupplierInvoice, MatchStatus


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
class TestPayablesCRUD:
    def test_supplier_and_3way_match_lifecycle(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        # 1. CREATE SUPPLIER
        sup_url = reverse("supplier-list-admin")
        sup_data = {
            "name": "Accra Stationery Supplies",
            "tax_id": "TIN-998877",
            "country_code": "GH",
            "wht_rate": 0.0750,
            "bank_account_number": "1234567890",
            "bank_name": "FNB Ghana"
        }
        res_sup = api_client.post(sup_url, sup_data, format="json")
        assert res_sup.status_code == status.HTTP_201_CREATED
        supplier_id = res_sup.data["data"]["id"]

        # 2. CREATE PURCHASE ORDER
        po_url = reverse("purchase-order-list-admin")
        po_data = {
            "po_number": "PO-2026-001",
            "supplier_id": supplier_id,
            "total_approved_amount": 5000.0,
            "lines": [
                {"item_code": "PAPER-A4", "quantity": 100, "approved_unit_price": 50.0}
            ]
        }
        res_po = api_client.post(po_url, po_data, format="json")
        assert res_po.status_code == status.HTTP_201_CREATED
        po_id = res_po.data["data"]["id"]

        # 3. CREATE GOODS RECEIVED NOTE
        grn_url = reverse("grn-list-admin")
        grn_data = {
            "grn_number": "GRN-2026-001",
            "po_id": po_id,
            "received_date": "2026-11-05",
            "lines": [
                {"item_code": "PAPER-A4", "received_quantity": 100}
            ]
        }
        res_grn = api_client.post(grn_url, grn_data, format="json")
        assert res_grn.status_code == status.HTTP_201_CREATED
        grn_id = res_grn.data["data"]["id"]

        # 4. CREATE SUPPLIER INVOICE
        inv_url = reverse("supplier-invoice-list-admin")
        inv_data = {
            "invoice_number": "BILL-001",
            "supplier_id": supplier_id,
            "po_id": po_id,
            "grn_id": grn_id,
            "gross_amount": 5000.0,
            "lines": [
                {"item_code": "PAPER-A4", "billed_quantity": 100, "billed_unit_price": 50.0}
            ]
        }
        res_inv = api_client.post(inv_url, inv_data, format="json")
        assert res_inv.status_code == status.HTTP_201_CREATED
        inv_id = res_inv.data["data"]["id"]

        # 5. EXECUTE 3-WAY MATCH
        match_url = reverse("supplier-invoice-match-admin", kwargs={"invoice_id": inv_id})
        res_match = api_client.post(match_url, format="json")
        assert res_match.status_code == status.HTTP_200_OK
        assert res_match.data["data"]["success"] is True

        # 6. PUBLIC INVOICE STATUS
        pub_status_url = reverse("supplier-invoice-status-public", kwargs={"invoice_id": inv_id})
        res_pub = api_client.get(pub_status_url)
        assert res_pub.status_code == status.HTTP_200_OK
        assert res_pub.data["data"]["match_status"] == MatchStatus.MATCHED
