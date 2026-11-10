import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.ledger.models import Account, AccountType, JournalEntry, JournalEntryStatus


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
