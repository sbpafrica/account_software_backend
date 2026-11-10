import pytest
from decimal import Decimal
from datetime import date
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User
from apps.ledger.models import Account, AccountType
from apps.ledger.services import LedgerService
from apps.treasury.models import BankAccount, BankTransaction, BankStatement, BankStatementLine, BankReconciliation


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

    def test_cashbook_running_balance_and_filters(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        # Create GL Accounts
        bank_gl = Account.objects.create(
            code="1025-ECOBANK",
            name="Ecobank Operating Account",
            account_type=AccountType.ASSET,
            opening_balance=Decimal("10000.0000")
        )
        rev_gl = Account.objects.create(
            code="4010-SALES-REV",
            name="Service Revenue",
            account_type=AccountType.REVENUE
        )
        exp_gl = Account.objects.create(
            code="6010-RENT-EXP",
            name="Office Rent Expense",
            account_type=AccountType.OPEX
        )

        bank_acc = BankAccount.objects.create(
            bank_name="Ecobank Ghana",
            account_number="0101010101",
            gl_account=bank_gl
        )

        # 1. Post a receipt: DR Bank 5000, CR Revenue 5000 on 2026-11-05
        LedgerService.post_journal_entry(
            entry_number="JE-CB-001",
            posting_date=date(2026, 11, 5),
            description="Client remittance for invoice #100",
            source_module="cashbook_test",
            source_ref="INV-100",
            user=superuser,
            lines_data=[
                {"account": bank_gl, "debit": Decimal("5000.0000"), "credit": Decimal("0.0000")},
                {"account": rev_gl, "debit": Decimal("0.0000"), "credit": Decimal("5000.0000")}
            ]
        )

        # 2. Post a payment: DR Expense 2000, CR Bank 2000 on 2026-11-07
        LedgerService.post_journal_entry(
            entry_number="JE-CB-002",
            posting_date=date(2026, 11, 7),
            description="Monthly office rent disbursement",
            source_module="cashbook_test",
            source_ref="RENT-NOV",
            user=superuser,
            lines_data=[
                {"account": exp_gl, "debit": Decimal("2000.0000"), "credit": Decimal("0.0000")},
                {"account": bank_gl, "debit": Decimal("0.0000"), "credit": Decimal("2000.0000")}
            ]
        )

        # Call Cashbook API
        cb_url = reverse("treasury-cashbook-admin")
        res_cb = api_client.get(cb_url, {
            "bank_account_id": str(bank_acc.id),
            "start_date": "2026-11-01",
            "end_date": "2026-11-10"
        })
        assert res_cb.status_code == status.HTTP_200_OK
        data = res_cb.data["data"]

        assert Decimal(str(data["opening_balance"])) == Decimal("10000.0000")
        assert Decimal(str(data["total_debits"])) == Decimal("5000.0000")
        assert Decimal(str(data["total_credits"])) == Decimal("2000.0000")
        assert Decimal(str(data["closing_balance"])) == Decimal("13000.0000")
        assert len(data["entries"]) == 2

        # Check running balances
        entry1 = data["entries"][0]
        assert Decimal(str(entry1["debit"])) == Decimal("5000.0000")
        assert Decimal(str(entry1["running_balance"])) == Decimal("15000.0000")

        entry2 = data["entries"][1]
        assert Decimal(str(entry2["credit"])) == Decimal("2000.0000")
        assert Decimal(str(entry2["running_balance"])) == Decimal("13000.0000")

    def test_bank_statement_import_and_duplicate_prevention(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        gl_acc = Account.objects.create(
            code="1027-GCB-ACC",
            name="GCB Main Account",
            account_type=AccountType.ASSET
        )
        bank_acc = BankAccount.objects.create(
            bank_name="GCB Bank Ghana",
            account_number="2233445566",
            gl_account=gl_acc
        )

        csv_content = """Date,Reference,Description,Debit,Credit,Balance
2026-11-01,REF-001,Deposit from Client A,15000.00,0.00,15000.00
2026-11-03,CHQ-101,Vendor Payment ABC,0.00,4500.00,10500.00
2026-11-05,CHG-99,Bank Monthly Maintenance Fee,0.00,50.00,10450.00
"""

        import_url = reverse("bank-statement-import-admin")
        import_payload = {
            "bank_account_id": str(bank_acc.id),
            "statement_date": "2026-11-05",
            "file_name": "GCB_Statement_Nov2026.csv",
            "csv_content": csv_content,
            "opening_balance": 0.0,
            "closing_balance": 10450.00
        }

        # 1. First import
        res_import = api_client.post(import_url, import_payload, format="json")
        assert res_import.status_code == status.HTTP_201_CREATED
        assert res_import.data["data"]["total_lines"] == 3
        stmt_id = res_import.data["data"]["id"]

        # Verify Statement Detail
        detail_url = reverse("bank-statement-detail-admin", kwargs={"statement_id": stmt_id})
        res_detail = api_client.get(detail_url)
        assert res_detail.status_code == status.HTTP_200_OK
        assert len(res_detail.data["data"]["lines"]) == 3

        # 2. Re-importing overlapping/duplicate lines: duplicate hashes must be skipped
        res_reimport = api_client.post(import_url, import_payload, format="json")
        assert res_reimport.status_code == status.HTTP_201_CREATED
        # Zero new lines should be imported because all 3 hashes already exist
        assert res_reimport.data["data"]["total_lines"] == 0

    def test_two_way_bank_reconciliation_workflow(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        bank_gl = Account.objects.create(
            code="1028-CALBANK",
            name="CalBank Operating Account",
            account_type=AccountType.ASSET,
            opening_balance=Decimal("0.0000")
        )
        rev_gl = Account.objects.create(
            code="4020-CONSULTING-REV",
            name="Consulting Services Revenue",
            account_type=AccountType.REVENUE
        )
        fee_exp_gl = Account.objects.create(
            code="6090-BANK-CHARGES",
            name="Bank Maintenance & Service Charges",
            account_type=AccountType.OPEX
        )

        bank_acc = BankAccount.objects.create(
            bank_name="CalBank Ghana",
            account_number="9988776655",
            gl_account=bank_gl
        )

        # 1. Post GL transactions:
        # Receipt 10,000.00 (will match bank statement)
        LedgerService.post_journal_entry(
            entry_number="JE-REC-01",
            posting_date=date(2026, 11, 2),
            description="Client Payment 1",
            source_module="receivables",
            source_ref="INV-001",
            user=superuser,
            lines_data=[
                {"account": bank_gl, "debit": Decimal("10000.0000"), "credit": Decimal("0.0000")},
                {"account": rev_gl, "debit": Decimal("0.0000"), "credit": Decimal("10000.0000")}
            ]
        )
        # Receipt 3,000.00 (Deposit in transit: not yet in statement!)
        LedgerService.post_journal_entry(
            entry_number="JE-REC-02",
            posting_date=date(2026, 11, 4),
            description="Client Payment 2 in transit",
            source_module="receivables",
            source_ref="INV-002",
            user=superuser,
            lines_data=[
                {"account": bank_gl, "debit": Decimal("3000.0000"), "credit": Decimal("0.0000")},
                {"account": rev_gl, "debit": Decimal("0.0000"), "credit": Decimal("3000.0000")}
            ]
        )

        # 2. Import Bank Statement:
        # Inflow 10,000.00 (matches JE-REC-01)
        # Outflow 100.00 (Bank service charge, not yet in GL)
        csv_content = """Date,Reference,Description,Debit,Credit,Balance
2026-11-02,DEP-1001,Remittance from Customer,10000.00,0.00,10000.00
2026-11-03,FEE-001,Monthly Service Fee,0.00,100.00,9900.00
"""
        import_url = reverse("bank-statement-import-admin")
        res_import = api_client.post(import_url, {
            "bank_account_id": str(bank_acc.id),
            "statement_date": "2026-11-04",
            "file_name": "CalBank_Nov.csv",
            "csv_content": csv_content,
            "opening_balance": 0.0,
            "closing_balance": 9900.0
        }, format="json")
        assert res_import.status_code == status.HTTP_201_CREATED

        # 3. Check Bank Reconciliation Summary before matching
        summary_url = reverse("bank-reconciliation-summary-admin")
        res_sum = api_client.get(summary_url, {
            "bank_account_id": str(bank_acc.id),
            "statement_date": "2026-11-04"
        })
        assert res_sum.status_code == status.HTTP_200_OK
        sum_data = res_sum.data["data"]
        # GL Book balance = 13,000 (10,000 + 3,000)
        assert Decimal(str(sum_data["gl_book_balance"])) == Decimal("13000.0000")
        # Deposits in transit = 13,000 (all unmatched GL debits)
        assert Decimal(str(sum_data["deposits_in_transit_total"])) == Decimal("13000.0000")

        # 4. Run Auto-Match engine!
        auto_url = reverse("bank-reconciliation-auto-match-admin")
        res_auto = api_client.post(auto_url, {
            "bank_account_id": str(bank_acc.id),
            "tolerance_days": 3
        }, format="json")
        assert res_auto.status_code == status.HTTP_200_OK
        assert res_auto.data["data"]["matched_count"] == 1
        assert Decimal(str(res_auto.data["data"]["total_matched_amount"])) == Decimal("10000.0000")

        # 5. Resolve Bank Fee: Post adjustment journal directly from statement line
        fee_line = BankStatementLine.objects.get(reference="FEE-001")
        adj_url = reverse("bank-reconciliation-adjust-admin")
        res_adj = api_client.post(adj_url, {
            "statement_line_id": str(fee_line.id),
            "offset_account_id": str(fee_exp_gl.id),
            "description": "Monthly CalBank fee booked to expenses"
        }, format="json")
        assert res_adj.status_code == status.HTTP_201_CREATED

        # Verify fee_line is now reconciled
        fee_line.refresh_from_db()
        assert fee_line.is_reconciled is True
        assert fee_line.matched_journal_line is not None

        # 6. Check summary again:
        # GL Book balance = 13,000 - 100 = 12,900
        # Statement balance = 9,900
        # Deposits in transit = 3,000 (the only unmatched GL receipt)
        # Outstanding cheques = 0
        # Adjusted bank balance = 9,900 + 3,000 = 12,900
        # Adjusted book balance = 12,900
        # Reconciled Difference = 0.0000!
        res_sum2 = api_client.get(summary_url, {
            "bank_account_id": str(bank_acc.id),
            "statement_date": "2026-11-04"
        })
        assert res_sum2.status_code == status.HTTP_200_OK
        sum_data2 = res_sum2.data["data"]
        assert Decimal(str(sum_data2["adjusted_bank_balance"])) == Decimal("12900.0000")
        assert Decimal(str(sum_data2["adjusted_book_balance"])) == Decimal("12900.0000")
        assert Decimal(str(sum_data2["reconciled_difference"])) == Decimal("0.0000")
        assert sum_data2["is_balanced"] is True

        # 7. Save and Finalize Bank Reconciliation
        rec_url = reverse("bank-reconciliation-list-create-admin")
        res_rec = api_client.post(rec_url, {
            "bank_account_id": str(bank_acc.id),
            "statement_date": "2026-11-04",
            "notes": "November 2026 CalBank Reconciliation completed with zero variance."
        }, format="json")
        assert res_rec.status_code == status.HTTP_201_CREATED
        rec_id = res_rec.data["data"]["id"]

        finalize_url = reverse("bank-reconciliation-finalize-admin", kwargs={"reconciliation_id": rec_id})
        res_final = api_client.post(finalize_url, format="json")
        assert res_final.status_code == status.HTTP_200_OK
        assert res_final.data["data"]["status"] == "COMPLETED"

    def test_direct_bank_feed_fnb_integration(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        fnb_gl = Account.objects.create(
            code="1021-FNB-GH",
            name="First National Bank Operating Account",
            account_type=AccountType.ASSET,
            opening_balance=Decimal("10000.0000")
        )
        fnb_acc = BankAccount.objects.create(
            bank_name="First National Bank (FNB)",
            account_number="620011223344",
            currency="GHS",
            gl_account=fnb_gl
        )

        # 1. Configure Direct Bank Feed connection (FNB API)
        config_url = reverse("bank-feed-configure-admin", kwargs={"bank_account_id": str(fnb_acc.id)})
        res_cfg = api_client.post(config_url, {
            "provider": "FNB_DIRECT_API",
            "client_id": "FNB-SBP-CLIENT-0099",
            "client_secret": "SuperSecretFNBKey123",
            "auto_sync": True
        }, format="json")
        assert res_cfg.status_code == status.HTTP_200_OK
        assert res_cfg.data["data"]["provider"] == "FNB_DIRECT_API"
        assert res_cfg.data["data"]["client_id"] == "FNB-SBP-CLIENT-0099"
        assert res_cfg.data["data"]["status"] == "CONNECTED"

        # 2. Query Feed Status
        res_get_cfg = api_client.get(config_url)
        assert res_get_cfg.status_code == status.HTTP_200_OK
        assert res_get_cfg.data["data"]["bank_name"] == "First National Bank (FNB)"

        # 3. Trigger Live Bank Feed Sync
        sync_url = reverse("bank-feed-sync-admin", kwargs={"bank_account_id": str(fnb_acc.id)})
        res_sync = api_client.post(sync_url, {
            "start_date": "2026-11-01",
            "end_date": "2026-11-30"
        }, format="json")
        assert res_sync.status_code == status.HTTP_200_OK
        sync_data = res_sync.data["data"]
        assert sync_data["success"] is True
        assert sync_data["transactions_fetched"] == 2
        assert sync_data["status"] == "CONNECTED"

        # 4. Verify Bank Statement Lines were ingested into database
        from apps.treasury.models import BankStatementLine
        lines = BankStatementLine.objects.filter(statement__bank_account=fnb_acc)
        assert lines.count() == 2

        # 5. Trigger Second Live Sync: Hashes must prevent duplicates
        res_sync2 = api_client.post(sync_url, {
            "start_date": "2026-11-01",
            "end_date": "2026-11-30"
        }, format="json")
        assert res_sync2.status_code == status.HTTP_200_OK
        # Total lines in database should remain 2 due to SHA-256 deduplication
        assert BankStatementLine.objects.filter(statement__bank_account=fnb_acc).count() == 2

    def test_mono_open_banking_feed_lifecycle_and_idempotency(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        gl_acc = Account.objects.create(
            code="1025-ECOBANK-GH",
            name="Ecobank Ghana Main Operating Account",
            account_type=AccountType.ASSET,
            currency="GHS",
            country_code="GH"
        )
        eco_acc = BankAccount.objects.create(
            bank_name="Ecobank Ghana",
            account_number="1441009988776",
            currency="GHS",
            country_code="GH",
            gl_account=gl_acc
        )

        # 1. Retrieve Connect Session Info for Mono Connect widget
        session_url = reverse("bank-feed-session-admin", kwargs={"bank_account_id": str(eco_acc.id)})
        res_session = api_client.get(session_url)
        assert res_session.status_code == status.HTTP_200_OK
        assert res_session.data["data"]["bank_name"] == "Ecobank Ghana"
        assert res_session.data["data"]["is_connected"] is False
        assert "mono_public_key" in res_session.data["data"]

        # 2. Exchange One-time Code (Link Bank Account) with Idempotency Key
        exchange_url = reverse("bank-feed-exchange-admin", kwargs={"bank_account_id": str(eco_acc.id)})
        idemp_key = "idemp-mono-exchange-key-999"

        res_exch = api_client.post(
            exchange_url,
            {"code": "test_code_auth_ecobank_001", "provider": "MONO"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=idemp_key
        )
        assert res_exch.status_code == status.HTTP_200_OK
        exch_data = res_exch.data["data"]
        assert exch_data["status"] == "CONNECTED"
        assert exch_data["provider"] == "MONO"
        assert exch_data["institution_name"] == "Ecobank Ghana"
        assert exch_data["account_number_masked"] == "****5678"

        # 3. Duplicate Exchange Replay (Idempotency check)
        res_exch_dup = api_client.post(
            exchange_url,
            {"code": "test_code_auth_ecobank_001", "provider": "MONO"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=idemp_key
        )
        assert res_exch_dup.status_code == status.HTTP_200_OK
        assert res_exch_dup.headers.get("X-Idempotency-Replay") == "true"

        # 4. Sync Live Feed via Mono
        sync_url = reverse("bank-feed-sync-admin", kwargs={"bank_account_id": str(eco_acc.id)})
        res_sync = api_client.post(sync_url, {}, format="json")
        assert res_sync.status_code == status.HTTP_200_OK
        assert res_sync.data["data"]["success"] is True
        assert res_sync.data["data"]["transactions_fetched"] == 2

        # 5. Disconnect Feed
        disconnect_url = reverse("bank-feed-disconnect-admin", kwargs={"bank_account_id": str(eco_acc.id)})
        res_disc = api_client.post(disconnect_url, format="json")
        assert res_disc.status_code == status.HTTP_200_OK
        assert res_disc.data["data"]["status"] == "DISCONNECTED"


