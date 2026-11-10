import logging
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_task(self, subject: str, recipient_list: list[str], message: str,
                    html_message: str = None, from_email: str = None) -> bool:
    """
    [ASYNC CELERY TASK]:
    Dispatches outbound email messages asynchronously with automatic exponential retry on failure.
    """
    if isinstance(recipient_list, str):
        recipient_list = [recipient_list]

    sender = from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', 'notifications@sbp-africa.com')
    try:
        sent_count = send_mail(
            subject=subject,
            message=message,
            from_email=sender,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False
        )
        logger.info(f"Successfully sent email '{subject}' to {recipient_list}")
        return bool(sent_count)
    except Exception as exc:
        logger.error(f"Failed sending email '{subject}' to {recipient_list}: {exc}")
        raise self.retry(exc=exc)


@shared_task
def cleanup_expired_tokens_and_invitations_task() -> dict:
    """
    [PERIODIC CELERY TASK]:
    Sweeps expired organization invitation tokens and cleans up stale system records.
    """
    from apps.organizations.models import OrganizationInvitation

    now = timezone.now()
    expired_invites = OrganizationInvitation.objects.filter(
        accepted=False,
        expires_at__lt=now
    )
    count = expired_invites.count()
    expired_invites.delete()

    logger.info(f"Purged {count} expired organization invitations.")
    return {'purged_invitations_count': count, 'timestamp': str(now)}
