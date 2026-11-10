import logging
from celery import shared_task
from apps.common.tasks import send_email_task
from .models import PaymentVoucher, PaymentVoucherStatus
from apps.users.models import User, UserRole

logger = logging.getLogger(__name__)


@shared_task
def send_payment_voucher_approval_alert_task(voucher_id: str) -> bool:
    """
    [ASYNC CELERY TASK]:
    Alerts designated Finance Managers and Chief Accountants that a payment voucher is awaiting approval.
    """
    try:
        voucher = PaymentVoucher.objects.select_related('supplier', 'prepared_by').get(id=voucher_id)
    except PaymentVoucher.DoesNotExist:
        logger.error(f"PaymentVoucher {voucher_id} not found.")
        return False

    # Find finance managers / chief accountants
    approvers = User.objects.filter(
        is_active=True,
        role__name__in=[UserRole.FINANCE_MANAGER, UserRole.CHIEF_ACCOUNTANT, UserRole.SUPER_ADMIN]
    ).exclude(id=voucher.prepared_by_id)  # Respect segregation of duties

    recipient_emails = [u.email for u in approvers if u.email]
    if not recipient_emails:
        logger.warning("No eligible approvers found for voucher notification.")
        return False

    supplier_name = voucher.supplier.name if voucher.supplier else 'Direct Expense'
    currency = getattr(voucher.bank_account, 'currency', 'GHS') if voucher.bank_account else 'GHS'
    subject = f"ACTION REQUIRED: Payment Voucher {voucher.voucher_number} awaiting approval"
    message = (
        f"Dear Finance Manager,\n\n"
        f"Payment Voucher {voucher.voucher_number} for {currency} {voucher.net_amount:,.2f} "
        f"has been submitted by {voucher.prepared_by.full_name if voucher.prepared_by else 'Finance Staff'} and is awaiting your review and authorization.\n\n"
        f"Payee: {supplier_name}\n"
        f"Voucher Date: {voucher.voucher_date}\n"
        f"Description: {voucher.description or 'N/A'}\n"
        f"Payment Mode: {voucher.payment_method}\n\n"
        f"Please log into SBP-FMS to inspect and authorize or reject this voucher.\n\n"
        f"Best regards,\n"
        f"SBP-FMS Accounts Payable Automation"
    )

    send_email_task.delay(
        subject=subject,
        recipient_list=recipient_emails,
        message=message
    )
    return True


@shared_task
def send_remittance_advice_email_task(voucher_id: str, supplier_email: str = None) -> bool:
    """
    [ASYNC CELERY TASK]:
    Sends payment remittance advice to the vendor upon voucher disbursement.
    """
    try:
        voucher = PaymentVoucher.objects.select_related('supplier').prefetch_related('lines').get(id=voucher_id)
    except PaymentVoucher.DoesNotExist:
        logger.error(f"PaymentVoucher {voucher_id} not found.")
        return False

    supplier = voucher.supplier
    recipient = supplier_email or (supplier.email if supplier else None)
    if not recipient:
        return False

    currency = getattr(voucher.bank_account, 'currency', 'GHS') if voucher.bank_account else 'GHS'
    lines_summary = "\n".join([
        f"- {line.description}: {line.amount:,.2f}"
        for line in voucher.lines.all()
    ])

    subject = f"Remittance Advice: Payment {voucher.voucher_number} - {currency} {voucher.net_amount:,.2f}"
    message = (
        f"Dear {supplier.name if supplier else 'Vendor'},\n\n"
        f"We have processed and disbursed payment according to the following remittance details:\n\n"
        f"Voucher Number: {voucher.voucher_number}\n"
        f"Disbursement Date: {voucher.voucher_date}\n"
        f"Disbursed Amount: {currency} {voucher.net_amount:,.2f}\n"
        f"Payment Method: {voucher.payment_method}\n"
        f"Bank Reference: {voucher.reference_number or 'N/A'}\n\n"
        f"Payment Allocations:\n{lines_summary}\n\n"
        f"Thank you,\n"
        f"Treasury & Accounts Payable"
    )

    send_email_task.delay(
        subject=subject,
        recipient_list=[recipient],
        message=message
    )
    return True
