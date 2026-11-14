import asyncio
from uuid import UUID

import httpx
import pytest
from fastapi import Depends, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.authorization import can_retrieve_document, require_admin
from app.core.config import Settings
from app.main import create_app

USER = '11111111-1111-4111-8111-111111111111'
OTHER = '22222222-2222-4222-8222-222222222222'
STAMP = '2026-11-14T10:00:00Z'
CONFIG = {'supabase_url': 'https://example.supabase.co',
          'supabase_publishable_key': 'sb_publishable_synthetic'}
HEADERS = {'Authorization': 'Bearer synthetic-token'}


def document(number, visibility='public', status='approved'):
    return {'id': str(UUID(int=number)), 'original_name': 'synthetic.txt',
            'visibility': visibility, 'review_status': status,
            'index_status': 'not_indexed', 'created_at': STAMP}


def client_for(role='student', auth_status=200, profile=True, events=None, docs=None):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.headers['apikey'] == CONFIG['supabase_publishable_key']
        assert request.headers['authorization'].startswith('Bearer ')
        if request.url.path == '/auth/v1/user':
            return httpx.Response(auth_status, json={
                'id': USER, 'email': 'synthetic@example.invalid',
                'user_metadata': {'role': 'admin'}, 'app_metadata': {'role': 'admin'}})
        if request.url.path == '/rest/v1/profiles':
            assert request.url.params['id'] == f'eq.{USER}'
            return httpx.Response(200, json=[{'id': USER, 'role': role}] if profile else [])
        if request.url.path == '/rest/v1/documents':
            return httpx.Response(200, json=docs or [])
        if request.url.path == '/rest/v1/security_events':
            return httpx.Response(200, json=events or [])
        raise AssertionError(request.url.path)

    app = create_app(Settings(_env_file=None, **CONFIG), httpx.MockTransport(handler))

    @app.get('/test/admin')
    def admin(_=Depends(require_admin)):
        return {'ok': True}

    return TestClient(app), calls


def test_configuration():
    config = Settings(_env_file=None, **CONFIG, supabase_secret_key='synthetic-secret')
    assert 'synthetic-secret' not in repr(config)
    assert 'sb_publishable_synthetic' not in repr(config)
    for key in ('', 'sb_secret_example', 'legacy-service-jwt'):
        with pytest.raises(ValidationError):
            Settings(**{**CONFIG, 'supabase_publishable_key': key})
    for url in ('http://example.com', 'https://user:password@example.com',
                'https://example.com/path', 'https://example.com?secret=x'):
        with pytest.raises(ValidationError):
            Settings(**{**CONFIG, 'supabase_url': url})


def test_health_startup_and_openapi():
    client, calls = client_for()
    with client:
        assert client.get('/health').json() == {'status': 'ok'}
        assert client.get('/docs').status_code == 200
        paths = client.get('/openapi.json').json()['paths']
        assert '/api/v1/chat/ask' not in paths
        assert set(paths['/api/v1/documents']) == {'get', 'post'}
    assert not calls


@pytest.mark.parametrize('path', ['/api/v1/me', '/api/v1/documents', '/api/v1/security/events'])
@pytest.mark.parametrize('headers', [{}, {'Authorization': 'Basic xyz'}, {'Authorization': 'Bearer'}])
def test_missing_authentication(path, headers):
    client, calls = client_for()
    with client:
        response = client.get(path, headers=headers)
        assert response.status_code == 401
        assert response.headers['www-authenticate'] == 'Bearer'
    assert not calls


@pytest.mark.parametrize('token', ['malformed', 'expired.jwt.signature', 'forged.jwt.signature'])
def test_auth_server_rejects_invalid_jwt(token):
    client, calls = client_for(auth_status=401)
    with client:
        response = client.get('/api/v1/me', headers={'Authorization': f'Bearer {token}'})
        assert response.status_code == 401
        assert token not in response.text
    assert len(calls) == 1  # Never query profiles or documents after rejection.
    assert calls[0].headers['authorization'] == f'Bearer {token}'


@pytest.mark.parametrize('role,expected', [('student', 403), ('admin', 200)])
def test_trusted_roles_and_admin_dependency(role, expected):
    client, _ = client_for(role)
    with client:
        me = client.get('/api/v1/me?role=admin', headers={**HEADERS, 'X-Role': 'admin'})
        assert me.json()['role'] == role
        assert client.get('/test/admin', headers=HEADERS).status_code == expected


@pytest.mark.parametrize('role,profile', [('owner', True), ('student', False)])
def test_untrusted_or_missing_profile_fails_closed(role, profile):
    client, _ = client_for(role, profile=profile)
    with client:
        assert client.get('/api/v1/me', headers=HEADERS).status_code == 403


@pytest.mark.parametrize('role,count', [('student', 1), ('admin', 2)])
def test_document_filters_and_defense_in_depth(role, count):
    docs = [document(1), document(2, 'restricted'), document(3, status='pending'),
            document(4, status='rejected'), document(5, 'restricted', 'pending')]
    client, calls = client_for(role, docs=docs)
    with client:
        response = client.get('/api/v1/documents', headers=HEADERS)
        assert response.status_code == 200
        assert len(response.json()['items']) == count
    params = calls[-1].url.params
    assert params['review_status'] == 'eq.approved'
    assert (params.get('visibility') == 'eq.public') == (role == 'student')


