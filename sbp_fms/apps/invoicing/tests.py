import datetime
from decimal import Decimal
import pytest
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.common.cache import CacheManager, make_cache_key
from apps.receivables.models import Client
from apps.ledger.models import Account, AccountType, JournalEntry
from apps.invoicing.models import (
    InvoiceCategory,
    InvoiceType,
    InvoiceStatus,
    InvoiceLayoutStyle,
    InvoiceTemplate,
    BillableItem,
    Invoice,
    InvoiceLine,
    InvoiceTaxLine,
    RecurringSchedule,
    RecurringScheduleStatus,
    RecurringFrequency,
)
from apps.invoicing.selectors import InvoicingSelector
from apps.invoicing.services import InvoicingService


@pytest.fixture
def setup_data(db):
    User = get_user_model()
    admin_user, _ = User.objects.get_or_create(
        email='admin@sbp-africa.com',
        defaults={'first_name': 'Admin', 'last_name': 'User', 'is_superuser': True, 'is_staff': True}
    )

    client, _ = Client.objects.get_or_create(
        code='CLI-GOLD-001',
        defaults={
            'name': 'AngloGold Ashanti Ltd',
            'country_code': 'GH',
            'billing_address': 'Obuasi Mine Site, Ashanti Region, Ghana',
            'tax_id': 'C0008899112',
            'email': 'procurement@anglogold.com',
        }
    )

    return {
        'user': admin_user,
        'client': client,
    }


@pytest.mark.django_db
class TestInvoiceCategoryServices:
    def test_seed_defaults_and_custom_category_creation(self, setup_data):
        # 1. Seed defaults
        categories = InvoicingService.invoice_category_seed_defaults()
        assert len(categories) >= 4
        assert InvoiceCategory.objects.filter(code='WORKFORCE_OUTSOURCING').exists()

        # 2. Admin adds custom vertical category on the fly
        custom_cat = InvoicingService.invoice_category_create(
            name="Renewable Energy & Solar Installations",
            code="SOLAR_ENERGY",
            description="Mine site solar grid installation and operational maintenance.",
        )
        assert custom_cat.id is not None
        assert custom_cat.code == "SOLAR_ENERGY"
        assert custom_cat.is_system is False

        # 3. Test caching and selector
        cached_list = InvoicingSelector.invoice_category_list()
        assert any(c.code == 'SOLAR_ENERGY' for c in cached_list)

        # 4. Invalidation on update
        InvoicingService.invoice_category_update(
            category_id=str(custom_cat.id),
            description="Updated solar energy scope"
        )
        updated_list = InvoicingSelector.invoice_category_list()
        updated_cat = [c for c in updated_list if c.code == 'SOLAR_ENERGY'][0]
        assert updated_cat.description == "Updated solar energy scope"


@pytest.mark.django_db
class TestInvoiceTemplateBuilder:
    def test_apply_staffing_preset(self, setup_data):
        client = setup_data['client']
        template = InvoicingService.invoice_template_apply_preset(
            preset_code="STAFFING_WORKFORCE",
            client_id=str(client.id),
            template_name="AngloGold Staffing Template",
            make_default=True,
        )

        assert template.layout_style == InvoiceLayoutStyle.DETAILED_STAFFING
        assert template.invoice_title == "TAX INVOICE - REIMBURSABLE WORKFORCE"
        assert len(template.header_custom_fields) >= 3
        assert any(f['key'] == 'po_number' for f in template.header_custom_fields)
        assert any(f['key'] == 'site_location' for f in template.header_custom_fields)

        assert len(template.line_custom_fields) >= 3
        assert any(f['key'] == 'staff_name' for f in template.line_custom_fields)
        assert any(f['key'] == 'days_worked' for f in template.line_custom_fields)

        # Test live canvas preview selector
        preview = InvoicingSelector.invoice_builder_preview_data(
            template_data={'preset_code': 'STAFFING_WORKFORCE'}
        )
        assert 'preview_invoice' in preview
        assert preview['preview_invoice']['subtotal'] > 0


