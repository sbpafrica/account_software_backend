import hmac
import hashlib
import logging
import uuid
from decimal import Decimal
import requests
from django.conf import settings
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class PaystackService:
    """
    [PAYSTACK PAYMENT GATEWAY INTEGRATION SERVICE]:
    Handles Paystack API calls for dynamic subscription plans, checkout initialization,
    transaction verification, and cryptographically secure webhook signature verification.
    """

    @classmethod
    def get_secret_key(cls) -> str:
        return getattr(settings, 'PAYSTACK_SECRET_KEY', '').strip()

    @classmethod
    def get_public_key(cls) -> str:
        return getattr(settings, 'PAYSTACK_PUBLIC_KEY', '').strip()

    @classmethod
    def get_base_url(cls) -> str:
        return getattr(settings, 'PAYSTACK_BASE_URL', 'https://api.paystack.co').rstrip('/')

    @classmethod
    def _headers(cls) -> dict:
        secret = cls.get_secret_key()
        return {
            'Authorization': f'Bearer {secret}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    @classmethod
    def create_plan(
        cls,
        *,
        name: str,
        amount: Decimal,
        interval: str,
        currency: str = 'GHS',
        description: str = ''
    ) -> dict:
        """
        Creates a subscription plan in Paystack.
        Intervals: 'monthly', 'annually', 'weekly', 'daily', etc.
        Amounts are converted to subunits (pesewas/kobo -> multiplied by 100).
        """
        # Map uppercase internal interval to Paystack format
        interval_map = {
            'MONTHLY': 'monthly',
            'ANNUALLY': 'annually',
            'WEEKLY': 'weekly',
            'DAILY': 'daily',
            'ONETIME': 'monthly',
            'FREE': 'monthly',
        }
        paystack_interval = interval_map.get(interval.upper(), interval.lower())

        # If free tier, return mock response without hitting external API
        if amount <= Decimal('0.00'):
            return {
                'plan_code': f'PLN_FREE_{uuid.uuid4().hex[:8]}',
                'name': name,
                'amount': 0,
                'interval': paystack_interval,
                'currency': currency,
            }

        url = f"{cls.get_base_url()}/plan"
        payload = {
            'name': name,
            'interval': paystack_interval,
            'amount': int(amount * 100),
            'currency': currency.upper(),
            'description': description or f"SBP-FMS Plan: {name}",
        }

        try:
            response = requests.post(url, json=payload, headers=cls._headers(), timeout=15)
            data = response.json()
            if not response.ok or not data.get('status'):
                msg = data.get('message', 'Failed to create plan on Paystack.')
                logger.error("Paystack create_plan failed: %s | Payload: %s", msg, payload)
                raise ValidationError(f"Paystack Plan Error: {msg}")
            return data.get('data', {})
        except requests.RequestException as e:
            logger.error("Paystack create_plan network error: %s", str(e))
            raise ValidationError(f"Could not connect to Paystack payment gateway: {str(e)}")

    @classmethod
    def initialize_transaction(
        cls,
        *,
        email: str,
        amount: Decimal,
        currency: str = 'GHS',
        reference: str = None,
        plan_code: str = None,
        callback_url: str = None,
        metadata: dict = None
    ) -> dict:
        """
        Initializes a checkout transaction with Paystack.
        Returns authorization_url, access_code, and reference.
        """
        if not reference:
            reference = f"fms_{uuid.uuid4().hex[:16]}"

        url = f"{cls.get_base_url()}/transaction/initialize"
        payload = {
            'email': email.strip().lower(),
            'amount': int(amount * 100),
            'currency': currency.upper(),
            'reference': reference,
        }
        if plan_code:
            payload['plan'] = plan_code
        if callback_url:
            payload['callback_url'] = callback_url
        if metadata:
            payload['metadata'] = metadata

        try:
            response = requests.post(url, json=payload, headers=cls._headers(), timeout=15)
            data = response.json()
            if not response.ok or not data.get('status'):
                msg = data.get('message', 'Failed to initialize transaction on Paystack.')
                logger.error("Paystack initialize_transaction failed: %s | Payload: %s", msg, payload)
                raise ValidationError(f"Paystack Initialize Error: {msg}")
            return data.get('data', {})
        except requests.RequestException as e:
            logger.error("Paystack initialize_transaction network error: %s", str(e))
            raise ValidationError(f"Could not connect to Paystack payment gateway: {str(e)}")

    @classmethod
    def verify_transaction(cls, *, reference: str) -> dict:
        """
        Verifies transaction status directly with Paystack via /transaction/verify/{reference}.
        """
        url = f"{cls.get_base_url()}/transaction/verify/{reference}"
        try:
            response = requests.get(url, headers=cls._headers(), timeout=15)
            data = response.json()
            if not response.ok or not data.get('status'):
                msg = data.get('message', 'Failed to verify transaction on Paystack.')
                logger.error("Paystack verify_transaction failed: %s | Ref: %s", msg, reference)
                raise ValidationError(f"Paystack Verification Error: {msg}")
            return data.get('data', {})
        except requests.RequestException as e:
            logger.error("Paystack verify_transaction network error: %s", str(e))
            raise ValidationError(f"Could not connect to Paystack payment gateway: {str(e)}")

    @classmethod
    def verify_webhook_signature(cls, payload_bytes: bytes, signature_header: str) -> bool:
        """
        Validates HMAC-SHA512 webhook signature sent by Paystack in 'X-Paystack-Signature' header.
        """
        if not signature_header:
            return False
        secret = cls.get_secret_key()
        if not secret:
            logger.warning("PAYSTACK_SECRET_KEY is empty; cannot verify webhook signature.")
            return False

        computed_signature = hmac.new(
            secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha512
        ).hexdigest()

        return hmac.compare_digest(computed_signature, signature_header)
