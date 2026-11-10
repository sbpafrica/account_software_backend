import logging
from celery import shared_task
from django.utils import timezone
from .models import BankFeedConnection, BankFeedStatus
from .bank_feed import BankFeedService
from apps.users.models import User

logger = logging.getLogger(__name__)


@shared_task
def sync_active_bank_feeds_task() -> dict:
    """
    [PERIODIC CELERY TASK]:
    Synchronizes statement transactions across all active bank feed connections.
    """
    active_connections = BankFeedConnection.objects.filter(
        status=BankFeedStatus.CONNECTED
    ).select_related('bank_account')

    system_user = User.objects.filter(is_superuser=True).first()

    synced_count = 0
    failed_count = 0

    for conn in active_connections:
        try:
            BankFeedService.sync_live_feed(
                bank_account_id=str(conn.bank_account.id),
                user=system_user
            )
            synced_count += 1
        except Exception as exc:
            logger.error(f"Failed periodic sync for connection {conn.id}: {exc}")
            failed_count += 1

    logger.info(f"Bank feed sync sweep complete: {synced_count} synced, {failed_count} failed.")
    return {
        'synced_count': synced_count,
        'failed_count': failed_count,
        'timestamp': str(timezone.now())
    }
