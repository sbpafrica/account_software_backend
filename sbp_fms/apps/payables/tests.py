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

    def test_payment_voucher_workflow_and_ap_reports(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        from apps.payables.models import Supplier, SupplierInvoice, MatchStatus, PaymentVoucherStatus
        from apps.ledger.models import Account, AccountType
        from apps.treasury.models import BankAccount

        supplier = Supplier.objects.create(name="Office Depot Ghana", tax_id="TIN-DEPOT-123", country_code="GH", withholding_tax_rate=Decimal("0.0500"))
        gl_bank = Account.objects.create(code="1026-FNB-PAYABLES", name="FNB Bank Payables", account_type=AccountType.ASSET)
        bank_acc = BankAccount.objects.create(bank_name="FNB Ghana", account_number="1122334455", gl_account=gl_bank)

        # 1. Create a draft voucher
        v_url = reverse("payment-voucher-list-admin")
        v_payload = {
            "voucher_number": "PV-2026-001",
            "voucher_date": "2026-11-09",
            "payee_name": "Office Depot Ghana",
            "payee_type": "SUPPLIER",
            "supplier_id": str(supplier.id),
            "bank_account_id": str(bank_acc.id),
            "gross_amount": 2000.0,
            "wht_rate": 0.05,
            "description": "Stationery supplies payment"
        }
        res_v = api_client.post(v_url, v_payload, format="json")
        assert res_v.status_code == status.HTTP_201_CREATED
        v_id = res_v.data["data"]["id"]
        assert Decimal(str(res_v.data["data"]["net_amount"])) == Decimal("1900.0000")
        assert res_v.data["data"]["status"] == PaymentVoucherStatus.DRAFT

        # 2. Submit Voucher
        sub_url = reverse("payment-voucher-submit-admin", kwargs={"voucher_id": v_id})
        res_sub = api_client.post(sub_url, format="json")
        assert res_sub.status_code == status.HTTP_200_OK
        assert res_sub.data["data"]["status"] == PaymentVoucherStatus.SUBMITTED

        # 3. Review Voucher
        rev_url = reverse("payment-voucher-review-admin", kwargs={"voucher_id": v_id})
        res_rev = api_client.post(rev_url, format="json")
        assert res_rev.status_code == status.HTTP_200_OK
        assert res_rev.data["data"]["status"] == PaymentVoucherStatus.REVIEWED

        # 4. Approve Voucher (by another user for Segregation of Duties)
        approver = User.objects.create_superuser(
            email="finance.director@sbp-africa.com",
            password="DirectorPassword123!",
            first_name="Finance",
            last_name="Director"
        )
        api_client.force_authenticate(user=approver)
        app_url = reverse("payment-voucher-approve-admin", kwargs={"voucher_id": v_id})
        res_app = api_client.post(app_url, format="json")
        assert res_app.status_code == status.HTTP_200_OK
        assert res_app.data["data"]["status"] == PaymentVoucherStatus.APPROVED

        # 5. Mark Voucher Paid (Posts to General Ledger)
        pay_url = reverse("payment-voucher-mark-paid-admin", kwargs={"voucher_id": v_id})
        res_pay = api_client.post(pay_url, {"bank_account_id": str(bank_acc.id), "reference_number": "FT-990011"}, format="json")
        assert res_pay.status_code == status.HTTP_200_OK
        assert res_pay.data["data"]["status"] == PaymentVoucherStatus.PAID
        assert res_pay.data["data"]["journal_entry"] is not None

        # 6. AP Aging Report
        aging_url = reverse("payables-aging-report-admin")
        res_aging = api_client.get(aging_url, {"country": "GH"})
        assert res_aging.status_code == status.HTTP_200_OK

        # 7. Supplier Statement
        stmt_url = reverse("supplier-statement-admin", kwargs={"supplier_id": str(supplier.id)})
        res_stmt = api_client.get(stmt_url)
        assert res_stmt.status_code == status.HTTP_200_OK
        assert "closing_balance" in res_stmt.data["data"]

    def test_employee_expense_claim_lifecycle(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        from apps.ledger.models import Account, AccountType
        from apps.treasury.models import BankAccount
        from apps.payables.models import ExpenseClaimStatus

        employee = User.objects.create_user(
            email="staff.dev@sbp-africa.com",
            password="StaffPassword123!",
            first_name="Kofi",
            last_name="Mensah"
        )

        gl_bank = Account.objects.create(code="1029-EXP-BANK", name="Stanbic Bank Expenses", account_type=AccountType.ASSET)
        bank_acc = BankAccount.objects.create(bank_name="Stanbic Bank", account_number="5544332211", gl_account=gl_bank)
        gl_exp = Account.objects.create(code="6020-TRAVEL", name="Staff Travel & Per Diem", account_type=AccountType.OPEX)

        # 1. Create Expense Claim Draft
        claim_url = reverse("expense-claim-list-create-admin")
        claim_payload = {
            "employee_id": str(employee.id),
            "claim_date": "2026-11-06",
            "claim_type": "REIMBURSEMENT",
            "department": "Engineering",
            "cost_centre": "CC-ACCRA-HQ",
            "notes": "Flight ticket and per diem for client site visit",
            "lines": [
                {
                    "expense_date": "2026-11-06",
                    "category": "Travel",
                    "expense_account_id": str(gl_exp.id),
                    "description": "Accra to Kumasi Flight Ticket",
                    "amount": 1200.0,
                    "receipt_reference": "AWA-0091"
                },
                {
                    "expense_date": "2026-11-06",
                    "category": "Meals",
                    "expense_account_id": str(gl_exp.id),
                    "description": "Lunch & Dinner Per Diem",
                    "amount": 350.0,
                    "receipt_reference": "MEAL-001"
                }
            ]
        }
        res_claim = api_client.post(claim_url, claim_payload, format="json")
        assert res_claim.status_code == status.HTTP_201_CREATED
        claim_id = res_claim.data["data"]["id"]
        assert Decimal(str(res_claim.data["data"]["total_expenses"])) == Decimal("1550.0000")
        assert Decimal(str(res_claim.data["data"]["net_payable_to_employee"])) == Decimal("1550.0000")
        assert res_claim.data["data"]["status"] == ExpenseClaimStatus.DRAFT

        # 2. Submit Claim
        sub_url = reverse("expense-claim-submit-admin", kwargs={"claim_id": claim_id})
        res_sub = api_client.post(sub_url, format="json")
        assert res_sub.status_code == status.HTTP_200_OK
        assert res_sub.data["data"]["status"] == ExpenseClaimStatus.SUBMITTED

        # 3. Approve Claim (Superuser or Finance Manager)
        app_url = reverse("expense-claim-approve-admin", kwargs={"claim_id": claim_id})
        res_app = api_client.post(app_url, format="json")
        assert res_app.status_code == status.HTTP_200_OK
        assert res_app.data["data"]["status"] == ExpenseClaimStatus.APPROVED

        # 4. Settle Claim (generates payment voucher and marks PAID)
        settle_url = reverse("expense-claim-settle-admin", kwargs={"claim_id": claim_id})
        res_settle = api_client.post(settle_url, {"bank_account_id": str(bank_acc.id)}, format="json")
        assert res_settle.status_code == status.HTTP_200_OK
        assert res_settle.data["data"]["status"] == ExpenseClaimStatus.PAID
        assert res_settle.data["data"]["settlement_voucher"] is not None


