from typing import Optional
from django.shortcuts import get_object_or_404
from apps.common.cache import CacheManager, make_cache_key
from apps.common.filters import apply_dict_filters, merge_filters
from .models import User, Role, Permission


def user_list(*, filters: Optional[dict] = None, role=None, country=None, is_active=None) -> list[User]:
    combined_filters = merge_filters(
        filters,
        assigned_country=country,
        is_active=is_active
    )
    if role:
        combined_filters['role__name'] = str(role).upper()

    cache_key = make_cache_key('fms:users:list', filters=combined_filters)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = User.objects.select_related('role').prefetch_related('role__permissions', 'direct_permissions').all()
    qs = apply_dict_filters(qs, combined_filters)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def user_detail(*, user_id) -> User:
    cache_key = f"fms:users:detail:{user_id}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    user = get_object_or_404(
        User.objects.select_related('role').prefetch_related('role__permissions', 'direct_permissions'),
        id=user_id
    )
    CacheManager.set(cache_key, user, timeout=1800)
    return user


def user_get_by_email(*, email: str) -> User:
    cache_key = f"fms:users:email:{email.lower().strip()}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    user = get_object_or_404(
        User.objects.select_related('role').prefetch_related('role__permissions', 'direct_permissions'),
        email=email
    )
    CacheManager.set(cache_key, user, timeout=1800)
    return user


def role_list(*, filters: Optional[dict] = None, name=None) -> list[Role]:
    combined_filters = merge_filters(filters, name=name)
    cache_key = make_cache_key('fms:roles:list', filters=combined_filters)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = Role.objects.prefetch_related('permissions').all()
    qs = apply_dict_filters(qs, combined_filters)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def role_detail(*, role_id) -> Role:
    cache_key = f"fms:roles:detail:{role_id}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    role = get_object_or_404(
        Role.objects.prefetch_related('permissions'),
        id=role_id
    )
    CacheManager.set(cache_key, role, timeout=1800)
    return role


def permission_list(*, filters: Optional[dict] = None, module=None) -> list[Permission]:
    combined_filters = merge_filters(filters, module=module)
    cache_key = make_cache_key('fms:permissions:list', filters=combined_filters)
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    qs = Permission.objects.all()
    qs = apply_dict_filters(qs, combined_filters)
    results = list(qs)
    CacheManager.set(cache_key, results, timeout=1800)
    return results


def permission_detail(*, permission_id) -> Permission:
    cache_key = f"fms:permissions:detail:{permission_id}"
    cached = CacheManager.get(cache_key)
    if cached is not None:
        return cached

    perm = get_object_or_404(Permission, id=permission_id)
    CacheManager.set(cache_key, perm, timeout=1800)
    return perm
