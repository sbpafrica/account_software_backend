import io
import pytest
from decimal import Decimal
import openpyxl
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from django.utils import timezone
import datetime

from apps.organizations.models import Organization, OrganizationMembership, OrganizationRole
from apps.organizations.context import set_current_organization, clear_current_organization
from apps.users.models import User, Role, UserRole
from apps.ledger.models import Account, AccountType
from apps.assets.models import FixedAsset, AssetCategory
from apps.common.models import ImportTemplate, ImportJob, ImportEntityType, ImportJobStatus, AuditLog


@pytest.fixture
def auth_tenant_setup():
    org = Organization.objects.create(
        name="SBP Africa Ltd",
        base_currency="GHS",
        plan_expires_at=timezone.now() + datetime.timedelta(days=30),
        is_inhouse=True
    )
    role_owner, _ = Role.objects.get_or_create(
        name=UserRole.ORGANIZATION_OWNER,
        defaults={"is_system_role": True}
    )
    user = User.objects.create_user(
        email="owner@sbpafrica.com",
        password="Password123!",
        first_name="Kwame",
        last_name="Mensah",
        role=role_owner
    )
    OrganizationMembership.objects.create(
        organization=org,
        user=user,
        role=OrganizationRole.OWNER,
        is_default=True
    )

    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_ORGANIZATION_ID=str(org.id))
    set_current_organization(org)

    yield {
        "client": client,
        "org": org,
        "user": user,
    }

    clear_current_organization()


