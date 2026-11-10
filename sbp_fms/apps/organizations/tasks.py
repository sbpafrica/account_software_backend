import logging
from celery import shared_task
from django.conf import settings
from apps.common.tasks import send_email_task
from .models import Organization, OrganizationInvitation
from apps.users.models import User

logger = logging.getLogger(__name__)


@shared_task
def send_organization_invitation_email_task(invitation_id: str) -> bool:
    """
    [ASYNC CELERY TASK]:
    Dispatches a team invitation email containing the unique acceptance token and joining link.
    """
    try:
        invitation = OrganizationInvitation.objects.select_related('organization', 'invited_by').get(id=invitation_id)
    except OrganizationInvitation.DoesNotExist:
        logger.error(f"OrganizationInvitation {invitation_id} not found.")
        return False

    org = invitation.organization
    inviter = invitation.invited_by
    subject = f"You have been invited to join {org.name} on SBP-FMS"
    
    frontend_base_url = getattr(settings, 'FRONTEND_URL', 'https://app.sbpfms.com')
    invite_url = f"{frontend_base_url}/accept-invite?token={invitation.token}"

    message = (
        f"Hello,\n\n"
        f"{inviter.first_name} {inviter.last_name} ({inviter.email}) has invited you to join "
        f"'{org.name}' as a {invitation.role} on SBP-FMS Financial Management System.\n\n"
        f"To accept this invitation and activate your account, please click the link below:\n"
        f"{invite_url}\n\n"
        f"This invitation token will expire on {invitation.expires_at.strftime('%Y-%m-%d %H:%M UTC')}.\n\n"
        f"Best regards,\n"
        f"The SBP-FMS Platform Team"
    )

    send_email_task.delay(
        subject=subject,
        recipient_list=[invitation.email],
        message=message
    )
    return True


@shared_task
def send_welcome_onboarding_email_task(organization_id: str, user_id: str) -> bool:
    """
    [ASYNC CELERY TASK]:
    Sends onboarding and setup guidance to the new organization owner.
    """
    try:
        org = Organization.objects.get(id=organization_id)
        user = User.objects.get(id=user_id)
    except (Organization.DoesNotExist, User.DoesNotExist):
        return False

    subject = f"Welcome to SBP-FMS - {org.name} is ready!"
    message = (
        f"Dear {user.first_name},\n\n"
        f"Congratulations on registering '{org.name}' on SBP-FMS!\n\n"
        f"Your organization workspace has been provisioned with the {org.plan} tier.\n"
        f"Primary Currency: {org.base_currency}\n\n"
        f"Next Steps to get started:\n"
        f"1. Configure your Chart of Accounts or use the default regional templates.\n"
        f"2. Add your bank accounts and configure direct feed integrations.\n"
        f"3. Invite your accounting team and auditors via the Team Management console.\n\n"
        f"If you require assistance, our support team is available at support@sbp-africa.com.\n\n"
        f"Best regards,\n"
        f"SBP-FMS Enterprise Accounting Team"
    )

    send_email_task.delay(
        subject=subject,
        recipient_list=[user.email],
        message=message
    )
    return True
