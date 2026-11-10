import pytest
from decimal import Decimal
from datetime import date
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User
from apps.ledger.models import Account, AccountType
from apps.treasury.models import BankAccount
from apps.assets.models import AssetCategory, FixedAsset, AssetStatus, DepreciationMethod, DepreciationRunStatus


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
class TestFixedAssetsLifecycle:
    def test_fixed_asset_register_depreciation_and_disposal(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        # 1. Setup GL Accounts for Fixed Assets
        gl_asset = Account.objects.create(code="1510-COMPUTERS", name="Computer Equipment Cost", account_type=AccountType.ASSET)
        gl_accum = Account.objects.create(code="1519-ACCUM-DEP-COMP", name="Accumulated Depreciation - Computers", account_type=AccountType.ASSET)
        gl_depr_exp = Account.objects.create(code="6050-DEP-EXPENSE", name="Depreciation Expense - Computers", account_type=AccountType.OPEX)
        gl_gain_loss = Account.objects.create(code="7010-GAIN-LOSS-DISP", name="Gain/Loss on Asset Disposal", account_type=AccountType.REVENUE)
        gl_bank = Account.objects.create(code="1021-STANBIC", name="Stanbic Bank Cash", account_type=AccountType.ASSET)
        bank_acc = BankAccount.objects.create(bank_name="Stanbic Bank", account_number="9000112233", gl_account=gl_bank)

        # 2. CREATE ASSET CATEGORY
        cat_url = reverse("asset-category-list-create-admin")
        cat_payload = {
            "code": "IT-EQUIP",
            "name": "Information Technology Equipment",
            "default_useful_life_years": 3,
            "default_depreciation_method": "STRAIGHT_LINE",
            "asset_gl_account_id": str(gl_asset.id),
            "accumulated_depr_gl_account_id": str(gl_accum.id),
            "depr_expense_gl_account_id": str(gl_depr_exp.id),
            "country_code": "GH"
        }
        res_cat = api_client.post(cat_url, cat_payload, format="json")
        assert res_cat.status_code == status.HTTP_201_CREATED
        cat_id = res_cat.data["data"]["id"]

        # 3. REGISTER FIXED ASSET
        # Cost: 36,000.00 GHS, Useful Life: 3 years (36 months), Salvage: 0.00 -> Monthly depr = 1,000.00 GHS
        asset_url = reverse("fixed-asset-list-create-admin")
        asset_payload = {
            "asset_tag": "AST-MACBOOK-001",
            "name": "MacBook Pro M3 Max 16-inch",
            "description": "Dev machine for senior software engineer",
            "category_id": cat_id,
            "purchase_date": "2026-11-01",
            "purchase_cost": 36000.0,
            "salvage_value": 0.0,
            "useful_life_years": 3,
            "depreciation_method": "STRAIGHT_LINE",
            "department": "Engineering",
            "cost_centre": "CC-ACCRA-HQ",
            "location": "Accra Office Floor 3"
        }
        res_asset = api_client.post(asset_url, asset_payload, format="json")
        assert res_asset.status_code == status.HTTP_201_CREATED
        asset_data = res_asset.data["data"]
        asset_id = asset_data["id"]
        assert Decimal(str(asset_data["purchase_cost"])) == Decimal("36000.0000")
        assert Decimal(str(asset_data["net_book_value"])) == Decimal("36000.0000")
        assert Decimal(str(asset_data["accumulated_depreciation"])) == Decimal("0.0000")
        assert asset_data["status"] == "ACTIVE"

        # 4. CHECK ASSET REGISTER SUMMARY
        summary_url = reverse("asset-register-summary-admin")
        res_sum = api_client.get(summary_url)
        assert res_sum.status_code == status.HTTP_200_OK
        sum_data = res_sum.data["data"]
        assert sum_data["total_asset_count"] == 1
        assert sum_data["active_asset_count"] == 1
        assert Decimal(str(sum_data["total_acquisition_cost"])) == Decimal("36000.0000")
        assert Decimal(str(sum_data["total_net_book_value"])) == Decimal("36000.0000")

        # 5. CALCULATE DEPRECIATION RUN
        # For 1 month: 36,000 / 36 = 1,000.0000 GHS
        calc_url = reverse("depreciation-run-list-calculate-admin")
        res_calc = api_client.post(calc_url, {"period_end_date": "2026-11-30"}, format="json")
        assert res_calc.status_code == status.HTTP_201_CREATED
        run_data = res_calc.data["data"]
        run_id = run_data["id"]
        assert run_data["status"] == "DRAFT"
        assert run_data["total_assets_processed"] == 1
        assert Decimal(str(run_data["total_depreciation"])) == Decimal("1000.0000")

        # 6. POST DEPRECIATION RUN TO GENERAL LEDGER
        post_url = reverse("depreciation-run-post-admin", kwargs={"run_id": run_id})
        res_post = api_client.post(post_url, format="json")
        assert res_post.status_code == status.HTTP_200_OK
        assert res_post.data["data"]["status"] == "POSTED"
        assert res_post.data["data"]["journal_entry"] is not None

        # Verify Fixed Asset balances updated
        res_asset_updated = api_client.get(reverse("fixed-asset-detail-admin", kwargs={"asset_id": asset_id}))
        assert res_asset_updated.status_code == status.HTTP_200_OK
        a_data = res_asset_updated.data["data"]
        assert Decimal(str(a_data["accumulated_depreciation"])) == Decimal("1000.0000")
        assert Decimal(str(a_data["net_book_value"])) == Decimal("35000.0000")

        # 7. CHECK ASSET DEPRECIATION SCHEDULE
        sched_url = reverse("fixed-asset-schedule-admin", kwargs={"asset_id": asset_id})
        res_sched = api_client.get(sched_url)
        assert res_sched.status_code == status.HTTP_200_OK
        lines = res_sched.data["data"]
        assert len(lines) == 1
        assert Decimal(str(lines[0]["depreciation_amount"])) == Decimal("1000.0000")
        assert Decimal(str(lines[0]["book_value_after"])) == Decimal("35000.0000")

        # 8. DISPOSE / DERECOGNIZE FIXED ASSET
        # NBV is 35,000. Sale proceeds: 38,000. Gain on disposal = +3,000 GHS.
        disp_url = reverse("fixed-asset-dispose-admin", kwargs={"asset_id": asset_id})
        disp_payload = {
            "disposal_date": "2026-12-01",
            "sale_proceeds": 38000.0,
            "bank_account_id": str(bank_acc.id),
            "gain_loss_account_id": str(gl_gain_loss.id)
        }
        res_disp = api_client.post(disp_url, disp_payload, format="json")
        assert res_disp.status_code == status.HTTP_200_OK
        disp_asset = res_disp.data["data"]
        assert disp_asset["status"] == "DISPOSED"
        assert Decimal(str(disp_asset["disposal_proceeds"])) == Decimal("38000.0000")
        assert Decimal(str(disp_asset["disposal_gain_loss"])) == Decimal("3000.0000")
