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
        payload = {
            "country_code": "GH",
            "gross_salary": 10000.0
        }
        res = api_client.post(calc_url, payload, format="json")
        assert res.status_code == status.HTTP_200_OK
        assert "employee_ssnit" in res.data["data"]
        assert "employer_ssnit" in res.data["data"]
        assert "total_ssnit_liability" in res.data["data"]