@pytest.mark.parametrize('role', ['student', 'admin'])
@pytest.mark.parametrize('status', ['pending', 'rejected'])
def test_generation_guard(role, status):
    assert not can_retrieve_document(role, document(1, status=status))
    assert not can_retrieve_document('student', document(1, 'restricted'))


@pytest.mark.parametrize('role,count', [('student', 1), ('admin', 3)])
def test_event_ownership(role, count):
    events = [{'id': str(UUID(int=i + 1)), 'user_id': owner, 'document_id': None,
               'event_type': 'synthetic', 'decision': 'deny', 'reason': None,
               'created_at': STAMP} for i, owner in enumerate([USER, OTHER, None])]
    client, calls = client_for(role, events=events)
    with client:
        response = client.get('/api/v1/security/events', headers=HEADERS)
        assert response.status_code == 200
        assert len(response.json()['items']) == count
    assert (calls[-1].url.params.get('user_id') == f'eq.{USER}') == (role == 'student')


def test_pagination_and_future_operations():
    client, _ = client_for()
    with client:
        for query in ('limit=101', 'offset=-1', 'limit=0'):
            assert client.get('/api/v1/documents?' + query, headers=HEADERS).status_code == 422
        for path in ('/api/v1/chat/ask', '/api/v1/evaluations/run'):
            assert client.post(path, headers=HEADERS).status_code in (404, 405)


@pytest.mark.parametrize('failure', ['timeout', 'server', 'json', 'redirect'])
def test_upstream_failure_is_sanitized(failure):
    def handler(request):
        if failure == 'timeout':
            raise httpx.ConnectError('sensitive upstream details', request=request)
        if failure == 'json':
            return httpx.Response(200, text='sensitive upstream details')
        if failure == 'redirect':
            return httpx.Response(302, headers={'location': 'https://untrusted.invalid'})
        return httpx.Response(500, text='sensitive upstream details')

    with TestClient(create_app(Settings(_env_file=None, **CONFIG), httpx.MockTransport(handler))) as client:
        response = client.get('/api/v1/me', headers=HEADERS)
        assert response.status_code == 503
        assert 'sensitive' not in response.text


def test_concurrent_tokens_are_request_scoped():
    client, _ = client_for()
    with client:
        gateway = client.app.state.gateway

        async def run():
            await asyncio.gather(gateway.get('/auth/v1/user', 'first'),
                                 gateway.get('/auth/v1/user', 'second'))

        asyncio.run(run())
        assert 'authorization' not in gateway.client.headers


@pytest.mark.parametrize('path', ['/auth/v1/user', '/rest/v1/profiles', '/rest/v1/documents'])
@pytest.mark.parametrize('status,expected', [(401, 401), (403, 403), (429, 503),
                                          (500, 503), (502, 503), (302, 503)])
def test_gateway_classifies_errors_without_leaking_details(path, status, expected):
    from app.db.supabase_client import SupabaseGateway

    def handler(request):
        return httpx.Response(status, json={'message': 'sensitive database and token details'},
                              headers={'location': 'https://untrusted.invalid'})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
            gateway = SupabaseGateway(upstream, Settings(_env_file=None, **CONFIG))
            with pytest.raises(HTTPException) as error:
                await gateway.get(path, 'private-token')
            assert error.value.status_code == expected
            assert 'sensitive' not in error.value.detail
            assert 'private-token' not in error.value.detail
            assert (error.value.headers or {}).get('WWW-Authenticate') == (
                'Bearer' if expected == 401 else None)

    asyncio.run(run())


@pytest.mark.parametrize('path,payload', [('/auth/v1/user', []), ('/auth/v1/user', None),
                                        ('/rest/v1/profiles', {}), ('/rest/v1/profiles', [None])])
def test_gateway_rejects_unexpected_json_shapes(path, payload):
    from app.db.supabase_client import SupabaseGateway

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=payload))) as upstream:
            gateway = SupabaseGateway(upstream, Settings(_env_file=None, **CONFIG))
            with pytest.raises(HTTPException) as error:
                await gateway.get(path, 'private-token')
            assert error.value.status_code == 503

    asyncio.run(run())


@pytest.mark.parametrize('code,expected', [('bad_jwt', 401), ('session_expired', 401),
    ('session_not_found', 401), ('user_not_found', 401), ('user_banned', 403),
    ('insufficient_aal', 403), ('unexpected_failure', 403)])
@pytest.mark.parametrize('field', ['code', 'error_code'])
def test_auth_403_uses_documented_codes(code, expected, field):
    from app.db.supabase_client import SupabaseGateway

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: httpx.Response(403, json={field: code, 'message': 'sensitive'}))) as upstream:
            with pytest.raises(HTTPException) as error:
                await SupabaseGateway(upstream, Settings(_env_file=None, **CONFIG)).get('/auth/v1/user', 'private')
            assert error.value.status_code == expected
            assert 'sensitive' not in error.value.detail

    asyncio.run(run())
