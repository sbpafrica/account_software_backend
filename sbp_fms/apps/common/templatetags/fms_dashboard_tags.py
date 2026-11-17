import json
from django import template
from django.utils import timezone
from datetime import timedelta

register = template.Library()


@register.simple_tag
def get_fms_dashboard_metrics():
    """
    Computes real-time KPIs and chart analytics data for the Jazzmin Admin Dashboard.
    """
    metrics = {
        'total_orgs': 0,
        'active_orgs': 0,
        'inhouse_orgs': 0,
        'trial_orgs': 0,
        'paid_orgs': 0,
        'total_users': 0,
        'active_users': 0,
        'staff_users': 0,
        'stakeholder_users': 0,
        'total_plans': 0,
        'total_transactions': 0,
        'total_ledger_accounts': 0,
        'total_invoices': 0,
        'total_assets': 0,
        'total_bank_accounts': 0,
        # Chart JSON datasets
        'tier_labels_json': json.dumps(['Trial (30-Day)', 'Starter', 'Growth', 'Enterprise', 'In-House (Exempt)', 'Custom']),
        'tier_counts_json': json.dumps([0, 0, 0, 0, 0, 0]),
        'monthly_labels_json': json.dumps(['Month 1', 'Month 2', 'Month 3', 'Month 4', 'Month 5', 'Current']),
        'monthly_orgs_json': json.dumps([0, 0, 0, 0, 0, 0]),
        'monthly_users_json': json.dumps([0, 0, 0, 0, 0, 0]),
        'module_labels_json': json.dumps(['Organizations', 'Users', 'Ledger Accounts', 'Invoices', 'Fixed Assets', 'Bank Accounts']),
        'module_counts_json': json.dumps([0, 0, 0, 0, 0, 0]),
    }

    try:
        from apps.organizations.models import Organization, SubscriptionPlan, SubscriptionTransaction, SubscriptionPlanTier
        from apps.users.models import User

        total_orgs = Organization.objects.count()
        active_orgs = Organization.objects.filter(is_active=True).count()
        inhouse_orgs = Organization.objects.filter(is_inhouse=True).count()
        trial_orgs = Organization.objects.filter(plan=SubscriptionPlanTier.TRIAL).count()
        starter_orgs = Organization.objects.filter(plan=SubscriptionPlanTier.STARTER).count()
        growth_orgs = Organization.objects.filter(plan=SubscriptionPlanTier.GROWTH).count()
        enterprise_orgs = Organization.objects.filter(plan=SubscriptionPlanTier.ENTERPRISE).count()
        custom_orgs = Organization.objects.filter(plan=SubscriptionPlanTier.CUSTOM).count()
        paid_orgs = total_orgs - trial_orgs - inhouse_orgs

        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        staff_users = User.objects.filter(is_staff=True).count()
        stakeholder_users = User.objects.filter(is_stakeholder=True).count()

        total_plans = SubscriptionPlan.objects.count()
        total_tx = SubscriptionTransaction.objects.count()

        metrics.update({
            'total_orgs': total_orgs,
            'active_orgs': active_orgs,
            'inhouse_orgs': inhouse_orgs,
            'trial_orgs': trial_orgs,
            'paid_orgs': max(0, paid_orgs),
            'total_users': total_users,
            'active_users': active_users,
            'staff_users': staff_users,
            'stakeholder_users': stakeholder_users,
            'total_plans': total_plans,
            'total_transactions': total_tx,
            'tier_counts_json': json.dumps([trial_orgs, starter_orgs, growth_orgs, enterprise_orgs, inhouse_orgs, custom_orgs]),
        })
    except Exception:
        pass

    # Optional Domain Module Metrics
    try:
        from apps.ledger.models import Account
        metrics['total_ledger_accounts'] = Account.objects.count()
    except Exception:
        pass

    try:
        from apps.payables.models import SupplierInvoice
        metrics['total_invoices'] = SupplierInvoice.objects.count()
    except Exception:
        pass

    try:
        from apps.assets.models import FixedAsset
        metrics['total_assets'] = FixedAsset.objects.count()
    except Exception:
        pass

    try:
        from apps.treasury.models import BankAccount
        metrics['total_bank_accounts'] = BankAccount.objects.count()
    except Exception:
        pass

    # Module activity comparison chart
    metrics['module_counts_json'] = json.dumps([
        metrics['total_orgs'],
        metrics['total_users'],
        metrics['total_ledger_accounts'],
        metrics['total_invoices'],
        metrics['total_assets'],
        metrics['total_bank_accounts'],
    ])

    # Dynamic 6-Month Timeline
    now = timezone.now()
    month_names = []
    month_org_counts = []
    month_user_counts = []

    try:
        from apps.organizations.models import Organization
        from apps.users.models import User
        for i in range(5, -1, -1):
            target_date = now - timedelta(days=i * 30)
            month_names.append(target_date.strftime('%b %Y'))
            # Cumulative count up to target date
            month_org_counts.append(Organization.objects.filter(created_at__lte=target_date).count())
            month_user_counts.append(User.objects.filter(created_at__lte=target_date).count())
    except Exception:
        month_names = ['5 Months Ago', '4 Months Ago', '3 Months Ago', '2 Months Ago', 'Last Month', 'This Month']
        month_org_counts = [0, 0, 0, 0, 0, metrics['total_orgs']]
        month_user_counts = [0, 0, 0, 0, 0, metrics['total_users']]

    metrics['monthly_labels_json'] = json.dumps(month_names)
    metrics['monthly_orgs_json'] = json.dumps(month_org_counts)
    metrics['monthly_users_json'] = json.dumps(month_user_counts)

    return metrics
