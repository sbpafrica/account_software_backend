import os
import django
from decimal import Decimal
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.users.models import User, Role, Permission, UserRole, DEFAULT_ROLE_PERMISSIONS
from apps.ledger.models import Account, AccountType
from apps.ledger.services import LedgerService
from apps.taxation.models import TaxRule, TaxType

print("1. Seeding Enterprise Permissions & Roles...")

# Collect all unique permission codes
all_perm_codes = set()
for perms in DEFAULT_ROLE_PERMISSIONS.values():
    all_perm_codes.update(perms)

# Seed granular permissions
created_perms = {}
for code in sorted(all_perm_codes):
    module = code.split(':')[0] if ':' in code else 'global'
    name = f"{code.replace(':', ' ').title()} Permission" if code != '*' else 'Superuser All Access'
    perm, _ = Permission.objects.get_or_create(
        code=code,
        defaults={'name': name, 'module': module, 'description': f'Access code for {code}'}
    )
    created_perms[code] = perm

# Seed roles and attach permissions
created_roles = {}
for role_name, perm_list in DEFAULT_ROLE_PERMISSIONS.items():
    role, _ = Role.objects.get_or_create(
        name=role_name,
        defaults={'description': f'System Role: {role_name}', 'is_system_role': True}
    )
    role_perms = [created_perms[code] for code in perm_list if code in created_perms]
    role.permissions.set(role_perms)
    created_roles[role_name] = role
    print(f"  Initialized role: {role_name} with {len(role_perms)} permissions.")

print("2. Seeding Enterprise Staff Accounts...")
users_seed = [
    ('ceo@sbp-africa.com', 'Kwame', 'Mensah', UserRole.SUPER_ADMIN, None, True),
    ('finance.mgr@sbp-africa.com', 'Abena', 'Osei', UserRole.FINANCE_MANAGER, None, False),
    ('chief.acct@sbp-africa.com', 'Kofi', 'Antwi', UserRole.CHIEF_ACCOUNTANT, None, False),
    ('auditor@sbp-africa.com', 'Esi', 'Appiah', UserRole.INTERNAL_AUDITOR, None, False),
    ('gh.acct@sbp-africa.com', 'Yaw', 'Boateng', UserRole.COUNTRY_ACCOUNTANT, 'GH', False),
    ('payroll@sbp-africa.com', 'Akua', 'Danso', UserRole.PAYROLL_ACCOUNTANT, None, False),
    ('treasury@sbp-africa.com', 'Kojo', 'Sarpong', UserRole.TREASURY_OFFICER, None, False),
]

for email, fn, ln, role_name, country, is_super in users_seed:
    user = User.objects.filter(email=email).first()
    if not user:
        role_obj = created_roles.get(role_name)
        if is_super:
            u = User.objects.create_superuser(
                email=email,
                password='Password123!',
                first_name=fn,
                last_name=ln,
                role=role_obj,
                assigned_country=country
            )
        else:
            u = User.objects.create_user(
                email=email,
                password='Password123!',
                first_name=fn,
                last_name=ln,
                role=role_obj,
                assigned_country=country
            )
        print(f"Created user: {u.email} ({role_name}) - Superuser: {u.is_superuser}")

super_admin = User.objects.get(email='ceo@sbp-africa.com')

print("3. Seeding Chart of Accounts...")
accounts_data = [
    ('1010-FNB-PAYROLL-GH', 'FNB Ghana Payroll Clearing Account', AccountType.ASSET),
    ('1020-FNB-OPEX-GH', 'FNB Ghana Operating Cash Account', AccountType.ASSET),
    ('1100-AR-GH', 'Accounts Receivable (Clients)', AccountType.ASSET),
    ('2010-AP-GH', 'Accounts Payable (Suppliers)', AccountType.LIABILITY),
    ('2020-TAX-PAYABLE-GH', 'Statutory Tax Payable (GRA/SSNIT)', AccountType.LIABILITY),
    ('2100-ESCROW-GH', 'Client Payroll Escrow Liability', AccountType.LIABILITY),
    ('4010-EOR-FEES-GH', 'EOR & HR Management Fee Revenue', AccountType.REVENUE),
    ('5010-DIRECT-WORKFORCE-GH', 'Direct Workforce Delivery Expense', AccountType.DIRECT_COST),
    ('6010-OFFICE-RENT-GH', 'Head Office Rent Expense', AccountType.OPEX),
]

created_accounts = {}
for code, name, acct_type in accounts_data:
    acct, _ = Account.objects.get_or_create(
        code=code,
        defaults={'name': name, 'account_type': acct_type, 'currency': 'GHS', 'country_code': 'GH'}
    )
    created_accounts[code] = acct

print("4. Posting Initial Capital Journal Entry...")
if not created_accounts['1020-FNB-OPEX-GH'].journal_lines.exists():
    LedgerService.post_journal_entry(
        entry_number="JE-2026-INIT-001",
        posting_date=date(2026, 1, 1),
        description="Initial Seed Operating Capital",
        source_module="MANUAL",
        source_ref="INIT_CAPITAL",
        user=super_admin,
        lines_data=[
            {'account': created_accounts['1020-FNB-OPEX-GH'], 'debit': Decimal('2500000.00'), 'credit': Decimal('0')},
            {'account': created_accounts['2100-ESCROW-GH'], 'debit': Decimal('0'), 'credit': Decimal('2500000.00')},
        ]
    )

print("5. Seeding Tax Rules for Ghana...")
TaxRule.objects.get_or_create(
    country_code='GH',
    tax_type=TaxType.WHT,
    defaults={'rate': Decimal('0.0750'), 'effective_from': date(2026, 1, 1)}
)

print("Seed Data with Users, Roles & Ledger Initialized Successfully!")