@pytest.mark.django_db
class TestImportTemplatesAndMigration:

    def test_list_and_create_custom_template(self, auth_tenant_setup):
        client = auth_tenant_setup["client"]
        org = auth_tenant_setup["org"]

        # 1. List templates (auto-initializes default)
        url_list = reverse("imports-template-list-create")
        res_list = client.get(url_list, {"entity_type": ImportEntityType.FIXED_ASSET})
        assert res_list.status_code == status.HTTP_200_OK
        data = res_list.json()["data"]
        assert len(data) >= 1
        assert data[0]["entity_type"] == ImportEntityType.FIXED_ASSET

        # 2. Create custom template with renamed headers and an added custom column
        custom_columns = [
            {
                "header_name": "Equipment Tag",  # Renamed from Asset Tag
                "field_key": "asset_tag",
                "system_field": "asset_tag",
                "data_type": "string",
                "is_required": True,
                "default_value": "",
            },
            {
                "header_name": "Machine Description",  # Renamed from Asset Name
                "field_key": "name",
                "system_field": "name",
                "data_type": "string",
                "is_required": True,
                "default_value": "",
            },
            {
                "header_name": "Category",
                "field_key": "category_code",
                "system_field": "category_code",
                "data_type": "string",
                "is_required": True,
                "default_value": "",
            },
            {
                "header_name": "Bought Date",
                "field_key": "purchase_date",
                "system_field": "purchase_date",
                "data_type": "date",
                "is_required": True,
                "default_value": "",
            },
            {
                "header_name": "Cost (GHS)",
                "field_key": "purchase_cost",
                "system_field": "purchase_cost",
                "data_type": "number",
                "is_required": True,
                "default_value": 0.0,
            },
            {
                "header_name": "Engine Serial No",  # Custom new column
                "field_key": "engine_serial_no",
                "system_field": None,
                "data_type": "string",
                "is_required": False,
                "default_value": "",
                "is_custom": True,
            }
        ]

        payload = {
            "name": "SBP Plant & Equipment Custom Template",
            "entity_type": ImportEntityType.FIXED_ASSET,
            "description": "Customized format for SBP engineering fleet",
            "columns_schema": custom_columns,
            "is_default": True
        }
        res_create = client.post(url_list, payload, format="json")
        assert res_create.status_code == status.HTTP_201_CREATED
        tpl_data = res_create.json()["data"]
        assert tpl_data["name"] == "SBP Plant & Equipment Custom Template"
        assert tpl_data["columns_count"] == 6

        # 3. Retrieve template detail
        tpl_id = tpl_data["id"]
        url_detail = reverse("imports-template-detail", kwargs={"template_id": tpl_id})
        res_detail = client.get(url_detail)
        assert res_detail.status_code == status.HTTP_200_OK

        # 4. Update template (modify column name or delete optional column)
        updated_columns = list(custom_columns)
        updated_columns[0]["header_name"] = "Asset Barcode ID"  # Renamed again
        res_update = client.put(url_detail, {"columns_schema": updated_columns}, format="json")
        assert res_update.status_code == status.HTTP_200_OK
        assert res_update.json()["data"]["columns_schema"][0]["header_name"] == "Asset Barcode ID"

    def test_download_custom_excel_template(self, auth_tenant_setup):
        client = auth_tenant_setup["client"]
        url_download = reverse("imports-template-download")
        res = client.get(url_download, {"entity_type": ImportEntityType.FIXED_ASSET})
        assert res.status_code == status.HTTP_200_OK
        assert res["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        # Verify openpyxl can read the returned workbook
        wb = openpyxl.load_workbook(io.BytesIO(res.content))
        ws = wb.active
        headers = [cell.value for cell in ws[1]]
        assert "Asset Tag *" in headers or "Asset Tag" in headers
        assert "Asset Name *" in headers or "Asset Name" in headers

    def test_preview_and_commit_fixed_assets(self, auth_tenant_setup):
        client = auth_tenant_setup["client"]
        org = auth_tenant_setup["org"]

        # Setup GL accounts & AssetCategory
        gl_asset = Account.objects.create(code="1500-TEST", name="Equipment Asset", account_type=AccountType.ASSET)
        gl_accum = Account.objects.create(code="1509-TEST", name="Accum Depr", account_type=AccountType.ASSET)
        gl_depr = Account.objects.create(code="6050-TEST", name="Depr Expense", account_type=AccountType.OPEX)
        cat = AssetCategory.objects.create(
            code="HVY",
            name="Heavy Machinery",
            asset_gl_account=gl_asset,
            accumulated_depr_gl_account=gl_accum,
            depr_expense_gl_account=gl_depr
        )

        # Create an in-memory Excel workbook with test data
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Asset Tag", "Asset Name", "Category Code", "Acquisition Date", "Purchase Cost", "Serial Number"])
        ws.append(["AST-GEN-001", "Caterpillar 500kVA Generator", "HVY", "2025-03-10", "150000.00", "CAT-SN-99881"])
        ws.append(["AST-FLT-002", "Forklift Truck 3-Ton", "HVY", "2025-05-20", "85000.00", "FLT-SN-11223"])

        excel_buf = io.BytesIO()
        wb.save(excel_buf)
        excel_buf.seek(0)
        excel_buf.name = "assets_onboarding.xlsx"

        # 1. Preview upload (dry-run)
        url_preview = reverse("imports-preview")
        res_preview = client.post(
            url_preview,
            {"file": excel_buf, "entity_type": ImportEntityType.FIXED_ASSET},
            format="multipart"
        )
        assert res_preview.status_code == status.HTTP_200_OK
        preview_data = res_preview.json()["data"]
        assert preview_data["total_rows"] == 2
        assert preview_data["valid_rows_count"] == 2
        assert preview_data["error_rows_count"] == 0
        assert preview_data["can_import"] is True
        job_id = preview_data["job_id"]

        # Ensure no records were created in DB during preview
        assert FixedAsset.objects.filter(organization=org).count() == 0

        # 2. Commit the import
        url_commit = reverse("imports-commit")
        res_commit = client.post(
            url_commit,
            {"job_id": job_id, "validated_rows": preview_data["_validated_data"]},
            format="json"
        )
        assert res_commit.status_code == status.HTTP_200_OK
        commit_data = res_commit.json()["data"]
        assert commit_data["imported_count"] == 2
        assert commit_data["status"] == "COMPLETED"

        # Verify DB records created and scoped to tenant
        assets = FixedAsset.objects.filter(organization=org)
        assert assets.count() == 2
        gen_asset = assets.filter(asset_tag="AST-GEN-001").first()
        assert gen_asset is not None
        assert gen_asset.name == "Caterpillar 500kVA Generator"
        assert gen_asset.purchase_cost == Decimal("150000.0000")
        assert gen_asset.net_book_value == Decimal("150000.0000")

        # Verify audit log was generated
        audit_entry = AuditLog.objects.filter(organization=org, action="BULK_IMPORT").first()
        assert audit_entry is not None
        assert audit_entry.resource_type == ImportEntityType.FIXED_ASSET

    def test_preview_catches_validation_errors(self, auth_tenant_setup):
        client = auth_tenant_setup["client"]

        # Create workbook with bad data: missing cost, invalid category
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Asset Tag", "Asset Name", "Category Code", "Acquisition Date", "Purchase Cost"])
        ws.append(["AST-ERR-001", "Faulty Asset", "NONEXISTENT", "2025-01-01", "0.00"])

        excel_buf = io.BytesIO()
        wb.save(excel_buf)
        excel_buf.seek(0)
        excel_buf.name = "error_test.xlsx"

        url_preview = reverse("imports-preview")
        res = client.post(
            url_preview,
            {"file": excel_buf, "entity_type": ImportEntityType.FIXED_ASSET},
            format="multipart"
        )
        assert res.status_code == status.HTTP_200_OK
        data = res.json()["data"]
        assert data["can_import"] is False
        assert data["error_rows_count"] >= 1
        errors = data["errors"]
        cols = [e["column"] for e in errors]
        assert "Category Code" in cols
        assert "Purchase Cost" in cols

    def test_chart_of_accounts_preview_and_commit(self, auth_tenant_setup):
        client = auth_tenant_setup["client"]

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Account Code", "Account Name", "Account Type", "Currency", "Opening Balance", "Description"])
        ws.append(["1015", "Petty Cash Float", "ASSET", "GHS", "2500.00", "Office Petty Cash"])
        ws.append(["4050", "Consultancy Fees Income", "REVENUE", "GHS", "0.00", "Monthly Service Fees"])

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        buf.name = "coa_import.xlsx"

        url_preview = reverse("imports-preview")
        res_preview = client.post(url_preview, {"file": buf, "entity_type": ImportEntityType.CHART_OF_ACCOUNTS}, format="multipart")
        assert res_preview.status_code == status.HTTP_200_OK
        p_data = res_preview.json()["data"]
        assert p_data["can_import"] is True
        assert p_data["valid_rows_count"] == 2

        url_commit = reverse("imports-commit")
        res_commit = client.post(url_commit, {"job_id": p_data["job_id"], "validated_rows": p_data["_validated_data"]}, format="json")
        assert res_commit.status_code == status.HTTP_200_OK
        assert res_commit.json()["data"]["imported_count"] == 2

        assert Account.objects.filter(code="1015").exists()
        assert Account.objects.filter(code="4050").exists()

    def test_journal_entry_enforces_debits_equal_credits(self, auth_tenant_setup):
        client = auth_tenant_setup["client"]

        # Ensure accounts exist
        Account.objects.create(code="1010-JE", name="Cash", account_type=AccountType.ASSET)
        Account.objects.create(code="3010-JE", name="Owner Equity", account_type=AccountType.EQUITY)

        # Unbalanced entry: Debit 5000, Credit 4000
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Posting Date", "Entry Reference", "Account Code", "Debit Amount", "Credit Amount", "Description"])
        ws.append(["2026-01-01", "OPEN-01", "1010-JE", "5000.00", "0.00", "Cash in"])
        ws.append(["2026-01-01", "OPEN-01", "3010-JE", "0.00", "4000.00", "Equity"])

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        buf.name = "unbalanced_journal.xlsx"

        url_preview = reverse("imports-preview")
        res_preview = client.post(url_preview, {"file": buf, "entity_type": ImportEntityType.JOURNAL_ENTRY}, format="multipart")
        assert res_preview.status_code == status.HTTP_200_OK
        p_data = res_preview.json()["data"]
        assert p_data["can_import"] is False
        assert any("unbalanced" in e["error"].lower() for e in p_data["errors"])

    def test_template_reset_to_default(self, auth_tenant_setup):
        client = auth_tenant_setup["client"]

        url_reset = reverse("imports-template-reset-default")
        res = client.post(url_reset, {"entity_type": ImportEntityType.CLIENT}, format="json")
        assert res.status_code == status.HTTP_200_OK
        tpl = res.json()["data"]
        assert tpl["entity_type"] == ImportEntityType.CLIENT
        assert tpl["is_default"] is True
        assert tpl["columns_count"] >= 5
