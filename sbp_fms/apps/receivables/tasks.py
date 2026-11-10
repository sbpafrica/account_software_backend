import logging
from celery import shared_task
from django.utils import timezone
from apps.common.tasks import send_email_task
from .models import ClientInvoice, ClientInvoiceStatus, PaymentReceipt

logger = logging.getLogger(__name__)


@shared_task
def send_invoice_email_task(invoice_id: str, recipient_email: str = None) -> bool:
    """
    [ASYNC CELERY TASK]:
    Sends client invoice notification with itemized breakdown and payment instructions.
    """
    try:
        invoice = ClientInvoice.objects.select_related('client').prefetch_related('lines').get(id=invoice_id)
    except ClientInvoice.DoesNotExist:
        logger.error(f"ClientInvoice {invoice_id} not found.")
        return False

    client = invoice.client
    recipient = recipient_email or client.email
    if not recipient:
        logger.warning(f"No recipient email found for ClientInvoice {invoice.invoice_number}")
        return False

    currency = getattr(client, 'currency', 'GHS')
    subject = f"Invoice {invoice.invoice_number} from SBP-FMS - {currency} {invoice.total_amount:,.2f}"
    
    lines_summary = "\n".join([
        f"- {line.description}: {line.quantity} x {line.unit_price:,.2f} = {line.total_amount:,.2f}"
        for line in invoice.lines.all()
    ])

    message = (
        f"Dear {client.name},\n\n"
        f"Please find below your invoice details:\n\n"
        f"Invoice Number: {invoice.invoice_number}\n"
        f"Issue Date: {invoice.issue_date}\n"
        f"Due Date: {invoice.due_date}\n"
        f"Currency: {currency}\n\n"
        f"Items:\n{lines_summary}\n\n"
        f"Subtotal: {invoice.subtotal:,.2f}\n"
        f"Tax Amount: {invoice.tax_amount:,.2f}\n"
        f"Total Amount Due: {invoice.total_amount:,.2f} {currency}\n\n"
        f"Payment Terms: {client.payment_terms_days} days.\n\n"
        f"Thank you for your business.\n\n"
        f"Best regards,\n"
        f"Accounts Receivable Team"
    )

    send_email_task.delay(
        subject=subject,
        recipient_list=[recipient],
        message=message
    )
    return True


@shared_task
def send_payment_receipt_email_task(receipt_id: str, recipient_email: str = None) -> bool:
    """
    [ASYNC CELERY TASK]:
    Dispatches formal payment receipt notification confirming settlement of receivable balances.
    """
    try:
        receipt = PaymentReceipt.objects.select_related('client').get(id=receipt_id)
    except PaymentReceipt.DoesNotExist:
        logger.error(f"PaymentReceipt {receipt_id} not found.")
        return False

    client = receipt.client
    recipient = recipient_email or client.email
    if not recipient:
        return False

    currency = getattr(receipt.bank_account, 'currency', 'GHS') if hasattr(receipt, 'bank_account') and receipt.bank_account else 'GHS'
    amount_str = f"{receipt.amount_received:,.2f}"
    subject = f"Payment Receipt {receipt.receipt_number} - {currency} {amount_str}"
    message = (
        f"Dear {client.name},\n\n"
        f"We have received and recorded your payment of {currency} {amount_str}.\n\n"
        f"Receipt Number: {receipt.receipt_number}\n"
        f"Payment Date: {receipt.receipt_date}\n"
        f"Payment Method: {receipt.payment_method}\n"
        f"Reference: {receipt.reference_number or 'N/A'}\n\n"
        f"Thank you for your prompt payment.\n\n"
        f"Best regards,\n"
        f"Treasury & Accounts Receivable"
    )

    send_email_task.delay(
        subject=subject,
        recipient_list=[recipient],
        message=message
    )
    return True


@shared_task
def check_overdue_invoices_and_send_reminders_task() -> dict:
    """
    [PERIODIC CELERY TASK]:
    Daily scheduled sweep:
    1. Identifies unpaid client invoices past their due dates.
    2. Updates their status to OVERDUE.
    3. Dispatches automated friendly payment reminder emails.
    """
    today = timezone.now().date()
    overdue_qs = ClientInvoice.objects.filter(
        status__in=[ClientInvoiceStatus.ISSUED, ClientInvoiceStatus.PARTIALLY_PAID],
        due_date__lt=today
    ).select_related('client')

    updated_count = 0
    reminded_count = 0

    for invoice in overdue_qs:
        # Update status to OVERDUE
        invoice.status = ClientInvoiceStatus.OVERDUE
        invoice.save(update_fields=['status', 'updated_at'])
        updated_count += 1

        client = invoice.client
        if client.email:
            currency = getattr(client, 'currency', 'GHS')
            subject = f"OVERDUE PAYMENT REMINDER: Invoice {invoice.invoice_number}"
            message = (
                f"Dear {client.name},\n\n"
                f"This is a courteous reminder that Invoice {invoice.invoice_number} for "
                f"{currency} {invoice.total_amount:,.2f} was due on {invoice.due_date} and is now overdue.\n\n"
                f"Outstanding Balance: {currency} {invoice.total_amount - invoice.amount_paid:,.2f}\n\n"
                f"Please arrange settlement at your earliest convenience or contact finance@sbp-africa.com "
                f"if payment has already been initiated.\n\n"
                f"Thank you,\n"
                f"Credit Control Team"
            )
            send_email_task.delay(
                subject=subject,
                recipient_list=[client.email],
                message=message
            )
            reminded_count += 1

    logger.info(f"Overdue invoice check complete: {updated_count} marked overdue, {reminded_count} reminders dispatched.")
    return {
        'marked_overdue_count': updated_count,
        'reminders_dispatched_count': reminded_count,
        'date': str(today)
    }
