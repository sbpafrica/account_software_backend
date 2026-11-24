from django.core.management.base import BaseCommand
from apps.organizations.models import Organization
from apps.assets.models import FixedAsset, DepreciationRun
from apps.treasury.models import BankAccount
from apps.receivables.models import Client, ClientInvoice, PaymentReceipt
from apps.payables.models import Supplier, PurchaseOrder, GoodsReceivedNote, SupplierInvoice, PaymentVoucher, ExpenseClaim
from apps.payroll_escrow.models import PayrollBatch
from apps.budgeting.models import Budget
from apps.contracts.models import Contract
from apps.invoicing.models import Invoice, BillableItem, InvoiceCategory, InvoiceTemplate, RecurringSchedule
from apps.common.cache import CacheManager


class Command(BaseCommand):
    help = "Adopts all unassigned (organization=NULL) legacy records into the primary corporate tenant (SBP Africa Group Ltd)."

    def handle(self, *args, **options):
        primary_org = (
            Organization.objects.filter(is_inhouse=True).first()
            or Organization.objects.filter(slug='sbp-africa-group').first()
            or Organization.objects.order_by('created_at').first()
        )
        if not primary_org:
            self.stdout.write(self.style.ERROR("No primary organization found. Please register or seed an organization first."))
            return

        self.stdout.write(f"Binding all orphaned records to primary tenant: '{primary_org.name}' ({primary_org.id})...")

        models_to_backfill = [
            FixedAsset,
            DepreciationRun,
            BankAccount,
            Client,
            ClientInvoice,
            PaymentReceipt,
            Supplier,
            PurchaseOrder,
            GoodsReceivedNote,
            SupplierInvoice,
            PaymentVoucher,
            ExpenseClaim,
            PayrollBatch,
            Budget,
            Contract,
            Invoice,
            BillableItem,
            InvoiceCategory,
            InvoiceTemplate,
            RecurringSchedule,
        ]

        total_updated = 0
        for model in models_to_backfill:
            try:
                count = model.all_objects.filter(organization__isnull=True).update(organization=primary_org)
                if count > 0:
                    self.stdout.write(f"  - {model.__name__}: {count} records backfilled.")
                    total_updated += count
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"  - {model.__name__}: skipped ({exc})"))

        CacheManager.clear_all()
        self.stdout.write(self.style.SUCCESS(f"[+] Multi-tenant backfill complete: {total_updated} orphaned records assigned to '{primary_org.name}'."))
