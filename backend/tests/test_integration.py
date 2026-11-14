"""Read-only HTTP checks. Real accounts/tokens must be supplied explicitly."""
import os

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def settings():
    if os.getenv('SHIELDRAG_INTEGRATION') != '1':
        pytest.skip('Set SHIELDRAG_INTEGRATION=1 for live Supabase checks')
    return Settings()


def test_live_auth_rejects_forged_jwt(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/v1/me', headers={
            'Authorization': 'Bearer forged.jwt.signature'}).status_code == 401


def test_live_postgrest_rejects_anonymous_table_access(settings):
    with httpx.Client(trust_env=False, timeout=15) as client:
        response = client.get(settings.supabase_url + '/rest/v1/documents',
                              params={'select': 'id', 'limit': '1'}, headers={
                                  'apikey': settings.supabase_publishable_key.get_secret_value()})
        assert response.status_code == 401
        assert response.json()['code'] == '42501'


def test_live_auth_health(settings):
    with httpx.Client(trust_env=False, timeout=15) as client:
        response = client.get(settings.supabase_url + '/auth/v1/health', headers={
            'apikey': settings.supabase_publishable_key.get_secret_value()})
        assert response.status_code == 200


@pytest.mark.parametrize('role', ['student', 'admin'])
def test_live_authenticated_endpoints(settings, role):
    token = os.getenv(f'SHIELDRAG_{role.upper()}_TOKEN')
    if not token:
        pytest.skip(f'Provide a synthetic {role} account access token')
    with TestClient(create_app(settings)) as client:
        headers = {'Authorization': f'Bearer {token}'}
        response = client.get('/api/v1/me', headers=headers)
        assert response.status_code == 200
        assert response.json()['role'] == role
        for path in ('/api/v1/documents', '/api/v1/security/events'):
            assert client.get(path, headers=headers).status_code == 200