@pytest.mark.django_db
class TestInvoiceCreationTaxAndGLPosting:
    def test_invoice_create_and_ghana_tax_calculation(self, setup_data):
        client = setup_data['client']
        user = setup_data['user']

        # Seed categories
        InvoicingService.invoice_category_seed_defaults()
        staffing_cat = InvoiceCategory.objects.get(code='WORKFORCE_OUTSOURCING')

        # Create staffing template
        template = InvoicingService.invoice_template_apply_preset(
            preset_code="STAFFING_WORKFORCE",
            client_id=str(client.id),
            make_default=True,
        )

        # Create catalog item
        item = InvoicingService.billable_item_create(
            code="STAFF-OPERATOR",
            name="Heavy Equipment Operator",
            category_id=str(staffing_cat.id),
            default_unit="Days",
            default_unit_price=Decimal("400.00"),
            default_tax_code="VAT_STANDARD",
        )

        # Create Invoice
        invoice = InvoicingService.invoice_create(
            client_id=str(client.id),
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + datetime.timedelta(days=30),
            category_id=str(staffing_cat.id),
            description="Outsourced Heavy Equipment Personnel - Obuasi Mine Shift Roster",
            template_id=str(template.id),
            reference_number="PO-AGL-2026-9901",
            custom_fields={
                'po_number': 'PO-AGL-2026-9901',
                'site_location': 'Obuasi Open Pit',
                'cost_center': 'Mining Ops #44',
                'contract_number': 'SBP-AGL-2025-01',
            },
            lines=[
                {
                    'item_id': str(item.id),
                    'description': 'Heavy Equipment Operator - Shift A',
                    'quantity': Decimal('25.00'),
                    'unit_price': Decimal('400.00'),
                    'tax_code': 'VAT_STANDARD',
                    'custom_fields': {
                        'staff_name': 'Kwame Mensah',
                        'employee_id': 'SBP-EMP-001',
                        'role_designation': 'Excavator Operator',
                        'days_worked': 25,
                    }
                },
                {
                    'item_id': str(item.id),
                    'description': 'Heavy Equipment Operator - Shift B',
                    'quantity': Decimal('20.00'),
                    'unit_price': Decimal('400.00'),
                    'tax_code': 'VAT_STANDARD',
                    'custom_fields': {
                        'staff_name': 'Kofi Boateng',
                        'employee_id': 'SBP-EMP-002',
                        'role_designation': 'Dump Truck Operator',
                        'days_worked': 20,
                    }
                }
            ],
            user=user,
        )

        # Base Subtotal = (25*400) + (20*400) = 10,000 + 8,000 = 18,000 GHS
        expected_subtotal = Decimal('18000.0000')
        assert invoice.subtotal == expected_subtotal
        assert invoice.status == InvoiceStatus.DRAFT
        assert invoice.category == staffing_cat
        assert invoice.description == "Outsourced Heavy Equipment Personnel - Obuasi Mine Shift Roster"
        assert invoice.custom_fields['site_location'] == 'Obuasi Open Pit'

        # Ghana GRA Cascading Tax verification:
        # NHIL: 2.5% of 18,000 = 450.00
        # GETFund: 2.5% of 18,000 = 450.00
        # COVID-19: 1.0% of 18,000 = 180.00
        # VAT Base = 18,000 + 450 + 450 + 180 = 19,080.00
        # VAT: 15% of 19,080.00 = 2,862.00
        # Total Tax = 450 + 450 + 180 + 2,862 = 3,942.00
        # Grand Total = 18,000 + 3,942 = 21,942.00
        expected_tax = Decimal('3942.0000')
        expected_total = Decimal('21942.0000')

        assert invoice.tax_amount == expected_tax
        assert invoice.total_amount == expected_total

        # Check tax lines breakdown records
        assert invoice.tax_lines.count() == 4
        nhil_line = invoice.tax_lines.get(tax_type__startswith='NHIL')
        assert nhil_line.tax_amount == Decimal('450.0000')
        vat_line = invoice.tax_lines.get(tax_type__startswith='VAT')
        assert vat_line.tax_amount == Decimal('2862.0000')

        # ---------------------------------------------------------------------
        # APPROVE INVOICE & GENERAL LEDGER POSTING
        # ---------------------------------------------------------------------
        approved_invoice = InvoicingService.invoice_approve(invoice_id=str(invoice.id), user=user)
        assert approved_invoice.status == InvoiceStatus.ISSUED
        assert approved_invoice.journal_entry is not None

        je = approved_invoice.journal_entry
        assert je.lines.count() >= 3

        # Debit AR = 21,942.00
        ar_line = je.lines.get(account__code='1100-AR-GH')
        assert ar_line.debit == Decimal('21942.0000')
        assert ar_line.credit == Decimal('0.0000')

        # Credit Revenue = 18,000.00
        rev_line = je.lines.get(account__code='4010-REVENUE-GH')
        assert rev_line.credit == Decimal('18000.0000')

        # Credit Tax Payable = 3,942.00
        tax_line = je.lines.get(account__code='2020-TAX-PAYABLE-GH')
        assert tax_line.credit == Decimal('3942.0000')

        # ---------------------------------------------------------------------
        # RENDER PAYLOAD VERIFICATION
        # ---------------------------------------------------------------------
        render_data = InvoicingSelector.invoice_render_data(invoice_id=str(invoice.id))
        assert render_data['invoice_number'] == invoice.invoice_number
        assert render_data['total_amount'] == 21942.00
        assert len(render_data['lines']) == 2
        assert render_data['lines'][0]['custom_fields']['staff_name'] == 'Kwame Mensah'
        assert len(render_data['tax_lines']) == 4
        assert render_data['banking']['bank_name'] is not None

    def test_invoice_credit_note_issuance(self, setup_data):
        client = setup_data['client']
        user = setup_data['user']

        invoice = InvoicingService.invoice_create(
            client_id=str(client.id),
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + datetime.timedelta(days=15),
            lines=[
                {
                    'description': 'Consulting Retainer',
                    'quantity': Decimal('1.00'),
                    'unit_price': Decimal('5000.00'),
                    'tax_code': 'EXEMPT',
                }
            ],
            auto_calculate_tax=False,
            user=user,
        )
        InvoicingService.invoice_approve(invoice_id=str(invoice.id), user=user)

        # Issue Credit Note for GHS 2,000.00 adjustment
        cn = InvoicingService.invoice_issue_credit_note(
            invoice_id=str(invoice.id),
            reason="Rate discount adjustment agreed by director",
            credit_amount=Decimal('2000.00'),
            user=user
        )

        assert cn.invoice_type == InvoiceType.CREDIT_NOTE
        assert cn.parent_invoice == invoice
        assert cn.total_amount == Decimal('2000.0000')
        assert cn.journal_entry is not None

        # Re-fetch invoice and verify amount_paid is updated
        invoice.refresh_from_db()
        assert invoice.amount_paid == Decimal('2000.0000')
        assert invoice.balance_due == Decimal('3000.0000')

    def test_invoice_void_reverses_gl(self, setup_data):
        client = setup_data['client']
        user = setup_data['user']

        invoice = InvoicingService.invoice_create(
            client_id=str(client.id),
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + datetime.timedelta(days=15),
            lines=[
                {
                    'description': 'Temporary Logistics Service',
                    'quantity': Decimal('1.00'),
                    'unit_price': Decimal('3000.00'),
                    'tax_code': 'EXEMPT',
                }
            ],
            auto_calculate_tax=False,
            user=user,
        )
        invoice = InvoicingService.invoice_approve(invoice_id=str(invoice.id), user=user)
        assert invoice.journal_entry is not None
        orig_je_id = invoice.journal_entry.id

        # Void invoice
        voided_inv = InvoicingService.invoice_void(
            invoice_id=str(invoice.id),
            reason="Duplicate billing entry",
            user=user
        )
        assert voided_inv.status == InvoiceStatus.VOIDED
        assert voided_inv.journal_entry is None


