import uuid
from django.conf import settings
from django.db import models


class BaseModel(models.Model):
    """
    [DEVELOPER NOTE]: Abstract base model inherited by all database entities in SBP-FMS.
    Provides standard UUID primary keys and immutable creation/update audit timestamps.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantQuerySet(models.QuerySet):
    """
    SaaS Tenant QuerySet providing explicit tenant filtering and unscoped access.
    """
    def for_tenant(self, organization):
        if organization:
            return self.filter(organization=organization)
        return self

    def unscoped(self):
        """Bypasses automatic tenant isolation for administrative or system jobs."""
        return self.all()


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    """
    SaaS Tenant Manager that automatically restricts queries to the active tenant in context.
    """
    def get_queryset(self):
        qs = super().get_queryset()
        try:
            from apps.organizations.context import get_current_organization
            current_org = get_current_organization()
            if current_org:
                return qs.filter(organization=current_org)
        except ImportError:
            pass
        return qs


class TenantModel(BaseModel):
    """
    [SAAS MULTI-TENANT BASE MODEL]:
    Abstract base model for all tenant-scoped financial and business entities.
    Automatically assigns the active organization on save and restricts queries.
    """
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_set',
        db_index=True,
        null=True,
        blank=True,
        help_text="Tenant organization that owns this record."
    )

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.organization_id:
            try:
                from apps.organizations.context import get_current_organization
                current_org = get_current_organization()
                if current_org:
                    self.organization = current_org
            except ImportError:
                pass
        super().save(*args, **kwargs)


class AuditLog(models.Model):
    """
    Enterprise immutable audit log recording every system mutation, financial posting, and approval.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    action = models.CharField(max_length=50, db_index=True)  # CREATE, UPDATE, DELETE, POST, REVERSE, APPROVE, REJECT
    module = models.CharField(max_length=50, db_index=True)  # ledger, payables, receivables, treasury, payroll
    resource_type = models.CharField(max_length=100, db_index=True)  # JournalEntry, SupplierInvoice, PaymentVoucher
    resource_id = models.CharField(max_length=100, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    changes = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        actor = self.actor_user.email if self.actor_user else 'SYSTEM'
        return f"[{self.timestamp}] {actor} -> {self.action} on {self.resource_type}:{self.resource_id}"


class DocumentAttachment(BaseModel):
    """
    Central document vault storing proofs, scanned invoices, vendor receipts, and contracts.
    """
    module = models.CharField(max_length=50, db_index=True)
    resource_id = models.CharField(max_length=100, db_index=True)
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500, blank=True, default='')
    file_size_bytes = models.PositiveIntegerField(default=0)
    mime_type = models.CharField(max_length=100, blank=True, default='application/octet-stream')
    file_hash = models.CharField(max_length=64, blank=True, default='', db_index=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.file_name} ({self.file_size_bytes} bytes) - {self.module}:{self.resource_id}"


class IdempotencyRecord(BaseModel):
    """
    [ENTERPRISE FINANCIAL IDEMPOTENCY]:
    Prevents duplicate transactions, double billing, duplicate journals, and redundant webhook processing.
    Stores request hashes and exact completed response payloads for replay.
    """
    key = models.CharField(max_length=255, unique=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    organization = models.ForeignKey('organizations.Organization', null=True, blank=True, on_delete=models.CASCADE, related_name='+')
    request_path = models.CharField(max_length=255)
    request_method = models.CharField(max_length=10)
    request_digest = models.CharField(max_length=64, blank=True, default='')  # SHA-256 of payload
    response_status_code = models.PositiveIntegerField(null=True, blank=True)
    response_headers = models.JSONField(default=dict, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    is_processing = models.BooleanField(default=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"IdempotencyKey {self.key} [{self.request_method} {self.request_path}] - Status: {self.response_status_code}"
