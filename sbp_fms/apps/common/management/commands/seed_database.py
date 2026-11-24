import datetime
from decimal import Decimal
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

# Model imports
from apps.users.models import Permission, Role, User, UserRole, DEFAULT_ROLE_PERMISSIONS
from apps.organizations.models import (
    SubscriptionPlan, SubscriptionPlanTier, BillingInterval,
    Organization, OrganizationMembership, OrganizationRole
)
from apps.ledger.models import (
    CompanyProfile, Department, CostCentre, Account, AccountType,
    JournalEntry, JournalLine, JournalEntryStatus
)
from apps.treasury.models import (
    BankAccount, BankStatement, BankStatementLine, BankTransaction
)
from apps.taxation.models import TaxRule, TaxType
from apps.receivables.models import (
    Client, ClientInvoice, ClientInvoiceLine, ClientInvoiceStatus,
    PaymentReceipt, ReceiptAllocation, PaymentReceiptStatus
)
from apps.payables.models import (
    Supplier, PurchaseOrder, POLine, GoodsReceivedNote, GRNLine,
    SupplierInvoice, InvoiceLine, MatchStatus,
    PaymentVoucher, VoucherLine, PaymentVoucherStatus,
    ExpenseClaim, ExpenseClaimLine, ExpenseClaimStatus, ExpenseClaimType
)
from apps.payroll_escrow.models import PayrollBatch, PayrollBatchStatus
from apps.assets.models import (
    AssetCategory, FixedAsset, DepreciationMethod, AssetStatus,
    DepreciationRun, DepreciationRunStatus
)
from apps.consolidation.models import ExchangeRate, RateType
from apps.budgeting.models import Budget, BudgetLine, BudgetStatus
from apps.contracts.models import Contract, ContractStatus
from apps.common.models import AuditLog
from apps.organizations.context import set_current_organization, clear_current_organization

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Seeds the SBP-FMS database with comprehensive, interconnected test data for development and production testing."

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Clean up existing demo data before seeding.',
        )
        parser.add_argument(
            '--password',
            type=str,
            default='P@ssword123!',
            help='Default password for all seeded users (default: P@ssword123!).',
        )

    def handle(self, *args, **options):
        clean = options.get('clean', False)
        default_pwd = options.get('password', 'P@ssword123!')

        self.stdout.write(self.style.MIGRATE_HEADING("=================================================="))
        self.stdout.write(self.style.MIGRATE_HEADING("   SBP-FMS Enterprise Database Seeder"))
        self.stdout.write(self.style.MIGRATE_HEADING("=================================================="))

        with transaction.atomic():
            if clean:
                self.stdout.write(self.style.WARNING("==> Cleaning previous demo data..."))
                self._clean_database()

            self.stdout.write("==> [1/14] Seeding RBAC Permissions & System Roles...")
            roles_map = self._seed_permissions_and_roles()

            self.stdout.write("==> [2/14] Seeding System & Tenant Users...")
            users_map = self._seed_users(roles_map, default_pwd)

            self.stdout.write("==> [3/14] Seeding SaaS Subscription Plans...")
            plans_map = self._seed_subscription_plans(users_map['superadmin'])

            self.stdout.write("==> [4/14] Seeding Organizations & Memberships...")
            orgs_map = self._seed_organizations(plans_map, users_map)

            # Bind multi-tenant context to primary organization during demo data seeding
            set_current_organization(orgs_map['primary'])
            try:
                self.stdout.write("==> [5/14] Seeding Chart of Accounts, Departments & Cost Centres...")
                ledger_data = self._seed_ledger(orgs_map['primary'], users_map)

                self.stdout.write("==> [6/14] Seeding Multi-Country Statutory Tax Rules...")
                self._seed_taxation()

                self.stdout.write("==> [7/14] Seeding Treasury Bank Accounts & Bank Statements...")
                treasury_data = self._seed_treasury(ledger_data, users_map)

                self.stdout.write("==> [8/14] Seeding Foreign Exchange Rates & Multi-Currency...")
                self._seed_exchange_rates()

                self.stdout.write("==> [9/14] Seeding Fixed Assets & Depreciation...")
                self._seed_assets(ledger_data, users_map)

                self.stdout.write("==> [10/14] Seeding Receivables (Clients, Invoices & Receipts)...")
                self._seed_receivables(treasury_data, ledger_data, users_map)

                self.stdout.write("==> [11/14] Seeding Payables (Suppliers, 3-Way Match, Vouchers & Expenses)...")
                self._seed_payables(treasury_data, ledger_data, users_map)

                self.stdout.write("==> [12/14] Seeding Payroll Escrow Batches...")
                self._seed_payroll_escrow(users_map)

                self.stdout.write("==> [13/14] Seeding Annual Operating Budgets...")
                self._seed_budgeting(ledger_data, users_map)

                self.stdout.write("==> [14/14] Seeding Client Service Contracts...")
                self._seed_contracts()

                # Adopt any unassigned / orphaned legacy demo records into primary corporate organization
                primary_org = orgs_map['primary']
                FixedAsset.all_objects.filter(organization__isnull=True).update(organization=primary_org)
                DepreciationRun.all_objects.filter(organization__isnull=True).update(organization=primary_org)
                BankAccount.all_objects.filter(organization__isnull=True).update(organization=primary_org)
                Client.all_objects.filter(organization__isnull=True).update(organization=primary_org)
                Supplier.all_objects.filter(organization__isnull=True).update(organization=primary_org)
                PayrollBatch.all_objects.filter(organization__isnull=True).update(organization=primary_org)
                Budget.all_objects.filter(organization__isnull=True).update(organization=primary_org)
                Contract.all_objects.filter(organization__isnull=True).update(organization=primary_org)
            finally:
                clear_current_organization()

        self.stdout.write(self.style.SUCCESS("\n[+] Database seeding completed successfully!"))
        self.stdout.write(self.style.SUCCESS("--------------------------------------------------"))
        self.stdout.write(self.style.SUCCESS("Test User Logins (Password: " + default_pwd + "):"))
        self.stdout.write(self.style.SUCCESS("  - Super Admin:     admin@sbpafrica.group"))
        self.stdout.write(self.style.SUCCESS("  - Finance Manager: finance@sbpafrica.group"))
        self.stdout.write(self.style.SUCCESS("  - Accountant:      accountant@sbpafrica.group"))
        self.stdout.write(self.style.SUCCESS("  - Auditor:         auditor@sbpafrica.group"))
        self.stdout.write(self.style.SUCCESS("  - Client Owner:    owner@horizonlogistics.com"))
        self.stdout.write(self.style.SUCCESS("--------------------------------------------------"))

    def _clean_database(self):
        """Cleans demo entities while preserving essential migration state."""
        Contract.objects.filter(contract_number__startswith='CTR-').delete()
        BudgetLine.objects.all().delete()
        Budget.objects.all().delete()
        FixedAsset.objects.filter(asset_tag__startswith='AST-').delete()
        AssetCategory.objects.all().delete()
        ReceiptAllocation.objects.all().delete()
        PaymentReceipt.objects.filter(receipt_number__startswith='REC-').delete()
        ClientInvoiceLine.objects.all().delete()
        ClientInvoice.objects.filter(invoice_number__startswith='INV-').delete()
        Client.objects.filter(code__startswith='CL-').delete()
        VoucherLine.objects.all().delete()
        PaymentVoucher.objects.filter(voucher_number__startswith='PV-').delete()
        ExpenseClaimLine.objects.all().delete()
        ExpenseClaim.objects.filter(claim_number__startswith='EXP-').delete()
        InvoiceLine.objects.all().delete()
        SupplierInvoice.objects.all().delete()
        GRNLine.objects.all().delete()
        GoodsReceivedNote.objects.all().delete()
        POLine.objects.all().delete()
        PurchaseOrder.objects.all().delete()
        Supplier.objects.filter(name__in=['Dell Technologies Africa', 'TotalEnergies Ghana', 'PwC Ghana Advisory']).delete()
        PayrollBatch.objects.filter(batch_code__startswith='PAY-').delete()
        BankStatementLine.objects.all().delete()
        BankStatement.objects.all().delete()
        BankTransaction.objects.all().delete()
        BankAccount.objects.all().delete()
        TaxRule.objects.all().delete()
        ExchangeRate.objects.all().delete()
        JournalLine.objects.all().delete()
        JournalEntry.objects.filter(entry_number__startswith='JV-').delete()
        Account.objects.all().delete()
        CostCentre.objects.all().delete()
        Department.objects.all().delete()
        CompanyProfile.objects.all().delete()
        OrganizationMembership.objects.all().delete()
        Organization.objects.filter(slug__in=['sbp-africa-group', 'horizon-logistics']).delete()
        SubscriptionPlan.objects.all().delete()
        User.objects.filter(email__in=[
            'admin@sbpafrica.group',
            'finance@sbpafrica.group',
            'accountant@sbpafrica.group',
            'auditor@sbpafrica.group',
            'owner@horizonlogistics.com'
        ]).delete()

    def _seed_permissions_and_roles(self):
        """Provisions all standard granular RBAC permissions and system roles."""
        all_perm_codes = set()
        for role_name, perms in DEFAULT_ROLE_PERMISSIONS.items():
            for p in perms:
                if p != '*':
                    all_perm_codes.add(p)

        # Standard permission catalog
        created_perms = {}
        for code in sorted(all_perm_codes):
            parts = code.split(':')
            module = parts[0]
            action = parts[1] if len(parts) > 1 else 'access'
            name = f"{action.capitalize()} {module.capitalize()}"
            perm, _ = Permission.objects.get_or_create(
                code=code,
                defaults={'name': name, 'module': module, 'description': f"Permission to {action} {module}"}
            )
            created_perms[code] = perm

        roles_map = {}
        for role_name, perms in DEFAULT_ROLE_PERMISSIONS.items():
            role, _ = Role.objects.get_or_create(
                name=role_name,
                defaults={
                    'description': f"Standard {role_name.replace('_', ' ').title()} system role",
                    'is_system_role': True
                }
            )
            if '*' in perms:
                role.permissions.set(Permission.objects.all())
            else:
                role_perms = [created_perms[p] for p in perms if p in created_perms]
                role.permissions.set(role_perms)
            roles_map[role_name] = role

        return roles_map

    def _seed_users(self, roles_map, default_pwd):
        """Creates standard administrative and operational test users."""
        users_map = {}

        # 1. Platform Super Admin
        admin, _ = User.objects.get_or_create(
            email='admin@sbpafrica.group',
            defaults={
                'first_name': 'Khelly',
                'last_name': 'SuperAdmin',
                'assigned_country': 'GH',
                'is_staff': True,
                'is_superuser': True,
                'is_stakeholder': True,
                'is_active': True,
                'role': roles_map[UserRole.SUPER_ADMIN]
            }
        )
        admin.is_stakeholder = True
        admin.set_password(default_pwd)
        admin.save()
        users_map['superadmin'] = admin

        # 2. Finance Manager (Stakeholder)
        finance_mgr, _ = User.objects.get_or_create(
            email='finance@sbpafrica.group',
            defaults={
                'first_name': 'Kwame',
                'last_name': 'Mensah',
                'assigned_country': 'GH',
                'is_stakeholder': True,
                'is_active': True,
                'role': roles_map[UserRole.FINANCE_MANAGER]
            }
        )
        finance_mgr.is_stakeholder = True
        finance_mgr.set_password(default_pwd)
        finance_mgr.save()
        users_map['finance_mgr'] = finance_mgr

        # 3. Chief Accountant
        accountant, _ = User.objects.get_or_create(
            email='accountant@sbpafrica.group',
            defaults={
                'first_name': 'Abena',
                'last_name': 'Osei',
                'assigned_country': 'GH',
                'is_active': True,
                'role': roles_map[UserRole.CHIEF_ACCOUNTANT]
            }
        )
        accountant.set_password(default_pwd)
        accountant.save()
        users_map['accountant'] = accountant

        # 4. Internal Auditor (Stakeholder)
        auditor, _ = User.objects.get_or_create(
            email='auditor@sbpafrica.group',
            defaults={
                'first_name': 'David',
                'last_name': 'Otieno',
                'assigned_country': 'KE',
                'is_stakeholder': True,
                'is_active': True,
                'role': roles_map[UserRole.INTERNAL_AUDITOR]
            }
        )
        auditor.is_stakeholder = True
        auditor.set_password(default_pwd)
        auditor.save()
        users_map['auditor'] = auditor

        # 5. External SaaS Tenant Owner
        client_owner, _ = User.objects.get_or_create(
            email='owner@horizonlogistics.com',
            defaults={
                'first_name': 'Hellen',
                'last_name': 'Wanjiru',
                'assigned_country': 'KE',
                'is_active': True,
                'role': roles_map[UserRole.SUPER_ADMIN]
            }
        )
        client_owner.set_password(default_pwd)
        client_owner.save()
        users_map['client_owner'] = client_owner

        return users_map

    def _seed_subscription_plans(self, superadmin):
        """Creates standard SaaS pricing tier plans."""
        plans_data = [
            {
                'name': 'Starter Tier (Single Entity)',
                'code': 'starter-monthly',
                'description': 'Ideal for single-country small businesses & consulting practices.',
                'price': Decimal('49.00'),
                'currency': 'USD',
                'interval': BillingInterval.MONTHLY,
                'trial_period_days': 30,
                'max_users': 5,
                'max_subsidiaries': 1,
                'features': ['ledger', 'receivables', 'payables', 'standard_reports'],
                'is_active': True,
                'is_public': True
            },
            {
                'name': 'Growth Tier (Multi-Entity / Multi-Currency)',
                'code': 'growth-monthly',
                'description': 'Best for expanding Pan-African companies with cross-border trade.',
                'price': Decimal('149.00'),
                'currency': 'USD',
                'interval': BillingInterval.MONTHLY,
                'trial_period_days': 30,
                'max_users': 20,
                'max_subsidiaries': 5,
                'features': ['ledger', 'receivables', 'payables', 'treasury', 'fx_revaluation', 'payroll_escrow'],
                'is_active': True,
                'is_public': True
            },
            {
                'name': 'Enterprise Tier (Unlimited Pan-African)',
                'code': 'enterprise-annual',
                'description': 'Unlimited entities, statutory multi-country engines & dedicated support.',
                'price': Decimal('1490.00'),
                'currency': 'USD',
                'interval': BillingInterval.ANNUALLY,
                'trial_period_days': 30,
                'max_users': None,
                'max_subsidiaries': 25,
                'features': ['all_features', 'custom_statutory_rules', 'open_banking', 'audit_vault'],
                'is_active': True,
                'is_public': True
            }
        ]

        plans_map = {}
        for pdata in plans_data:
            plan, _ = SubscriptionPlan.objects.get_or_create(
                code=pdata['code'],
                defaults={**pdata, 'created_by': superadmin}
            )
            plans_map[pdata['code']] = plan

        return plans_map

    def _seed_organizations(self, plans_map, users_map):
        """Provisions primary holding organization and demo tenant."""
        now = timezone.now()
        trial_expiry = now + datetime.timedelta(days=30)
        orgs_map = {}

        # 1. SBP Africa Group (Primary Corporate Tenant - In-House Exempt)
        sbp_org, _ = Organization.objects.get_or_create(
            slug='sbp-africa-group',
            defaults={
                'name': 'SBP Africa Group Ltd',
                'subdomain': 'sbp-africa',
                'plan': SubscriptionPlanTier.INHOUSE,
                'subscription_plan': plans_map['enterprise-annual'],
                'plan_expires_at': None,  # In-House never expires
                'is_inhouse': True,       # Completely exempt from all billing & subscription gating
                'base_currency': 'GHS',
                'billing_email': 'billing@sbpafrica.group',
                'is_active': True,
                'settings': {'timezone': 'UTC', 'fiscal_year_start': '01-01'}
            }
        )
        sbp_org.is_inhouse = True
        sbp_org.plan = SubscriptionPlanTier.INHOUSE
        sbp_org.plan_expires_at = None
        sbp_org.save()
        orgs_map['primary'] = sbp_org

        # Assign memberships
        OrganizationMembership.objects.get_or_create(
            organization=sbp_org, user=users_map['superadmin'],
            defaults={'role': OrganizationRole.OWNER, 'is_default': True}
        )
        OrganizationMembership.objects.get_or_create(
            organization=sbp_org, user=users_map['finance_mgr'],
            defaults={'role': OrganizationRole.ADMIN, 'is_default': True}
        )
        OrganizationMembership.objects.get_or_create(
            organization=sbp_org, user=users_map['accountant'],
            defaults={'role': OrganizationRole.ACCOUNTANT, 'is_default': True}
        )
        OrganizationMembership.objects.get_or_create(
            organization=sbp_org, user=users_map['auditor'],
            defaults={'role': OrganizationRole.AUDITOR, 'is_default': True}
        )

        # 2. Horizon Logistics (Demo Customer Onboarding with 30-Day Free Trial)
        horizon_org, _ = Organization.objects.get_or_create(
            slug='horizon-logistics',
            defaults={
                'name': 'Horizon Logistics Ltd',
                'subdomain': 'horizon',
                'plan': SubscriptionPlanTier.TRIAL,
                'subscription_plan': plans_map['growth-monthly'],
                'plan_expires_at': trial_expiry,
                'base_currency': 'KES',
                'billing_email': 'owner@horizonlogistics.com',
                'is_active': True,
                'settings': {'timezone': 'Africa/Nairobi'}
            }
        )
        orgs_map['tenant_trial'] = horizon_org

        OrganizationMembership.objects.get_or_create(
            organization=horizon_org, user=users_map['client_owner'],
            defaults={'role': OrganizationRole.OWNER, 'is_default': True}
        )

        return orgs_map

    def _seed_ledger(self, organization, users_map):
        """Creates CompanyProfile, Departments, Cost Centres, Chart of Accounts, and opening Journal Entries."""
        # 1. Company Profile
        profile, _ = CompanyProfile.objects.get_or_create(
            organization=organization,
            defaults={
                'company_name': 'SBP Africa Group Ltd',
                'registration_number': 'CS123456789',
                'tax_identification_number': 'C0012345678',
                'business_address': 'Heritage Towers, 6th Floor, Ridge West, Accra, Ghana',
                'telephone': '+233 30 212 3456',
                'email': 'finance@sbpafrica.group',
                'base_currency': 'GHS',
                'country_code': 'GH'
            }
        )

        # 2. Departments
        depts_data = [
            ('EXEC', 'Executive Office'),
            ('FIN', 'Finance & Accounting'),
            ('OPS', 'Operations & Logistics'),
            ('TECH', 'Technology & Systems'),
            ('HR', 'Human Resources & Talent')
        ]
        created_depts = {}
        for code, name in depts_data:
            dept, _ = Department.objects.get_or_create(code=code, defaults={'name': name, 'is_active': True})
            created_depts[code] = dept

        # 3. Cost Centres
        cc_data = [
            ('CC-HQ', 'Corporate Headquarters', created_depts['EXEC']),
            ('CC-ACCRA', 'Accra Operations Hub', created_depts['OPS']),
            ('CC-KUMASI', 'Kumasi Distribution Centre', created_depts['OPS']),
            ('CC-SHARED', 'Central Shared Services', created_depts['FIN'])
        ]
        created_ccs = {}
        for code, name, dept in cc_data:
            cc, _ = CostCentre.objects.get_or_create(code=code, defaults={'name': name, 'department': dept, 'is_active': True})
            created_ccs[code] = cc

        # 4. Standard IFRS/GAAP Chart of Accounts
        coa_data = [
            # ASSETS (1000 - 1999)
            ('1010', 'Cash on Hand (Petty Cash)', AccountType.ASSET, 'Current Asset', Decimal('15000.0000')),
            ('1020', 'Ecobank Operating Account (GHS)', AccountType.ASSET, 'Bank', Decimal('450000.0000')),
            ('1030', 'Stanbic Escrow Account (GHS)', AccountType.ASSET, 'Bank', Decimal('250000.0000')),
            ('1100', 'Accounts Receivable (Trade Debtors)', AccountType.ASSET, 'Current Asset', Decimal('85000.0000')),
            ('1200', 'Prepaid Expenses & Insurance', AccountType.ASSET, 'Current Asset', Decimal('12000.0000')),
            ('1500', 'Computer & IT Hardware Equipment', AccountType.ASSET, 'Fixed Asset', Decimal('120000.0000')),
            ('1510', 'Motor Vehicles & Fleet', AccountType.ASSET, 'Fixed Asset', Decimal('350000.0000')),
            ('1590', 'Accumulated Depreciation - Fixed Assets', AccountType.ASSET, 'Contra Asset', Decimal('-45000.0000')),

            # LIABILITIES (2000 - 2999)
            ('2010', 'Accounts Payable (Trade Creditors)', AccountType.LIABILITY, 'Current Liability', Decimal('65000.0000')),
            ('2020', 'Accrued Payroll & Net Salaries Payable', AccountType.LIABILITY, 'Current Liability', Decimal('48000.0000')),
            ('2030', 'GRA PAYE Tax Payable', AccountType.LIABILITY, 'Statutory Liability', Decimal('18500.0000')),
            ('2031', 'SSNIT Tier 1 & 2 Contributions Payable', AccountType.LIABILITY, 'Statutory Liability', Decimal('12400.0000')),
            ('2040', 'Withholding Tax (WHT) Payable', AccountType.LIABILITY, 'Statutory Liability', Decimal('8900.0000')),
            ('2050', 'GRA VAT / NHIL / GETFund Payable', AccountType.LIABILITY, 'Statutory Liability', Decimal('24200.0000')),

            # EQUITY (3000 - 3999)
            ('3010', 'Stated Share Capital', AccountType.EQUITY, 'Equity', Decimal('600000.0000')),
            ('3020', 'Retained Earnings', AccountType.EQUITY, 'Equity', Decimal('470000.0000')),

            # REVENUE (4000 - 4999)
            ('4010', 'Accounting & Management Advisory Revenue', AccountType.REVENUE, 'Operating Revenue', Decimal('0.0000')),
            ('4020', 'Payroll Escrow Administration Fees', AccountType.REVENUE, 'Operating Revenue', Decimal('0.0000')),
            ('4030', 'Software SaaS Subscription Income', AccountType.REVENUE, 'Operating Revenue', Decimal('0.0000')),

            # DIRECT COSTS (5000 - 5999)
            ('5010', 'Direct Project Contractor Costs', AccountType.DIRECT_COST, 'Direct Cost', Decimal('0.0000')),
            ('5020', 'Direct Client Reimbursable Disbursements', AccountType.DIRECT_COST, 'Direct Cost', Decimal('0.0000')),

            # OPEX (6000 - 6999)
            ('6010', 'Staff Salaries, Wages & Allowances', AccountType.OPEX, 'Operating Expense', Decimal('0.0000')),
            ('6020', 'Office Rent, Rates & Utilities', AccountType.OPEX, 'Operating Expense', Decimal('0.0000')),
            ('6030', 'Cloud Infrastructure & Software Subscriptions', AccountType.OPEX, 'Operating Expense', Decimal('0.0000')),
            ('6040', 'Depreciation Expense', AccountType.OPEX, 'Operating Expense', Decimal('0.0000')),
            ('6050', 'Bank Service & Transaction Charges', AccountType.OPEX, 'Operating Expense', Decimal('0.0000')),
            ('6060', 'Realized & Unrealized FX Loss / Gain', AccountType.OPEX, 'Financial Expense', Decimal('0.0000')),
        ]

        accounts_map = {}
        for code, name, acct_type, subtype, op_bal in coa_data:
            acct, _ = Account.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'account_type': acct_type,
                    'subtype': subtype,
                    'currency': 'GHS',
                    'country_code': 'GH',
                    'opening_balance': op_bal,
                    'opening_balance_date': datetime.date(2026, 1, 1),
                    'is_active': True,
                    'allow_direct_posting': True
                }
            )
            accounts_map[code] = acct

        # 5. Seed Balanced Opening Journal Entry
        today = timezone.now().date()
        entry, _ = JournalEntry.objects.get_or_create(
            entry_number='JV-2026-0001',
            defaults={
                'posting_date': today - datetime.timedelta(days=15),
                'status': JournalEntryStatus.POSTED,
                'description': 'Opening General Ledger Balances for FY2026',
                'source_module': 'LEDGER_INITIAL',
                'source_reference_id': 'INITIAL_FY2026',
                'created_by': users_map['superadmin'],
                'approved_by': users_map['finance_mgr']
            }
        )

        if not entry.lines.exists():
            # Balanced opening lines: Total Debits = Total Credits = 1,237,000.00 GHS
            lines = [
                # Debits (Assets)
                JournalLine(entry=entry, account=accounts_map['1020'], debit=Decimal('450000.0000'), credit=Decimal('0.0000'), cost_centre='CC-HQ'),
                JournalLine(entry=entry, account=accounts_map['1030'], debit=Decimal('250000.0000'), credit=Decimal('0.0000'), cost_centre='CC-HQ'),
                JournalLine(entry=entry, account=accounts_map['1100'], debit=Decimal('85000.0000'), credit=Decimal('0.0000'), cost_centre='CC-ACCRA'),
                JournalLine(entry=entry, account=accounts_map['1500'], debit=Decimal('120000.0000'), credit=Decimal('0.0000'), cost_centre='CC-HQ'),
                JournalLine(entry=entry, account=accounts_map['1510'], debit=Decimal('332000.0000'), credit=Decimal('0.0000'), cost_centre='CC-ACCRA'),

                # Credits (Liabilities & Equity)
                JournalLine(entry=entry, account=accounts_map['2010'], debit=Decimal('0.0000'), credit=Decimal('65000.0000'), cost_centre='CC-HQ'),
                JournalLine(entry=entry, account=accounts_map['2020'], debit=Decimal('0.0000'), credit=Decimal('48000.0000'), cost_centre='CC-HQ'),
                JournalLine(entry=entry, account=accounts_map['2030'], debit=Decimal('0.0000'), credit=Decimal('18500.0000'), cost_centre='CC-HQ'),
                JournalLine(entry=entry, account=accounts_map['2031'], debit=Decimal('0.0000'), credit=Decimal('12400.0000'), cost_centre='CC-HQ'),
                JournalLine(entry=entry, account=accounts_map['2040'], debit=Decimal('0.0000'), credit=Decimal('8900.0000'), cost_centre='CC-HQ'),
                JournalLine(entry=entry, account=accounts_map['2050'], debit=Decimal('0.0000'), credit=Decimal('14200.0000'), cost_centre='CC-HQ'),
                JournalLine(entry=entry, account=accounts_map['3010'], debit=Decimal('0.0000'), credit=Decimal('600000.0000'), cost_centre='CC-HQ'),
                JournalLine(entry=entry, account=accounts_map['3020'], debit=Decimal('0.0000'), credit=Decimal('470000.0000'), cost_centre='CC-HQ'),
            ]
            JournalLine.objects.bulk_create(lines)

        return {
            'profile': profile,
            'departments': created_depts,
            'cost_centres': created_ccs,
            'accounts': accounts_map,
            'initial_entry': entry
        }

    def _seed_taxation(self):
        """Seeds statutory progressive tax brackets & rates for Ghana and Kenya."""
        today = datetime.date(2026, 1, 1)

        tax_rules = [
            # Ghana (GH) GRA PAYE Progressive Brackets (Graduated Schedule)
            ('GH', TaxType.PAYE, Decimal('0.0000'), Decimal('588.0000'), Decimal('0.0000')),
            ('GH', TaxType.PAYE, Decimal('588.0000'), Decimal('668.0000'), Decimal('0.0500')),
            ('GH', TaxType.PAYE, Decimal('668.0000'), Decimal('768.0000'), Decimal('0.1000')),
            ('GH', TaxType.PAYE, Decimal('768.0000'), Decimal('3668.0000'), Decimal('0.1750')),
            ('GH', TaxType.PAYE, Decimal('3668.0000'), Decimal('19668.0000'), Decimal('0.2500')),
            ('GH', TaxType.PAYE, Decimal('19668.0000'), Decimal('50000.0000'), Decimal('0.3000')),
            ('GH', TaxType.PAYE, Decimal('50000.0000'), None, Decimal('0.3500')),

            # Ghana SSNIT Tier 1
            ('GH', TaxType.SSNIT, Decimal('0.0000'), None, Decimal('0.1350')),

            # Ghana Standard Withholding Tax
            ('GH', TaxType.WHT, Decimal('0.0000'), None, Decimal('0.0750')),

            # Ghana Standard VAT
            ('GH', TaxType.VAT, Decimal('0.0000'), None, Decimal('0.1500')),

            # Kenya (KE) KRA Standard WHT & VAT
            ('KE', TaxType.WHT, Decimal('0.0000'), None, Decimal('0.0500')),
            ('KE', TaxType.VAT, Decimal('0.0000'), None, Decimal('0.1600')),
        ]

        for cc, ttype, bmin, bmax, rate in tax_rules:
            TaxRule.objects.get_or_create(
                country_code=cc,
                tax_type=ttype,
                bracket_min=bmin,
                bracket_max=bmax,
                defaults={'rate': rate, 'effective_from': today}
            )

    def _seed_treasury(self, ledger_data, users_map):
        """Creates institutional bank accounts, statement imports, and statement lines."""
        accounts_map = ledger_data['accounts']
        today = timezone.now().date()

        # 1. Ecobank Operating Account
        eco_bank, _ = BankAccount.objects.get_or_create(
            account_number='0123456789012',
            defaults={
                'bank_name': 'Ecobank Ghana PLC',
                'branch_name': 'Ridge Main Branch, Accra',
                'swift_code': 'ECOCGHAC',
                'currency': 'GHS',
                'country_code': 'GH',
                'gl_account': accounts_map['1020'],
                'is_active': True
            }
        )

        # 2. Stanbic Escrow Account
        stanbic_bank, _ = BankAccount.objects.get_or_create(
            account_number='9040001234567',
            defaults={
                'bank_name': 'Stanbic Bank Ghana',
                'branch_name': 'Airport City Branch, Accra',
                'swift_code': 'SBICGHAC',
                'currency': 'GHS',
                'country_code': 'GH',
                'gl_account': accounts_map['1030'],
                'is_active': True
            }
        )

        # 3. Monthly Bank Statement for Ecobank
        stmt, _ = BankStatement.objects.get_or_create(
            bank_account=eco_bank,
            statement_date=today - datetime.timedelta(days=1),
            defaults={
                'start_date': today - datetime.timedelta(days=30),
                'end_date': today - datetime.timedelta(days=1),
                'opening_balance': Decimal('400000.0000'),
                'closing_balance': Decimal('450000.0000'),
                'file_name': 'Ecobank_Statement_Nov2026.csv',
                'total_lines': 3,
                'imported_by': users_map['accountant']
            }
        )

        # Statement lines
        stmt_lines = [
            (
                today - datetime.timedelta(days=10),
                'ECO-DEP-001',
                'Customer Wire: Ashanti Mining Invoice Settlement',
                Decimal('75000.0000'),
                Decimal('0.0000'),
                Decimal('75000.0000'),
                'hash_ecobank_001'
            ),
            (
                today - datetime.timedelta(days=5),
                'ECO-WDR-002',
                'Vendor Settlement: Dell Technologies Africa PO-001',
                Decimal('0.0000'),
                Decimal('22000.0000'),
                Decimal('-22000.0000'),
                'hash_ecobank_002'
            ),
            (
                today - datetime.timedelta(days=2),
                'ECO-CHG-003',
                'Monthly Bank Account Maintenance & Commission',
                Decimal('0.0000'),
                Decimal('3000.0000'),
                Decimal('-3000.0000'),
                'hash_ecobank_003'
            )
        ]

        for dt, ref, desc, deb, cred, net, tx_hash in stmt_lines:
            BankStatementLine.objects.get_or_create(
                transaction_hash=tx_hash,
                defaults={
                    'statement': stmt,
                    'bank_account': eco_bank,
                    'transaction_date': dt,
                    'reference': ref,
                    'description': desc,
                    'debit': deb,
                    'credit': cred,
                    'amount': net,
                    'is_reconciled': False
                }
            )

        return {
            'ecobank': eco_bank,
            'stanbic': stanbic_bank,
            'statement': stmt
        }

    def _seed_exchange_rates(self):
        """Seeds daily and month-end closing foreign exchange rates."""
        today = timezone.now().date()
        rates = [
            ('USD', 'GHS', today, Decimal('15.850000'), RateType.CLOSING),
            ('EUR', 'GHS', today, Decimal('17.200000'), RateType.CLOSING),
            ('GBP', 'GHS', today, Decimal('20.450000'), RateType.CLOSING),
            ('KES', 'GHS', today, Decimal('0.122000'), RateType.CLOSING),
            ('USD', 'KES', today, Decimal('129.500000'), RateType.CLOSING),
        ]

        for fc, tc, dt, rate, rtype in rates:
            ExchangeRate.objects.get_or_create(
                from_currency=fc,
                to_currency=tc,
                rate_date=dt,
                rate_type=rtype,
                defaults={'rate': rate}
            )

    def _seed_assets(self, ledger_data, users_map):
        """Creates fixed asset categories, assets, and depreciation schedules."""
        accounts = ledger_data['accounts']
        today = timezone.now().date()

        # 1. Asset Categories
        cat_it, _ = AssetCategory.objects.get_or_create(
            code='CAT-IT',
            defaults={
                'name': 'Computer & IT Hardware Equipment',
                'default_useful_life_years': 3,
                'default_depreciation_method': DepreciationMethod.STRAIGHT_LINE,
                'asset_gl_account': accounts['1500'],
                'accumulated_depr_gl_account': accounts['1590'],
                'depr_expense_gl_account': accounts['6040'],
                'country_code': 'GH'
            }
        )

        cat_veh, _ = AssetCategory.objects.get_or_create(
            code='CAT-VEH',
            defaults={
                'name': 'Commercial Fleet & Motor Vehicles',
                'default_useful_life_years': 5,
                'default_depreciation_method': DepreciationMethod.STRAIGHT_LINE,
                'asset_gl_account': accounts['1510'],
                'accumulated_depr_gl_account': accounts['1590'],
                'depr_expense_gl_account': accounts['6040'],
                'country_code': 'GH'
            }
        )

        # 2. Fixed Assets
        FixedAsset.objects.get_or_create(
            asset_tag='AST-IT-001',
            defaults={
                'name': 'MacBook Pro M3 Workstations (Batch of 5)',
                'description': 'Laptops for Software & Accounting Engineers',
                'category': cat_it,
                'purchase_date': today - datetime.timedelta(days=180),
                'purchase_cost': Decimal('75000.0000'),
                'salvage_value': Decimal('5000.0000'),
                'useful_life_years': 3,
                'depreciation_method': DepreciationMethod.STRAIGHT_LINE,
                'accumulated_depreciation': Decimal('11666.6667'),
                'net_book_value': Decimal('63333.3333'),
                'status': AssetStatus.ACTIVE,
                'department': 'Technology',
                'cost_centre': 'CC-HQ',
                'location': 'Ridge HQ, Accra',
                'country_code': 'GH'
            }
        )

        FixedAsset.objects.get_or_create(
            asset_tag='AST-VEH-001',
            defaults={
                'name': 'Toyota Hilux 4x4 Double Cabin (Fleet #1)',
                'description': 'Field Operations & Client Site Audits Vehicle',
                'category': cat_veh,
                'purchase_date': today - datetime.timedelta(days=365),
                'purchase_cost': Decimal('280000.0000'),
                'salvage_value': Decimal('40000.0000'),
                'useful_life_years': 5,
                'depreciation_method': DepreciationMethod.STRAIGHT_LINE,
                'accumulated_depreciation': Decimal('48000.0000'),
                'net_book_value': Decimal('232000.0000'),
                'status': AssetStatus.ACTIVE,
                'department': 'Operations',
                'cost_centre': 'CC-ACCRA',
                'location': 'Accra Hub',
                'country_code': 'GH'
            }
        )

        # 3. Monthly Depreciation Run
        DepreciationRun.objects.get_or_create(
            run_number='DEP-2026-10',
            defaults={
                'period_end_date': today - datetime.timedelta(days=15),
                'total_depreciation': Decimal('5944.4444'),
                'total_assets_processed': 2,
                'status': DepreciationRunStatus.POSTED,
                'run_by': users_map['accountant']
            }
        )

    def _seed_receivables(self, treasury_data, ledger_data, users_map):
        """Creates B2B corporate clients, client invoices, invoice lines, and payment receipts."""
        today = timezone.now().date()

        # 1. Clients
        client_ashanti, _ = Client.objects.get_or_create(
            code='CL-001',
            defaults={
                'name': 'Ashanti Gold Mining Consortium',
                'country_code': 'GH',
                'category': 'MINING_CORPORATE',
                'tax_id': 'C0098765432',
                'contact_person': 'Kwabena Darko',
                'telephone': '+233 24 111 2233',
                'email': 'accounts@ashantimining.com',
                'billing_address': 'Obuasi Mining District, Ashanti Region, Ghana',
                'credit_limit': Decimal('500000.0000'),
                'payment_terms_days': 30,
                'is_active': True
            }
        )

        client_volta, _ = Client.objects.get_or_create(
            code='CL-002',
            defaults={
                'name': 'Volta Energy Solutions Ltd',
                'country_code': 'GH',
                'category': 'ENERGY_UTILITY',
                'tax_id': 'C0055443322',
                'contact_person': 'Ama Serwaa',
                'telephone': '+233 20 444 5566',
                'email': 'finance@voltaenergy.gh',
                'billing_address': 'Tema Heavy Industrial Area, Greater Accra',
                'credit_limit': Decimal('250000.0000'),
                'payment_terms_days': 30,
                'is_active': True
            }
        )

        # 2. Client Invoice 1: Partially Paid
        inv1, _ = ClientInvoice.objects.get_or_create(
            invoice_number='INV-2026-0001',
            defaults={
                'client': client_ashanti,
                'issue_date': today - datetime.timedelta(days=20),
                'due_date': today + datetime.timedelta(days=10),
                'subtotal': Decimal('100000.0000'),
                'tax_amount': Decimal('15000.0000'),
                'total_amount': Decimal('115000.0000'),
                'amount_paid': Decimal('75000.0000'),
                'status': ClientInvoiceStatus.PARTIALLY_PAID,
                'created_by': users_map['accountant'],
                'approved_by': users_map['finance_mgr']
            }
        )
        if not inv1.lines.exists():
            ClientInvoiceLine.objects.create(
                invoice=inv1,
                description='Enterprise Accounting Systems Implementation & Advisory',
                quantity=Decimal('1.00'),
                unit_price=Decimal('100000.0000'),
                tax_code='VAT-15',
                tax_rate=Decimal('0.1500'),
                tax_amount=Decimal('15000.0000'),
                line_total=Decimal('115000.0000')
            )

        # 3. Client Invoice 2: Issued (Awaiting Payment)
        inv2, _ = ClientInvoice.objects.get_or_create(
            invoice_number='INV-2026-0002',
            defaults={
                'client': client_volta,
                'issue_date': today - datetime.timedelta(days=5),
                'due_date': today + datetime.timedelta(days=25),
                'subtotal': Decimal('45000.0000'),
                'tax_amount': Decimal('6750.0000'),
                'total_amount': Decimal('51750.0000'),
                'amount_paid': Decimal('0.0000'),
                'status': ClientInvoiceStatus.ISSUED,
                'created_by': users_map['accountant'],
                'approved_by': users_map['finance_mgr']
            }
        )
        if not inv2.lines.exists():
            ClientInvoiceLine.objects.create(
                invoice=inv2,
                description='Monthly Financial Management Retainer & Escrow Oversight',
                quantity=Decimal('1.00'),
                unit_price=Decimal('45000.0000'),
                tax_code='VAT-15',
                tax_rate=Decimal('0.1500'),
                tax_amount=Decimal('6750.0000'),
                line_total=Decimal('51750.0000')
            )

        # 4. Payment Receipt & Allocation for Invoice 1
        receipt, _ = PaymentReceipt.objects.get_or_create(
            receipt_number='REC-2026-0001',
            defaults={
                'receipt_date': today - datetime.timedelta(days=10),
                'client': client_ashanti,
                'amount_received': Decimal('75000.0000'),
                'payment_method': 'BANK_TRANSFER',
                'bank_account': treasury_data['ecobank'],
                'reference_number': 'ECO-DEP-001',
                'description': 'Part-payment for INV-2026-0001 via Ecobank Wire',
                'status': PaymentReceiptStatus.CONFIRMED,
                'created_by': users_map['accountant']
            }
        )
        ReceiptAllocation.objects.get_or_create(
            receipt=receipt,
            invoice=inv1,
            defaults={'amount_allocated': Decimal('75000.0000')}
        )

    def _seed_payables(self, treasury_data, ledger_data, users_map):
        """Creates suppliers, POs, GRNs, 3-way matched vendor bills, and payment vouchers."""
        accounts = ledger_data['accounts']
        today = timezone.now().date()

        # 1. Suppliers
        sup_dell, _ = Supplier.objects.get_or_create(
            name='Dell Technologies Africa',
            tax_id='V0012398745',
            defaults={
                'country_code': 'GH',
                'category': 'IT_EQUIPMENT',
                'contact_person': 'Samuel Boadu',
                'telephone': '+233 30 777 8899',
                'email': 'orders@dell-africa.com',
                'address': 'Airport Residential Area, Accra',
                'withholding_tax_rate': Decimal('0.0750'),
                'payment_terms_days': 30,
                'bank_account_number': '110022334455',
                'bank_name': 'Standard Chartered Bank',
                'is_active': True
            }
        )

        sup_pwc, _ = Supplier.objects.get_or_create(
            name='PwC Ghana Advisory',
            tax_id='V0099887766',
            defaults={
                'country_code': 'GH',
                'category': 'PROFESSIONAL_SERVICES',
                'contact_person': 'Eileen Koomson',
                'telephone': '+233 30 270 1200',
                'email': 'gh_billing@pwc.com',
                'address': 'PwC Tower, A&C Square, East Legon, Accra',
                'withholding_tax_rate': Decimal('0.0750'),
                'payment_terms_days': 30,
                'bank_account_number': '220033445566',
                'bank_name': 'Absa Bank Ghana',
                'is_active': True
            }
        )

        # 2. Purchase Order
        po, _ = PurchaseOrder.objects.get_or_create(
            po_number='PO-2026-0001',
            defaults={
                'supplier': sup_dell,
                'total_approved_amount': Decimal('22000.0000'),
                'is_approved': True
            }
        )
        if not po.lines.exists():
            POLine.objects.create(po=po, item_code='DELL-LAT-7440', quantity=2, approved_unit_price=Decimal('11000.0000'))

        # 3. Goods Received Note (GRN)
        grn, _ = GoodsReceivedNote.objects.get_or_create(
            grn_number='GRN-2026-0001',
            defaults={
                'po': po,
                'received_date': today - datetime.timedelta(days=12)
            }
        )
        if not grn.lines.exists():
            GRNLine.objects.create(grn=grn, item_code='DELL-LAT-7440', received_quantity=2)

        # 4. Supplier Invoice (3-Way Match Passed)
        bill, _ = SupplierInvoice.objects.get_or_create(
            supplier=sup_dell,
            invoice_number='INV-DELL-9988',
            defaults={
                'po': po,
                'grn': grn,
                'gross_amount': Decimal('22000.0000'),
                'wht_amount': Decimal('1650.0000'),
                'net_payable_amount': Decimal('20350.0000'),
                'amount_paid': Decimal('20350.0000'),
                'bill_date': today - datetime.timedelta(days=10),
                'due_date': today + datetime.timedelta(days=20),
                'match_status': MatchStatus.PAID
            }
        )
        if not bill.lines.exists():
            InvoiceLine.objects.create(invoice=bill, item_code='DELL-LAT-7440', billed_quantity=2, billed_unit_price=Decimal('11000.0000'))

        # 5. Payment Voucher for Dell Bill
        pv, _ = PaymentVoucher.objects.get_or_create(
            voucher_number='PV-2026-0001',
            defaults={
                'voucher_date': today - datetime.timedelta(days=5),
                'payment_date': today - datetime.timedelta(days=5),
                'payee_name': sup_dell.name,
                'supplier': sup_dell,
                'supplier_invoice': bill,
                'bank_account': treasury_data['ecobank'],
                'reference_number': 'ECO-WDR-002',
                'description': 'Settlement for 2x Dell Latitude 7440 Laptops per PO-001',
                'expense_account': accounts['1500'],
                'gross_amount': Decimal('22000.0000'),
                'wht_rate': Decimal('0.0750'),
                'wht_amount': Decimal('1650.0000'),
                'net_amount': Decimal('20350.0000'),
                'status': PaymentVoucherStatus.PAID,
                'prepared_by': users_map['accountant'],
                'reviewed_by': users_map['finance_mgr'],
                'approved_by': users_map['superadmin']
            }
        )
        if not pv.lines.exists():
            VoucherLine.objects.create(
                voucher=pv,
                account=accounts['1500'],
                description='Dell Hardware Laptops',
                amount=Decimal('22000.0000')
            )

        # 6. Staff Expense Claim
        claim, _ = ExpenseClaim.objects.get_or_create(
            claim_number='EXP-2026-0001',
            defaults={
                'claim_date': today - datetime.timedelta(days=3),
                'claim_type': ExpenseClaimType.REIMBURSEMENT,
                'employee': users_map['accountant'],
                'total_expenses': Decimal('1850.0000'),
                'net_payable_to_employee': Decimal('1850.0000'),
                'notes': 'Client Site Audit Visit Transportation & Fuel to Obuasi Mining Site',
                'status': ExpenseClaimStatus.APPROVED,
                'approved_by': users_map['finance_mgr'],
                'department': 'Finance',
                'cost_centre': 'CC-ACCRA',
                'country_code': 'GH'
            }
        )
        if not claim.lines.exists():
            ExpenseClaimLine.objects.create(
                claim=claim,
                expense_date=today - datetime.timedelta(days=4),
                category='Travel & Fuel',
                expense_account=accounts['6020'],
                description='Interstate Highway Fuel & Toll Receipts',
                amount=Decimal('1850.0000'),
                receipt_reference='REC-FUEL-001'
            )

    def _seed_payroll_escrow(self, users_map):
        """Creates realistic Pan-African payroll escrow batches."""
        now = timezone.now()
        cur_month = now.month
        cur_year = now.year

        PayrollBatch.objects.get_or_create(
            batch_code=f'PAY-GH-{cur_year}-{cur_month:02d}',
            defaults={
                'client_id': '11111111-2222-3333-4444-555555555555',
                'client_name': 'Ashanti Gold Mining Consortium',
                'country_code': 'GH',
                'month': cur_month,
                'year': cur_year,
                'total_net_salaries': Decimal('325000.0000'),
                'total_statutory_taxes': Decimal('85000.0000'),
                'total_management_fee': Decimal('15000.0000'),
                'status': PayrollBatchStatus.FUNDED
            }
        )

        PayrollBatch.objects.get_or_create(
            batch_code=f'PAY-KE-{cur_year}-{cur_month:02d}',
            defaults={
                'client_id': '22222222-3333-4444-5555-666666666666',
                'client_name': 'Horizon Logistics Ltd',
                'country_code': 'KE',
                'month': cur_month,
                'year': cur_year,
                'total_net_salaries': Decimal('180000.0000'),
                'total_statutory_taxes': Decimal('42000.0000'),
                'total_management_fee': Decimal('10000.0000'),
                'status': PayrollBatchStatus.DRAFT
            }
        )

    def _seed_budgeting(self, ledger_data, users_map):
        """Creates department operating budgets and budget lines."""
        accounts = ledger_data['accounts']
        cur_year = timezone.now().year

        budget, _ = Budget.objects.get_or_create(
            name=f'Corporate Operating Budget FY{cur_year}',
            financial_year=cur_year,
            defaults={
                'department': 'Operations',
                'cost_centre': 'CC-ACCRA',
                'status': BudgetStatus.APPROVED,
                'total_budget': Decimal('480000.0000'),
                'created_by': users_map['accountant'],
                'approved_by': users_map['finance_mgr'],
                'notes': f'Approved Annual Operational Budget for Ghana Facilities FY{cur_year}'
            }
        )

        if not budget.lines.exists():
            BudgetLine.objects.create(
                budget=budget,
                account=accounts['6010'],
                period_month=None,
                planned_amount=Decimal('300000.0000'),
                notes='Annual Staff Salaries'
            )
            BudgetLine.objects.create(
                budget=budget,
                account=accounts['6020'],
                period_month=None,
                planned_amount=Decimal('120000.0000'),
                notes='Annual Office Facilities & Utilities'
            )
            BudgetLine.objects.create(
                budget=budget,
                account=accounts['6030'],
                period_month=None,
                planned_amount=Decimal('60000.0000'),
                notes='Cloud Infrastructure & SaaS Tooling'
            )

    def _seed_contracts(self):
        """Creates client B2B service contracts."""
        today = timezone.now().date()
        client = Client.objects.filter(code='CL-001').first()
        if client:
            Contract.objects.get_or_create(
                contract_number='CTR-2026-001',
                defaults={
                    'client': client,
                    'title': 'Master Financial Management & Payroll Escrow Service Agreement',
                    'start_date': today - datetime.timedelta(days=90),
                    'end_date': today + datetime.timedelta(days=275),
                    'total_contract_value': Decimal('1200000.0000'),
                    'status': ContractStatus.ACTIVE,
                    'cost_centre': 'CC-ACCRA',
                    'notes': 'Multi-Year Retainer Contract for Financial Services'
                }
            )
