import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User
from apps.common.models import AuditLog, DocumentAttachment
from apps.common.services import AuditService, DocumentService


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
class TestCommonAuditAndDocuments:
    def test_audit_log_recording_and_api(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        # 1. Record an audit log via AuditService
        log_entry = AuditService.log(
            actor_user=superuser,
            action="APPROVE",
            module="payables",
            resource_type="PaymentVoucher",
            resource_id="PV-2026-999",
            changes={"status": {"before": "REVIEWED", "after": "APPROVED"}},
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0"
        )
        assert log_entry.id is not None

        # 2. Query Audit Log API
        url = reverse("audit-log-list-admin")
        res = api_client.get(url, {"module": "payables", "action": "APPROVE"})
        assert res.status_code == status.HTTP_200_OK
        data = res.data["data"]
        assert len(data) >= 1
        assert data[0]["module"] == "payables"
        assert data[0]["resource_type"] == "PaymentVoucher"
        assert data[0]["action"] == "APPROVE"

    def test_document_attachment_vault_lifecycle(self, api_client, superuser):
        api_client.force_authenticate(user=superuser)

        # 1. Create document attachment
        url = reverse("document-attachment-list-create-admin")
        payload = {
            "module": "payables",
            "resource_id": "INV-SUPP-123",
            "file_name": "scanned_supplier_invoice_123.pdf",
            "file_path": "/var/storage/sbp_fms/attachments/inv_123.pdf",
            "file_size_bytes": 1048576,
            "mime_type": "application/pdf",
            "file_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        }
        res_create = api_client.post(url, payload, format="json")
        assert res_create.status_code == status.HTTP_201_CREATED
        doc_id = res_create.data["data"]["id"]

        # 2. List attachments for resource
        res_list = api_client.get(url, {"module": "payables", "resource_id": "INV-SUPP-123"})
        assert res_list.status_code == status.HTTP_200_OK
        assert len(res_list.data["data"]) == 1
        assert res_list.data["data"][0]["file_name"] == "scanned_supplier_invoice_123.pdf"

        # 3. Delete attachment
        del_url = reverse("document-attachment-delete-admin", kwargs={"attachment_id": doc_id})
        res_del = api_client.delete(del_url)
        assert res_del.status_code == status.HTTP_200_OK
        assert not DocumentAttachment.objects.filter(id=doc_id).exists()

    def test_openapi_schema_formats_and_downloads(self, api_client):
        # 1. JSON export endpoint
        res_json = api_client.get(reverse("schema-json"))
        assert res_json.status_code == status.HTTP_200_OK
        assert "application/json" in res_json["Content-Type"]
        assert "openapi" in res_json.json()

        # 2. JSON download with attachment disposition
        res_dl_json = api_client.get(reverse("schema-json") + "?download=1")
        assert res_dl_json.status_code == status.HTTP_200_OK
        assert "attachment" in res_dl_json["Content-Disposition"]

        # 3. YAML export endpoint
        res_yaml = api_client.get(reverse("schema-yaml"))
        assert res_yaml.status_code == status.HTTP_200_OK
        assert "yaml" in res_yaml["Content-Type"]

        # 4. Download dispatcher endpoint
        res_dl = api_client.get(reverse("schema-download") + "?format=json")
        assert res_dl.status_code == status.HTTP_200_OK
        assert "attachment" in res_dl["Content-Disposition"]

        # 5. Swagger UI has download links rendered
        res_docs = api_client.get(reverse("swagger-ui"))
        assert res_docs.status_code == status.HTTP_200_OK
        assert "Download JSON" in res_docs.content.decode()

        # 6. ReDoc has download links rendered
        res_redoc = api_client.get(reverse("redoc"))
        assert res_redoc.status_code == status.HTTP_200_OK
        assert "Download JSON" in res_redoc.content.decode()
