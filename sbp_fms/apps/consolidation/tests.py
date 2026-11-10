import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.ledger.models import Account, AccountType
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
class TestConsolidationCRUD:
    def test_exchange_rate_and_fx_revaluation(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        # 1. Create Exchange Rate (1 USD = 15.500000 GHS)
        rate_url = reverse("exchange-rate-list-create-admin")
        rate_payload = {
            "from_currency": "USD",
            "to_currency": "GHS",
            "rate_date": "2026-11-30",
            "rate": 15.500000,
            "rate_type": "CLOSING"
        }
        res_rate = api_client.post(rate_url, rate_payload, format="json")
        assert res_rate.status_code == status.HTTP_201_CREATED
        assert Decimal(str(res_rate.data["data"]["rate"])) == Decimal("15.500000")

        # 2. List Exchange Rates
        res_list = api_client.get(rate_url, {"from_currency": "USD"})
        assert res_list.status_code == status.HTTP_200_OK
        assert len(res_list.data["data"]) >= 1

        # 3. Create USD Foreign Currency Bank Account and post initial transaction
        usd_bank_acct = Account.objects.create(
            code="1025-USD-STANBIC",
            name="Stanbic USD Operating Account",
            account_type=AccountType.ASSET,
            currency="USD",
            country_code="GH"
        )
        ghs_equity = Account.objects.create(
            code="3000-CAPITAL-GH",
            name="Shareholder Capital Contribution",
            account_type=AccountType.EQUITY,
            currency="GHS",
            country_code="GH"
        )

        # Initial deposit of 10,000 USD (at booking rate 10.0 GHS = 100,000 GHS)
        LedgerService.post_journal_entry(
            entry_number="JE-USD-DEP-001",
            posting_date="2026-11-01",
            description="Initial USD Capital Deposit",
            source_module="TREASURY",
            source_ref="DEP-001",
            user=superuser,
            lines_data=[
                {"account": usd_bank_acct, "debit": Decimal("10000.0000"), "credit": Decimal("0.0000"), "country_code": "GH"},
                {"account": ghs_equity, "debit": Decimal("0.0000"), "credit": Decimal("10000.0000"), "country_code": "GH"}
            ]
        )

        # 4. Consolidated Trial Balance
        tb_url = reverse("consolidated-trial-balance-admin")
        res_tb = api_client.get(tb_url, {"reporting_currency": "GHS", "as_of_date": "2026-11-30"})
        assert res_tb.status_code == status.HTTP_200_OK
        tb_data = res_tb.data["data"]
        assert tb_data["reporting_currency"] == "GHS"
        assert len(tb_data["accounts"]) >= 2
        # USD bank account should be translated at 15.5 rate -> 155,000 GHS
        usd_item = next(item for item in tb_data["accounts"] if item["account_code"] == "1025-USD-STANBIC")
        assert Decimal(str(usd_item["exchange_rate"])) == Decimal("15.500000")
        assert Decimal(str(usd_item["consolidated_debit"])) == Decimal("155000.0000")

        # 5. Execute Month-End FX Revaluation Run
        rev_url = reverse("fx-revaluation-run-admin")
        rev_payload = {
            "revaluation_date": "2026-11-30",
            "reporting_currency": "GHS",
            "notes": "November 2026 month-end revaluation"
        }
        res_rev = api_client.post(rev_url, rev_payload, format="json")
        assert res_rev.status_code == status.HTTP_201_CREATED
        rev_data = res_rev.data["data"]
        # Unrealized Gain = (10,000 * 15.5) - 10,000 = 145,000 GHS gain
        assert Decimal(str(rev_data["total_gain_loss"])) == Decimal("145000.0000")
        assert rev_data["journal_entry_number"] is not None

    def test_groq_exchange_rate_service_and_caching(self):
        from apps.consolidation.groq_fx import GroqExchangeRateService
        from apps.consolidation.models import ExchangeRate, RateType

        # 1. Fetch live rate (first query - not cached)
        result1 = GroqExchangeRateService.fetch_live_rate(from_currency="USD", to_currency="GHS")
        assert result1["from_currency"] == "USD"
        assert result1["to_currency"] == "GHS"
        assert result1["rate"] > 0
        assert result1["is_cached"] is False
        assert "xe.com" in result1["source"]

        # 2. Fetch live rate again (second query - served from memory cache)
        result2 = GroqExchangeRateService.fetch_live_rate(from_currency="USD", to_currency="GHS")
        assert result2["rate"] == result1["rate"]
        assert result2["is_cached"] is True

        # 3. Force refresh busts cache
        result3 = GroqExchangeRateService.fetch_live_rate(from_currency="USD", to_currency="GHS", force_refresh=True)
        assert result3["is_cached"] is False

        # 4. Spot rate was persisted in ExchangeRate table
        spot_rate = ExchangeRate.objects.filter(
            from_currency="USD",
            to_currency="GHS",
            rate_type=RateType.SPOT
        ).first()
        assert spot_rate is not None
        assert spot_rate.rate == result1["rate"]

    def test_live_exchange_rate_admin_api(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)
        url = reverse("exchange-rate-live-admin")

        # Query USD to GHS
        resp = api_client.get(url, {"from_currency": "USD", "to_currency": "GHS"})
        assert resp.status_code == status.HTTP_200_OK
        data = resp.data["data"]
        assert data["from_currency"] == "USD"
        assert data["to_currency"] == "GHS"
        assert Decimal(str(data["rate"])) > 0

        # Query with force_refresh
        resp_refresh = api_client.get(url, {"from_currency": "USD", "to_currency": "GHS", "force_refresh": "true"})
        assert resp_refresh.status_code == status.HTTP_200_OK
        assert resp_refresh.data["data"]["is_cached"] is False

