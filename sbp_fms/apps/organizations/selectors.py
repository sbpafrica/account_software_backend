from django.shortcuts import get_object_or_404
from apps.common.cache import CacheManager, make_cache_key
from .models import (
    Organization, OrganizationMembership, OrganizationInvitation,
    SubscriptionPlan, SubscriptionTransaction
)


def organization_detail(*, organization_id) -> Organization:
    cache_key = make_cache_key("fms:organizations:detail", identifier=organization_id)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    org = get_object_or_404(Organization, id=organization_id, is_active=True)
    CacheManager.set(cache_key, org, timeout=3600)
    return org


def user_organizations_list(*, user) -> list[OrganizationMembership]:
    cache_key = make_cache_key("fms:organizations:user_orgs", identifier=user.id)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    memberships = list(
        OrganizationMembership.objects.filter(
            user=user,
            organization__is_active=True
        ).select_related('organization').order_by('-is_default', 'organization__name')
    )
    CacheManager.set(cache_key, memberships, timeout=1800)
    return memberships


def organization_invitations_list(*, organization_id) -> list[OrganizationInvitation]:
    cache_key = make_cache_key("fms:organizations:invitations", identifier=organization_id)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    invitations = list(
        OrganizationInvitation.objects.filter(
            organization_id=organization_id,
            accepted=False
        ).order_by('-created_at')
    )
    CacheManager.set(cache_key, invitations, timeout=1800)
    return invitations


def subscription_plans_list(*, public_only: bool = True) -> list[SubscriptionPlan]:
    """
    Retrieves subscription plans. Cached for high read performance.
    """
    cache_key = make_cache_key(f"fms:organizations:plans:list:{public_only}")
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = SubscriptionPlan.objects.filter(is_active=True)
    if public_only:
        qs = qs.filter(is_public=True)
    plans = list(qs.order_by('price', 'name'))
    CacheManager.set(cache_key, plans, timeout=3600)
    return plans


def subscription_plan_detail(*, plan_id) -> SubscriptionPlan:
    """
    Retrieves a single subscription plan by ID or code.
    """
    cache_key = make_cache_key("fms:organizations:plans:detail", identifier=plan_id)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    CacheManager.set(cache_key, plan, timeout=3600)
    return plan


def subscription_transactions_list(*, organization_id) -> list[SubscriptionTransaction]:
    """
    Retrieves transaction history for an organization.
    """
    cache_key = make_cache_key("fms:organizations:transactions:list", identifier=organization_id)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    txs = list(
        SubscriptionTransaction.objects.filter(
            organization_id=organization_id
        ).select_related('plan').order_by('-created_at')
    )
    CacheManager.set(cache_key, txs, timeout=600)
    return txs

