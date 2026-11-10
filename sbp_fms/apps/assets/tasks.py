import logging
from datetime import date
from celery import shared_task
from django.utils import timezone
from apps.assets.services import AssetsService
from apps.users.models import User

logger = logging.getLogger(__name__)


@shared_task
def run_periodic_depreciation_batch_task(period_date_str: str = None) -> dict:
    """
    [PERIODIC CELERY TASK]:
    Computes monthly straight-line / reducing-balance depreciation for all active fixed assets,
    generates the depreciation schedule lines, and posts balancing General Ledger journal entries.
    """
    if period_date_str:
        period_date = date.fromisoformat(period_date_str)
    else:
        period_date = timezone.now().date()

    # System user actor
    system_user = User.objects.filter(is_superuser=True).first()
    if not system_user:
        logger.warning("No superuser found to attribute automated depreciation run.")
        return {'status': 'skipped', 'reason': 'No system user available'}

    try:
        run = AssetsService.depreciation_run_execute(
            period_date=period_date,
            user=system_user,
            notes=f"Automated monthly depreciation batch run for {period_date.strftime('%B %Y')} via Celery."
        )
        logger.info(f"Completed depreciation run {run.run_number} for {run.total_depreciation_amount} across {run.asset_count} assets.")
        return {
            'status': 'success',
            'run_id': str(run.id),
            'run_number': run.run_number,
            'total_depreciation_amount': str(run.total_depreciation_amount),
            'asset_count': run.asset_count
        }
    except Exception as exc:
        logger.error(f"Automated depreciation run failed: {exc}")
        return {'status': 'failed', 'error': str(exc)}
