"""Opt-in real Auth, FastAPI, PostgREST/RLS and RPC verification."""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture(scope='module')
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


@dataclass(repr=False)
class LiveRun:
    manifest: dict = field(repr=False)
    tokens: dict = field(repr=False)
    upstream: httpx.Client = field(repr=False)
    api: TestClient = field(repr=False)

    def __repr__(self):
        return '<LiveRun credentials redacted>'

    def headers(self, role):
        return {'Authorization': f'Bearer {self.tokens[role]}'}

    def document_ids(self):
        return {d['id'] for d in self.manifest['documents']}

    def expected_documents(self, role):
        return {d['id'] for d in self.manifest['documents'] if d['review_status'] == 'approved'
                and (d['visibility'] == 'public' or role == 'admin')}


@pytest.fixture(scope='module')
def live_run(settings):
    if os.getenv('SHIELDRAG_LIVE_FIXTURES') != '1':
        pytest.skip('Set SHIELDRAG_LIVE_FIXTURES=1 after applying isolated SQL fixtures')
    path = Path(os.getenv('SHIELDRAG_FIXTURE_MANIFEST', '.integration/live/manifest.json'))
    if not path.is_file():
        pytest.fail('Full live verification requires the private fixture manifest', pytrace=False)
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if manifest.get('supabase_url') != settings.supabase_url or manifest.get('version') != 1:
        pytest.fail('Fixture project or version does not match configuration', pytrace=False)
    with httpx.Client(base_url=settings.supabase_url, timeout=15, trust_env=False,
                      headers={'apikey': settings.supabase_publishable_key.get_secret_value()}) as upstream:
        tokens = {}
        try:
            for role in ('student', 'admin'):
                account = manifest['accounts'][role]
                response = upstream.post('/auth/v1/token', params={'grant_type': 'password'},
                                         json={'email': account['email'], 'password': account['password']})
                if response.status_code != 200:
                    pytest.fail(f'Synthetic {role} password sign-in failed; check fixture setup', pytrace=False)
                tokens[role] = response.json()['access_token']
            with TestClient(create_app(settings)) as api:
                yield LiveRun(manifest, tokens, upstream, api)
        finally:
            # Revoke only these synthetic sessions; SQL cleanup is still mandatory.
            for token in tokens.values():
                response = upstream.post('/auth/v1/logout', params={'scope': 'global'},
                                         headers={'Authorization': f'Bearer {token}'})
                if response.status_code != 204:
                    pytest.fail('Synthetic session logout failed; apply cleanup.sql', pytrace=False)


@pytest.mark.parametrize('role', ['student', 'admin'])
def test_fixture_password_login_jwt_and_trusted_role(live_run, role):
    response = live_run.api.get('/api/v1/me?role=admin',
                                headers={**live_run.headers(role), 'X-Role': 'admin'})
    assert response.status_code == 200
    assert response.json()['id'] == live_run.manifest['accounts'][role]['id']
    assert response.json()['role'] == role
    assert live_run.api.get('/api/v1/security/events', headers=live_run.headers(role)).status_code == 200
    # Both users have user_metadata.role=admin; only the trusted profile grants Admin.
    response = live_run.upstream.get('/auth/v1/user', headers=live_run.headers(role))
    assert response.status_code == 200
    assert response.json()['user_metadata']['role'] == 'admin'


@pytest.mark.parametrize('role', ['student', 'admin'])
def test_fixture_fastapi_document_catalog(live_run, role):
    response = live_run.api.get('/api/v1/documents?limit=100', headers=live_run.headers(role))
    assert response.status_code == 200
    visible = {row['id'] for row in response.json()['items']} & live_run.document_ids()
    assert visible == live_run.expected_documents(role)


@pytest.mark.parametrize('role', ['student', 'admin'])
def test_fixture_direct_postgrest_documents_and_chunks(live_run, role):
    ids = ','.join(sorted(live_run.document_ids()))
    # Metadata and content are checked independently. Fixtures are uploaded by the
    # Admin so the Student cannot see restricted metadata via uploader privileges.
    response = live_run.upstream.get('/rest/v1/documents', headers=live_run.headers(role),
                                     params={'id': f'in.({ids})', 'select': 'id'})
    assert response.status_code == 200
    expected = (live_run.document_ids() if role == 'admin'
                else live_run.expected_documents(role))
    assert {row['id'] for row in response.json()} == expected
    response = live_run.upstream.get('/rest/v1/document_chunks', headers=live_run.headers(role),
                                     params={'document_id': f'in.({ids})', 'select': 'id,document_id'})
    assert response.status_code == 200
    assert {row['document_id'] for row in response.json()} == live_run.expected_documents(role)
    # Exact fixture assertions cannot pass vacuously on an empty RLS result.


@pytest.mark.parametrize('role', ['student', 'admin'])
def test_fixture_vector_rpc_has_positive_and_negative_assertions(live_run, role):
    ids = ','.join(sorted(live_run.document_ids()))
    response = live_run.upstream.post('/rest/v1/rpc/match_shield_chunks',
                                      headers=live_run.headers(role),
                                      params={'document_id': f'in.({ids})', 'select': 'chunk_id,document_id'},
                                      json={'query_embedding': live_run.manifest['embedding'], 'match_count': 20})
    assert response.status_code == 200
    assert {row['document_id'] for row in response.json()} == live_run.expected_documents(role)


def test_fixture_student_cannot_promote_profile(live_run):
    student_id = live_run.manifest['accounts']['student']['id']
    response = live_run.upstream.patch('/rest/v1/profiles', headers=live_run.headers('student'),
                                       params={'id': f'eq.{student_id}'}, json={'role': 'admin'})
    assert response.status_code in (200, 204, 403)
    # UPDATE may return 200/204 with zero affected rows under RLS. Status alone is
    # insufficient: verify persisted state through an independent Admin read.
    response = live_run.upstream.get('/rest/v1/profiles', headers=live_run.headers('admin'),
                                     params={'id': f'eq.{student_id}', 'select': 'id,role'})
    assert response.status_code == 200
    assert response.json() == [{'id': student_id, 'role': 'student'}]
    assert live_run.api.get('/api/v1/me', headers=live_run.headers('student')).json()['role'] == 'student'


def test_fixture_tampered_signed_access_token_rejected(live_run):
    pieces = live_run.tokens['student'].split('.')
    pieces[2] = ('A' if pieces[2][0] != 'A' else 'B') + pieces[2][1:]
    response = live_run.api.get('/api/v1/me', headers={'Authorization': 'Bearer ' + '.'.join(pieces)})
    assert response.status_code == 401
    assert response.headers['www-authenticate'] == 'Bearer'
