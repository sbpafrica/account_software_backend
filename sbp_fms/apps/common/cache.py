import hashlib
import urllib.parse
from typing import Any, Callable, Optional
from django.core.cache import cache

# Standard SBP-FMS Cache Key Patterns
KEY_TRIAL_BALANCE = "fms:tb:{country}:{date}"
KEY_AGING_REPORT = "fms:aging:{country}"
KEY_CASH_FORECAST = "fms:forecast"
KEY_CLIENT_ESCROW = "fms:escrow:{client_id}:{country}"
KEY_ACCOUNTS_LIST = "fms:accounts:{country}:{is_active}"


def make_cache_key(prefix: str, identifier: Any = None, filters: Optional[dict] = None, **kwargs) -> str:
    """
    [DETERMINISTIC CACHE KEY BUILDER]:
    Constructs a deterministic cache key for selectors based on namespace, identifier,
    and normalized Python filter dictionaries / kwargs.
    """
    clean_prefix = prefix.strip(':')
    parts = [clean_prefix]

    if identifier is not None:
        parts.append(str(identifier))

    combined = {}
    if filters:
        for k, v in sorted(filters.items()):
            if v is not None and v != '':
                combined[str(k)] = str(v)
    for k, v in sorted(kwargs.items()):
        if v is not None and v != '':
            combined[str(k)] = str(v)

    if combined:
        query_str = urllib.parse.urlencode(combined)
        if len(query_str) > 40:
            digest = hashlib.md5(query_str.encode()).hexdigest()[:12]
            parts.append(digest)
        else:
            parts.append(query_str)

    return ":".join(parts)


class CacheManager:
    """
    [CACHE MANAGER]:
    Centralized caching and cache invalidation service for SBP-FMS.
    Provides deterministic key management and cross-domain cache invalidation triggers.
    """
    @staticmethod
    def get(key: str) -> Any:
        try:
            return cache.get(key)
        except Exception:
            return None

    @staticmethod
    def set(key: str, value: Any, timeout: int = 1800) -> None:
        try:
            cache.set(key, value, timeout)
        except Exception:
            pass

    @staticmethod
    def delete(key: str) -> None:
        try:
            cache.delete(key)
        except Exception:
            pass

    @staticmethod
    def delete_pattern(prefix: str) -> None:
        """
        Deletes keys matching a prefix. Compatible with both Redis and LocMemCache backends.
        """
        try:
            # 1. Native django-redis delete_pattern
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern(f"{prefix}*")
                return

            # 2. Redis client via cache.client
            client = getattr(cache, 'client', None) or getattr(cache, '_client', None)
            if client and hasattr(client, 'keys') and hasattr(client, 'delete'):
                raw_keys = client.keys(f"*{prefix}*")
                if raw_keys:
                    client.delete(*raw_keys)
                return

            # 3. LocMemCache fallback inspection
            locmem_cache = getattr(cache, '_cache', None)
            if isinstance(locmem_cache, dict):
                matched = [k for k in list(locmem_cache.keys()) if prefix in k]
                for k in matched:
                    cache.delete(k)
                return
        except Exception:
            pass

    @staticmethod
    def get_or_set(key: str, callback: Callable[[], Any], timeout: int = 1800) -> Any:
        """
        Retrieves cached value if present; otherwise executes callback, caches, and returns result.
        """
        cached = CacheManager.get(key)
        if cached is not None:
            return cached
        val = callback()
        CacheManager.set(key, val, timeout=timeout)
        return val

    # -------------------------------------------------------------------------
    # DOMAIN-SPECIFIC CACHE INVALIDATION TRIGGERS
    # -------------------------------------------------------------------------

    @staticmethod
    def invalidate_users() -> None:
        """Invalidates user accounts, roles, and granular permissions."""
        CacheManager.delete_pattern("fms:users:")
        CacheManager.delete_pattern("fms:roles:")
        CacheManager.delete_pattern("fms:permissions:")

    @staticmethod
    def invalidate_ledger(country_code: Optional[str] = None) -> None:
        """
        Invalidates trial balances, accounts lists, journal queries, and liquidity forecasts
        whenever accounts or journal entries are posted or reversed.
        """
        CacheManager.delete_pattern("fms:tb:")
        CacheManager.delete_pattern("fms:accounts:")
        CacheManager.delete_pattern("fms:journals:")
        CacheManager.delete(KEY_CASH_FORECAST)

    @staticmethod
    def invalidate_escrow(client_id: Optional[str] = None, country_code: str = 'GH') -> None:
        """
        Invalidates client escrow balances, payroll batches, and cash forecasts
        when payroll funding shifts or batches are disbursed.
        """
        if client_id:
            CacheManager.delete(KEY_CLIENT_ESCROW.format(client_id=client_id, country=country_code))
        CacheManager.delete_pattern("fms:escrow:")
        CacheManager.delete_pattern("fms:payroll:")
        CacheManager.delete(KEY_CASH_FORECAST)

    @staticmethod
    def invalidate_payroll() -> None:
        """Invalidates payroll batches and escrow cache."""
        CacheManager.delete_pattern("fms:payroll:")
        CacheManager.delete_pattern("fms:escrow:")
        CacheManager.delete(KEY_CASH_FORECAST)

    @staticmethod
    def invalidate_receivables(country_code: Optional[str] = None) -> None:
        """
        Invalidates debtor aging, client accounts, client invoices, and cash forecasts
        when client invoices are issued, matched, or paid.
        """
        CacheManager.delete_pattern("fms:clients:")
        CacheManager.delete_pattern("fms:receivables:")
        CacheManager.delete_pattern("fms:aging:")
        CacheManager.delete(KEY_CASH_FORECAST)

    @staticmethod
    def invalidate_payables() -> None:
        """
        Invalidates supplier lists, supplier invoices, and cash forecasts
        when supplier bills are entered, matched, or paid.
        """
        CacheManager.delete_pattern("fms:suppliers:")
        CacheManager.delete_pattern("fms:payables:")
        CacheManager.delete(KEY_CASH_FORECAST)

    @staticmethod
    def invalidate_treasury() -> None:
        """
        Invalidates bank accounts, bank statement transactions, and liquidity forecast.
        """
        CacheManager.delete_pattern("fms:treasury:")
        CacheManager.delete(KEY_CASH_FORECAST)

    @staticmethod
    def invalidate_taxation() -> None:
        """Invalidates statutory tax rule caches."""
        CacheManager.delete_pattern("fms:tax:")

    @staticmethod
    def invalidate_all() -> None:
        """Flushes all SBP-FMS application caches."""
        CacheManager.delete_pattern("fms:")
