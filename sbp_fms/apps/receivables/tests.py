import hmac
import hashlib
import json
import pytest
from decimal import Decimal
from unittest.mock import patch
from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.receivables.models import Client, ClientInvoice, ClientInvoiceStatus, PaymentReceipt


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


@pytest.mark.django_db
class TestReceivablesPaystackPayment:
    """
    Tests Paystack online payment for Client Invoices:
    1. Checkout initialization with idempotency.
    2. Synchronous verification with atomic double-entry GL posting.
    3. Idempotent re-verification.
    """

    @patch('apps.organizations.paystack.PaystackService.initialize_transaction')
    def test_invoice_paystack_initialize_and_idempotency(self, mock_init, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        client = Client.objects.create(name="Paystack Test Client", code="CL-PSTK-001", country_code="GH")
        inv = ClientInvoice.objects.create(
            invoice_number="INV-PSTK-001",
            client=client,
            issue_date="2026-11-01",
            due_date="2026-11-30",
            total_amount=Decimal("1500.0000"),
            amount_paid=Decimal("0.0000"),
            status=ClientInvoiceStatus.ISSUED
        )

        mock_ref = f"inv_{inv.id.hex[:8]}_test123"
        mock_init.return_value = {
            'authorization_url': 'https://checkout.paystack.com/auth_mock',
            'access_code': 'mock_access_code',
            'reference': mock_ref
        }

        url = reverse("invoice-paystack-initialize", kwargs={"invoice_id": str(inv.id)})
        idemp_key = "idemp_inv_init_test_001"

        # 1. Initialize checkout
        res = api_client.post(url, {"amount": 1500.0}, format="json", HTTP_IDEMPOTENCY_KEY=idemp_key)
        assert res.status_code == status.HTTP_201_CREATED
        assert res.data["data"]["authorization_url"] == "https://checkout.paystack.com/auth_mock"
        assert res.data["data"]["reference"] == mock_ref

        # 2. Idempotent replay: Calling again with same key returns cached response
        res_replay = api_client.post(url, {"amount": 1500.0}, format="json", HTTP_IDEMPOTENCY_KEY=idemp_key)
        assert res_replay.status_code == status.HTTP_201_CREATED
        assert res_replay.get("X-Idempotency-Replay") == "true"
        assert res_replay.data["data"]["reference"] == mock_ref

    @patch('apps.organizations.paystack.PaystackService.verify_transaction')
    def test_invoice_paystack_verify_and_atomic_gl_posting(self, mock_verify, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        client = Client.objects.create(name="Paystack Verify Client", code="CL-PSTK-002", country_code="GH")
        inv = ClientInvoice.objects.create(
            invoice_number="INV-PSTK-002",
            client=client,
            issue_date="2026-11-01",
            due_date="2026-11-30",
            total_amount=Decimal("2000.0000"),
            amount_paid=Decimal("0.0000"),
            status=ClientInvoiceStatus.ISSUED
        )

        mock_ref = f"inv_{inv.id.hex[:8]}_verify_success"
        mock_verify.return_value = {
            'status': 'success',
            'amount': 200000,  # 2000.00 GHS in pesewas
            'currency': 'GHS',
            'reference': mock_ref,
            'metadata': {
                'invoice_id': str(inv.id),
                'client_id': str(client.id)
            }
        }

        url = reverse("invoice-paystack-verify")
        idemp_key = "idemp_inv_ver_test_002"

        # 1. Verify payment
        res = api_client.post(url, {"reference": mock_ref}, format="json", HTTP_IDEMPOTENCY_KEY=idemp_key)
        assert res.status_code == status.HTTP_200_OK
        assert res.data["data"]["status"] == "SUCCESS"

        inv.refresh_from_db()
        assert inv.status == ClientInvoiceStatus.PAID
        assert inv.amount_paid == Decimal("2000.0000")
        assert inv.balance_due == Decimal("0.0000")

        # Verify PaymentReceipt was created with balanced GL Journal
        receipt = PaymentReceipt.objects.get(reference_number=mock_ref)
        assert receipt.payment_method == "PAYSTACK"
        assert receipt.amount_received == Decimal("2000.0000")
        assert receipt.journal_entry is not None
        assert receipt.journal_entry.source_module == "RECEIVABLES"

        # 2. Idempotent re-verification returns cached/confirmed result
        res_dup = api_client.post(url, {"reference": mock_ref}, format="json", HTTP_IDEMPOTENCY_KEY=idemp_key)
        assert res_dup.status_code == status.HTTP_200_OK
        assert res_dup.get("X-Idempotency-Replay") == "true"

    @patch('apps.organizations.paystack.PaystackService.verify_transaction')
    def test_paystack_webhook_invoice_payment_routing_and_deduplication(self, mock_verify, api_client):
        client = Client.objects.create(name="Webhook Client", code="CL-PSTK-003", country_code="GH")
        inv = ClientInvoice.objects.create(
            invoice_number="INV-PSTK-003",
            client=client,
            issue_date="2026-11-01",
            due_date="2026-11-30",
            total_amount=Decimal("3500.0000"),
            amount_paid=Decimal("0.0000"),
            status=ClientInvoiceStatus.ISSUED
        )

        mock_ref = f"inv_{inv.id.hex[:8]}_webhook_charge"
        mock_verify.return_value = {
            'status': 'success',
            'amount': 350000,
            'currency': 'GHS',
            'reference': mock_ref,
            'metadata': {'type': 'invoice_payment', 'invoice_id': str(inv.id), 'client_id': str(client.id)}
        }

        webhook_payload = {
            'event': 'charge.success',
            'id': f'evt_{inv.id.hex[:10]}',
            'data': {
                'id': 1234567,
                'status': 'success',
                'reference': mock_ref,
                'amount': 350000,
                'currency': 'GHS',
                'metadata': {'type': 'invoice_payment', 'invoice_id': str(inv.id)}
            }
        }
        raw_body = json.dumps(webhook_payload).encode('utf-8')
        secret = getattr(settings, 'PAYSTACK_SECRET_KEY', 'sk_test_mock_paystack_secret_key')
        sig = hmac.new(secret.encode('utf-8'), raw_body, hashlib.sha512).hexdigest()

        webhook_url = reverse("unified-paystack-webhook")

        # 1. First delivery: Processed
        res = api_client.post(
            webhook_url,
            data=raw_body,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=sig
        )
        assert res.status_code == status.HTTP_200_OK

        inv.refresh_from_db()
        assert inv.status == ClientInvoiceStatus.PAID
        assert inv.balance_due == Decimal("0.0000")

        # 2. Second duplicate delivery (Webhook replay): Acknowledged idempotently without duplicate receipt
        res_dup = api_client.post(
            webhook_url,
            data=raw_body,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=sig
        )
        assert res_dup.status_code == status.HTTP_200_OK
        assert res_dup.data["data"]["status"] == "ignored"

    def test_invoice_builder_and_custom_fields_lifecycle(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        client = Client.objects.create(
            name="Ashanti Gold Mining Consortium",
            code="CL-AGMC-01",
            country_code="GH",
            tax_id="TIN-AGMC-8910"
        )

        # 1. Fetch industry invoice presets
        presets_url = reverse("invoice-template-presets-admin")
        res_presets = api_client.get(presets_url)
        assert res_presets.status_code == status.HTTP_200_OK
        presets_data = res_presets.data["data"]
        assert len(presets_data) == 4
        preset_codes = [p["preset_code"] for p in presets_data]
        assert "STAFFING_WORKFORCE" in preset_codes
        assert "STANDARD_CORPORATE" in preset_codes
        assert "RECRUITMENT_PLACEMENTS" in preset_codes
        assert "CONSULTING_MANAGEMENT" in preset_codes

        # 2. Apply "STAFFING_WORKFORCE" preset to client as default
        apply_url = reverse("invoice-template-presets-admin")  # POST /presets/apply/ Wait, check URL name
        # Let's check the url name in urls.py: name='invoice-template-presets-admin' for presets
        # In urls.py: path('admin/invoice-templates/presets/', InvoiceTemplatePresetsAdminApi.as_view(), name='invoice-template-presets-admin')
        res_apply = api_client.post(presets_url, {
            "preset_code": "STAFFING_WORKFORCE",
            "client_id": str(client.id),
            "template_name": "Ashanti Gold Mining Timesheet Layout",
            "is_default": True
        }, format="json")
        assert res_apply.status_code == status.HTTP_201_CREATED
        tmpl_data = res_apply.data["data"]
        template_id = tmpl_data["id"]
        assert tmpl_data["layout_style"] == "DETAILED_STAFFING"
        assert len(tmpl_data["header_custom_fields"]) >= 3
        assert len(tmpl_data["line_custom_fields"]) >= 3

        client.refresh_from_db()
        assert str(client.default_template.id) == template_id

        # 3. Test Real-time Invoice Builder Preview API
        preview_url = reverse("invoice-builder-preview-admin")
        res_prev = api_client.post(preview_url, {
            "template_id": template_id,
            "sample_invoice": {
                "custom_fields": {
                    "po_number": "PO-AGMC-2026-9921",
                    "service_period": "October 2026",
                    "site_location": "Tarkwa Mine Site A"
                }
            }
        }, format="json")
        assert res_prev.status_code == status.HTTP_200_OK
        prev_data = res_prev.data["data"]
        assert "invoice" in prev_data
        assert "client" in prev_data
        assert "company" in prev_data
        assert "template" in prev_data
        assert "totals" in prev_data
        assert len(prev_data["invoice"]["header_custom_fields"]) >= 3

        # 4. Create Invoice with Custom Header Fields & Custom Line Columns
        inv_url = reverse("client-invoice-list-admin")
        inv_payload = {
            "invoice_number": f"INV-AGMC-{client.id.hex[:6]}",
            "client_id": str(client.id),
            "template_id": template_id,
            "issue_date": "2026-10-31",
            "due_date": "2026-11-30",
            "custom_fields": {
                "po_number": "PO-AGMC-2026-0042",
                "service_period": "October 2026",
                "site_location": "Tarkwa Concession Site B",
                "timesheet_approver": "Ing. Kwame Antwi (Mine Manager)"
            },
            "lines": [
                {
                    "description": "Heavy Machinery Operation & Excavation Services",
                    "quantity": 26.0,
                    "unit_of_measurement": "Days",
                    "unit_price": 500.0,
                    "discount": 0.0,
                    "tax_code": "VAT-15",
                    "tax_rate": 0.15,
                    "custom_fields": {
                        "staff_name": "Kofi Mensah (ID: SBP-084)",
                        "role_designation": "Excavator Operator",
                        "days_worked": 26,
                        "department": "Extraction Pit 2"
                    }
                },
                {
                    "description": "Articulated Dump Truck Driver Workforce",
                    "quantity": 26.0,
                    "unit_of_measurement": "Days",
                    "unit_price": 400.0,
                    "discount": 0.0,
                    "tax_code": "VAT-15",
                    "tax_rate": 0.15,
                    "custom_fields": {
                        "staff_name": "Yaw Boateng (ID: SBP-085)",
                        "role_designation": "Dump Truck Driver",
                        "days_worked": 26,
                        "department": "Haulage Fleet"
                    }
                }
            ]
        }
        res_inv = api_client.post(inv_url, inv_payload, format="json")
        assert res_inv.status_code == status.HTTP_201_CREATED
        created_inv = res_inv.data["data"]
        inv_id = created_inv["id"]
        assert created_inv["custom_fields"]["po_number"] == "PO-AGMC-2026-0042"
        assert len(created_inv["lines"]) == 2
        assert created_inv["lines"][0]["custom_fields"]["staff_name"] == "Kofi Mensah (ID: SBP-084)"

        # 5. Test Required Field Validation
        bad_payload = {
            "invoice_number": f"INV-BAD-{client.id.hex[:6]}",
            "client_id": str(client.id),
            "template_id": template_id,
            "issue_date": "2026-10-31",
            "due_date": "2026-11-30",
            "custom_fields": {}  # Missing required po_number and service_period
        }
        res_bad = api_client.post(inv_url, bad_payload, format="json")
        assert res_bad.status_code == status.HTTP_400_BAD_REQUEST

        # 6. Test Full Rendered Invoice Data API (with CompanyProfile and BankAccount present)
        from apps.ledger.models import Account, AccountType, CompanyProfile
        from apps.treasury.models import BankAccount
        CompanyProfile.objects.create(
            company_name="SBP Africa Ltd",
            business_address="14 Liberation Road, Accra",
            telephone="+233 30 200 1234",
            email="billing@sbpafrica.group",
            tax_identification_number="C0099887766",
        )
        bank_gl = Account.objects.create(
            code="1025",
            name="Ecobank Corporate",
            account_type=AccountType.ASSET,
            currency="GHS",
        )
        BankAccount.objects.create(
            bank_name="Ecobank Ghana",
            account_number="0123456789",
            branch_name="Ridge",
            swift_code="ECOCGHAC",
            currency="GHS",
            gl_account=bank_gl,
            is_active=True,
        )

        render_url = reverse("client-invoice-render-admin", kwargs={"invoice_id": inv_id})
        res_render = api_client.get(render_url)
        assert res_render.status_code == status.HTTP_200_OK
        render_data = res_render.data["data"]
        assert render_data["company"]["address"] == "14 Liberation Road, Accra"
        assert render_data["company"]["phone"] == "+233 30 200 1234"
        assert render_data["company"]["email"] == "billing@sbpafrica.group"
        assert render_data["bank_accounts"][0]["swift_code"] == "ECOCGHAC"
        assert render_data["template"]["layout_style"] == "DETAILED_STAFFING"
        assert render_data["client"]["name"] == "Ashanti Gold Mining Consortium"
        assert any(f["key"] == "po_number" and f["value"] == "PO-AGMC-2026-0042" for f in render_data["invoice"]["header_custom_fields"])
        assert len(render_data["lines"]) == 2
        assert render_data["lines"][0]["custom_fields"]["staff_name"] == "Kofi Mensah (ID: SBP-084)"