@pytest.mark.django_db
class TestCachingAndInvalidation:
    def test_caching_and_invalidation_lifecycle(self, setup_data):
        client = setup_data['client']
        user = setup_data['user']

        # 1. Initially invoice list is empty or returns list
        invoices_initial = InvoicingSelector.invoice_list(client_id=str(client.id))
        count_initial = len(invoices_initial)

        # 2. Create invoice -> verifies cache invalidation
        inv = InvoicingService.invoice_create(
            client_id=str(client.id),
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + datetime.timedelta(days=30),
            lines=[
                {
                    'description': 'Cache Testing Line Item',
                    'quantity': Decimal('1.00'),
                    'unit_price': Decimal('1200.00'),
                    'tax_code': 'EXEMPT',
                }
            ],
            auto_calculate_tax=False,
            user=user,
        )

        invoices_after = InvoicingSelector.invoice_list(client_id=str(client.id))
        assert len(invoices_after) == count_initial + 1

        # 3. Cache detail selector
        inv_detail_1 = InvoicingSelector.invoice_detail(invoice_id=str(inv.id))
        assert inv_detail_1.id == inv.id

        # 4. Invalidate on update
        InvoicingService.invoice_update(invoice_id=str(inv.id), description="Updated description for cache check")
        inv_detail_2 = InvoicingSelector.invoice_detail(invoice_id=str(inv.id))
        assert inv_detail_2.description == "Updated description for cache check"


