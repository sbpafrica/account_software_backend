import pytest
import uuid
from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.payroll_escrow.models import PayrollBatch, PayrollBatchStatus


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
class TestPayrollEscrowCRUD:
    def test_payroll_batch_crud_lifecycle(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        client_uuid = uuid.uuid4()

        # 1. CREATE
        url_create = reverse("payroll-batch-list-admin")
        batch_data = {
            "batch_code": "BATCH-2026-11",
            "client_id": str(client_uuid),
            "client_name": "MultiNational Client GH",
            "country_code": "GH",
            "month": 11,
            "year": 2026,
            "total_net_salaries": 45000.0,
            "total_statutory_taxes": 12000.0,
            "total_management_fee": 3000.0
        }
        res_create = api_client.post(url_create, batch_data, format="json")
        assert res_create.status_code == status.HTTP_201_CREATED
        batch_id = res_create.data["data"]["id"]

        # 2. LIST
        res_list = api_client.get(url_create)
        assert res_list.status_code == status.HTTP_200_OK
        assert any(b["id"] == batch_id for b in res_list.data["data"])

        # 3. RETRIEVE
        detail_url = reverse("payroll-batch-detail-admin", kwargs={"batch_id": batch_id})
        res_get = api_client.get(detail_url)
        assert res_get.status_code == status.HTTP_200_OK
        assert Decimal(str(res_get.data["data"]["total_funding_required"])) == Decimal("60000.0000")

        # 4. UPDATE
        res_up = api_client.put(detail_url, {"client_name": "MultiNational Client Group"}, format="json")
        assert res_up.status_code == status.HTTP_200_OK
        assert res_up.data["data"]["client_name"] == "MultiNational Client Group"

        # 5. PUBLIC ESCROW BALANCE
        pub_balance_url = reverse("payroll-client-balance-public", kwargs={"client_id": str(client_uuid)})
        res_bal = api_client.get(pub_balance_url)
        assert res_bal.status_code == status.HTTP_200_OK

        # 6. DELETE
        res_del = api_client.delete(detail_url)
        assert res_del.status_code == status.HTTP_200_OK
        assert not PayrollBatch.objects.filter(id=batch_id).exists()
