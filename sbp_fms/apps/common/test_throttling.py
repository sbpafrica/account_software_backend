import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.settings import api_settings
from django.core.cache import cache
from apps.users.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestRateLimitingAndThrottling:
    """
    Test suite verifying application-layer rate limiting and throttling.
    """

    def test_auth_burst_rate_throttle_blocks_rapid_attempts(self, api_client, monkeypatch):
        """
        Verify that brute force login attempts beyond limit return HTTP 429 with uniform error envelope.
        """
        monkeypatch.setitem(api_settings.DEFAULT_THROTTLE_RATES, 'auth_burst', '3/minute')
        cache.clear()

        url = reverse('user-login')
        payload = {'email': 'victim@acme.com', 'password': 'WrongPassword123!'}

        # 1st attempt: allowed (invalid creds)
        res1 = api_client.post(url, payload, format='json')
        assert res1.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED)

        # 2nd attempt: allowed
        res2 = api_client.post(url, payload, format='json')
        assert res2.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED)

        # 3rd attempt: allowed
        res3 = api_client.post(url, payload, format='json')
        assert res3.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED)

        # 4th attempt: throttled with HTTP 429 Too Many Requests
        res4 = api_client.post(url, payload, format='json')
        assert res4.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        data = res4.json()
        assert data['success'] is False
        assert data['code'] == 'THROTTLED'
        assert 'Request was throttled' in data['message']

    def test_registration_throttle_blocks_tenant_creation_spam(self, api_client, monkeypatch):
        """
        Verify that rapid tenant creation from the same IP is throttled at HTTP 429.
        """
        monkeypatch.setitem(api_settings.DEFAULT_THROTTLE_RATES, 'registration', '2/minute')
        cache.clear()

        url = reverse('organization-register-public')

        for i in range(2):
            payload = {
                'organization_name': f'Org Rapid {i}',
                'email': f'owner{i}@rapid.com',
                'password': 'StrongPassword123!',
                'first_name': 'First',
                'last_name': 'Last',
                'country_code': 'GH',
                'base_currency': 'GHS'
            }
            res = api_client.post(url, payload, format='json')
            assert res.status_code == status.HTTP_201_CREATED

        # 3rd attempt from same IP must be throttled
        payload3 = {
            'organization_name': 'Org Rapid Spam',
            'email': 'spam@rapid.com',
            'password': 'StrongPassword123!',
            'first_name': 'Spam',
            'last_name': 'Bot',
            'country_code': 'GH',
            'base_currency': 'GHS'
        }
        res3 = api_client.post(url, payload3, format='json')
        assert res3.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert res3.json()['code'] == 'THROTTLED'