@pytest.mark.django_db
class TestRecurringBillingSchedule:
    def test_recurring_schedule_execution(self, setup_data):
        client = setup_data['client']
        user = setup_data['user']

        schedule = InvoicingService.recurring_schedule_create(
            schedule_name="Monthly Workforce Retainer - Site A",
            client_id=str(client.id),
            frequency=RecurringFrequency.MONTHLY,
            start_date=timezone.now().date(),
            auto_issue=True,
            invoice_payload={
                'description': 'Monthly outsourced personnel retainer',
                'lines': [
                    {
                        'description': 'Retainer fee',
                        'quantity': 1,
                        'unit_price': 15000.0,
                        'tax_code': 'EXEMPT',
                    }
                ]
            }
        )

        assert schedule.status == RecurringScheduleStatus.ACTIVE
        assert schedule.next_run_date == timezone.now().date()

        # Execute due schedules
        generated = InvoicingService.recurring_schedule_execute_due(as_of_date=timezone.now().date(), user=user)
        assert len(generated) >= 1

        gen_inv = generated[0]
        assert gen_inv.client == client
        assert gen_inv.status == InvoiceStatus.ISSUED
        assert gen_inv.journal_entry is not None

        # Verify next_run_date was advanced
        schedule.refresh_from_db()
        assert schedule.next_run_date > timezone.now().date()


from rest_framework.test import APIClient


@pytest.mark.django_db
class TestInvoicingAPIEndpoints:
    def test_api_category_and_invoice_endpoints(self, setup_data):
        client_model = setup_data['client']
        user = setup_data['user']

        api_client = APIClient()
        api_client.force_authenticate(user=user)

        # 1. Seed Categories API
        res_seed = api_client.post('/api/v1/invoicing/categories/seed-defaults/')
        assert res_seed.status_code == 200
        assert res_seed.data['success'] is True

        # 2. Create custom category API
        res_cat_create = api_client.post('/api/v1/invoicing/categories/', {
            'name': 'Expatriate Relocation Services',
            'code': 'EXPAT_RELOCATION',
            'description': 'Work permits, residency visas, and expat housing.',
        }, format='json')
        assert res_cat_create.status_code == 201
        cat_id = res_cat_create.data['data']['id']

        # 3. List presets API
        res_presets = api_client.get('/api/v1/invoicing/templates/presets/')
        assert res_presets.status_code == 200
        assert len(res_presets.data['data']) >= 3

        # 4. Apply preset API
        res_apply = api_client.post('/api/v1/invoicing/templates/apply-preset/', {
            'preset_code': 'STAFFING_WORKFORCE',
            'client_id': str(client_model.id),
            'template_name': 'Custom Workforce Template',
            'make_default': True,
        }, format='json')
        assert res_apply.status_code == 201
        template_id = res_apply.data['data']['id']

        # 5. Create invoice via API
        res_inv_create = api_client.post('/api/v1/invoicing/invoices/', {
            'client_id': str(client_model.id),
            'issue_date': str(timezone.now().date()),
            'due_date': str(timezone.now().date() + datetime.timedelta(days=30)),
            'category_id': cat_id,
            'description': 'Expat visa quota processing and immigration support',
            'template_id': template_id,
            'reference_number': 'PO-EXPAT-001',
            'lines': [
                {
                    'description': 'Work Permit Class G Processing',
                    'quantity': '2.00',
                    'unit_price': '15000.00',
                    'tax_code': 'VAT_STANDARD',
                    'custom_fields': {'staff_name': 'John Doe'},
                }
            ],
            'custom_fields': {'po_number': 'PO-EXPAT-001'},
            'auto_calculate_tax': True,
        }, format='json')
        assert res_inv_create.status_code == 201
        invoice_id = res_inv_create.data['data']['id']
        assert res_inv_create.data['data']['subtotal'] == '30000.0000'
        # Total with Ghana tax = 30,000 + (2.5%*30000 + 2.5%*30000 + 1%*30000) + 15%*(30000+1800) = 30,000 + 1,800 + 4,770 = 36,570.00
        assert Decimal(res_inv_create.data['data']['total_amount']) == Decimal('36570.0000')

        # 6. Approve invoice API
        res_approve = api_client.post(f'/api/v1/invoicing/invoices/{invoice_id}/approve/')
        assert res_approve.status_code == 200
        assert res_approve.data['data']['status'] == InvoiceStatus.ISSUED

        # 7. Render invoice API
        res_render = api_client.get(f'/api/v1/invoicing/invoices/{invoice_id}/render/')
        assert res_render.status_code == 200
        assert res_render.data['data']['total_amount'] == 36570.00
        assert len(res_render.data['data']['tax_lines']) == 4
        assert res_render.data['data']['banking'] is not None
