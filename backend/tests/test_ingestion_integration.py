"""Real Storage + FastAPI ingestion. Requires explicit opt-in and server key."""
import hashlib
import io
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID

import pytest
import httpx
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.db.document_store import BUCKET, object_key
from app.main import create_app
from test_integration import live_run, settings  # Reuse synthetic-account fixtures.

pytestmark = pytest.mark.integration


@pytest.fixture(scope='module')
def ingestion(live_run, settings):
    if os.getenv('SHIELDRAG_INGESTION') != '1':
        pytest.skip('Set SHIELDRAG_INGESTION=1 for real private Storage writes')
    secret = settings.supabase_secret_key.get_secret_value()
    if not secret.startswith('sb_secret_'):
        pytest.fail('Live ingestion requires SUPABASE_SECRET_KEY in private configuration', pytrace=False)
    marker = 'shieldrag-live-' + live_run.manifest['run_id'] + '-'
    privileged = {'apikey': secret}  # No user bearer token on these test-only calls.
    users = {a['id'] for a in live_run.manifest['accounts'].values()}
    manifest_path = Path(os.getenv('SHIELDRAG_FIXTURE_MANIFEST', '.integration/live/manifest.json'))
    journal = manifest_path.parent / 'ingestion-journal.json'
    journal.write_text(json.dumps({'run_id': live_run.manifest['run_id'], 'marker': marker,
                                   'fixture_users': sorted(users)}), encoding='utf-8')
    # Return a redacted LiveRun rather than a dictionary containing the server key.
    live_run.ingestion_marker = marker
    try:
        yield live_run
    finally:
        response = live_run.upstream.get('/rest/v1/documents', headers=privileged, params={
            'uploaded_by': 'in.(' + ','.join(sorted(users)) + ')',
            'original_name': 'like.' + marker + '*',
            'select': 'id,uploaded_by,original_name,storage_path', 'limit': '100'})
        if response.status_code != 200:
            pytest.fail('Ingestion cleanup could not inspect fixture metadata; retain journal', pytrace=False)
        for document in response.json():
            doc_id = str(UUID(document['id']))
            key = document['storage_path']
            extension = key.rsplit('.', 1)[-1]
            if (document['uploaded_by'] not in users or not document['original_name'].startswith(marker)
                    or extension not in ('pdf', 'txt') or key != object_key(
                        UUID(document['uploaded_by']), UUID(doc_id), extension)):
                pytest.fail('Ingestion cleanup refused an unexpected fixture reference', pytrace=False)
            chunks = live_run.upstream.get('/rest/v1/document_chunks', headers=privileged,
                                           params={'document_id': f'eq.{doc_id}', 'select': 'id'})
            if chunks.status_code != 200 or chunks.json() != []:
                pytest.fail('Ingestion cleanup refused unexpected chunk data', pytrace=False)
            audit = live_run.upstream.get('/rest/v1/security_events', headers=privileged,
                                          params={'document_id': f'eq.{doc_id}', 'select': 'user_id,event_type'})
            if audit.status_code != 200 or any(event['user_id'] not in users or event['event_type'] not in (
                    'document_uploaded', 'document_approved', 'document_rejected',
                    'document_integrity_failure') for event in audit.json()):
                pytest.fail('Ingestion cleanup refused unexpected audit data', pytrace=False)
            # Remove only the exact server-generated object; never delete Storage via SQL.
            removed = live_run.upstream.request('DELETE', '/storage/v1/object/' + BUCKET, headers=privileged,
                                                 json={'prefixes': [key]})
            if removed.status_code != 200:
                pytest.fail('Ingestion Storage cleanup failed; retain journal', pytrace=False)
            events = live_run.upstream.delete('/rest/v1/security_events', headers=privileged, params={
                'document_id': f'eq.{doc_id}', 'user_id': 'in.(' + ','.join(sorted(users)) + ')'})
            deleted = live_run.upstream.delete('/rest/v1/documents', headers=privileged,
                                                params={'id': f'eq.{doc_id}'})
            if events.status_code not in (200, 204) or deleted.status_code not in (200, 204):
                pytest.fail('Ingestion metadata cleanup failed; retain journal', pytrace=False)
        journal.unlink()


def upload(run, suffix='sample', extension='txt', visibility='public', role='student'):
    data = b'Synthetic secure ingestion fixture\n'
    mime = 'text/plain'
    if extension == 'pdf':
        output = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.write(output)
        data, mime = output.getvalue(), 'application/pdf'
    response = run.api.post('/api/v1/documents', headers=run.headers(role), data={'visibility': visibility},
                             files={'file': (run.ingestion_marker + suffix + '.' + extension, data, mime)})
    assert response.status_code == 201
    return response.json(), data


@pytest.mark.parametrize('extension', ['pdf', 'txt'])
def test_live_private_upload_hash_initial_state_and_approval(ingestion, settings, extension):
    document, data = upload(ingestion, extension=extension, visibility='restricted')
    assert document['sha256'] == hashlib.sha256(data).hexdigest()
    assert document['review_status'] == 'pending' and document['index_status'] == 'not_indexed'
    assert 'storage_path' not in document
    doc_id = document['id']
    key = object_key(UUID(document['uploaded_by']), UUID(doc_id), extension)
    response = ingestion.upstream.get('/storage/v1/object/authenticated/' + BUCKET + '/' + key,
                                      headers={'apikey': settings.supabase_secret_key.get_secret_value()})
    assert response.status_code == 200 and response.content == data
    for role in ('student', 'admin'):
        response = ingestion.upstream.get('/storage/v1/object/authenticated/' + BUCKET + '/' + key,
                                          headers=ingestion.headers(role))
        assert response.status_code != 200  # Bucket remains backend-only for content.
    public = ingestion.upstream.get('/storage/v1/object/public/' + BUCKET + '/' + key)
    assert public.status_code != 200
    assert ingestion.api.post(f'/api/v1/documents/{doc_id}/approve', headers=ingestion.headers('student'),
                               json={}).status_code == 403
    approved = ingestion.api.post(f'/api/v1/documents/{doc_id}/approve', headers=ingestion.headers('admin'), json={})
    assert approved.status_code == 200
    assert approved.json()['review_status'] == 'approved'
    assert approved.json()['index_status'] == 'not_indexed'
    assert approved.json()['reviewed_by'] == ingestion.manifest['accounts']['admin']['id']
    assert ingestion.api.post(f'/api/v1/documents/{doc_id}/approve', headers=ingestion.headers('admin'),
                               json={}).status_code == 409


def test_live_metadata_visibility_and_rejection(ingestion):
    doc, _ = upload(ingestion, 'admin-public', role='admin')
    path = '/api/v1/documents/' + doc['id']
    assert ingestion.api.get(path, headers=ingestion.headers('student')).status_code == 404
    assert ingestion.api.get(path, headers=ingestion.headers('admin')).status_code == 200
    assert ingestion.api.post(path + '/approve', headers=ingestion.headers('admin'), json={}).status_code == 200
    assert ingestion.api.get(path, headers=ingestion.headers('student')).status_code == 200
    restricted, _ = upload(ingestion, 'admin-restricted', visibility='restricted', role='admin')
    restricted_path = '/api/v1/documents/' + restricted['id']
    assert ingestion.api.post(restricted_path + '/approve', headers=ingestion.headers('admin'), json={}).status_code == 200
    assert ingestion.api.get(restricted_path, headers=ingestion.headers('student')).status_code == 404
    rejected, _ = upload(ingestion, 'rejected')
    rejected_path = '/api/v1/documents/' + rejected['id']
    assert ingestion.api.post(rejected_path + '/reject', headers=ingestion.headers('student'),
                               json={'reason': 'synthetic'}).status_code == 403
    response = ingestion.api.post(rejected_path + '/reject', headers=ingestion.headers('admin'),
                                  json={'reason': 'synthetic rejection'})
    assert response.status_code == 200 and response.json()['review_status'] == 'rejected'
    assert ingestion.api.post(rejected_path + '/approve', headers=ingestion.headers('admin'), json={}).status_code == 409
    assert rejected['id'] not in {d['id'] for d in ingestion.api.get('/api/v1/documents?limit=100',
        headers=ingestion.headers('admin')).json()['items']}


def test_live_tampering_blocks_approval(ingestion, settings):
    doc, _ = upload(ingestion, 'tampering')
    key = object_key(UUID(doc['uploaded_by']), UUID(doc['id']), 'txt')
    response = ingestion.upstream.put('/storage/v1/object/' + BUCKET + '/' + key,
        headers={'apikey': settings.supabase_secret_key.get_secret_value(), 'Content-Type': 'text/plain'},
        content=b'Synthetic tampered bytes')
    assert response.status_code == 200
    assert ingestion.api.post('/api/v1/documents/' + doc['id'] + '/approve',
        headers=ingestion.headers('student'), json={}).status_code == 403
    assert integrity_events(ingestion, doc['id']) == []
    assert ingestion.api.post('/api/v1/documents/' + doc['id'] + '/approve',
        headers=ingestion.headers('admin'), json={}).status_code == 409
    response = ingestion.api.get('/api/v1/documents/' + doc['id'], headers=ingestion.headers('admin'))
    assert response.json()['review_status'] == 'pending'
    assert response.json()['reviewed_by'] is None
    events = integrity_events(ingestion, doc['id'])
    assert len(events) == 1
    event = events[0]
    UUID(event['id'])
    assert event == {'id': event['id'], 'user_id': ingestion.manifest['accounts']['admin']['id'],
                     'document_id': doc['id'], 'event_type': 'document_integrity_failure',
                     'decision': 'deny', 'reason': 'SHA-256 mismatch detected'}
    assert 'Synthetic tampered bytes' not in json.dumps(event)


def integrity_events(run, document_id):
    response = run.upstream.get('/rest/v1/security_events', headers=run.headers('admin'), params={
        'document_id': 'eq.' + document_id, 'event_type': 'eq.document_integrity_failure',
        'select': 'id,user_id,document_id,event_type,decision,reason'})
    assert response.status_code == 200
    return response.json()


def test_live_missing_object_is_audited_without_approving(ingestion, settings):
    doc, _ = upload(ingestion, 'missing-object')
    key = object_key(UUID(doc['uploaded_by']), UUID(doc['id']), 'txt')
    response = ingestion.upstream.request('DELETE', '/storage/v1/object/' + BUCKET,
        headers={'apikey': settings.supabase_secret_key.get_secret_value()}, json={'prefixes': [key]})
    assert response.status_code == 200
    response = ingestion.api.post('/api/v1/documents/' + doc['id'] + '/approve',
                                  headers=ingestion.headers('admin'), json={})
    assert response.status_code == 409
    assert ingestion.api.get('/api/v1/documents/' + doc['id'],
                             headers=ingestion.headers('admin')).json()['review_status'] == 'pending'
    events = integrity_events(ingestion, doc['id'])
    assert len(events) == 1 and events[0]['reason'] == 'Stored object is missing'


class DropFirstAuditAcknowledgement(httpx.AsyncBaseTransport):
    """Forward real requests; drop one real successful audit response after commit."""

    def __init__(self):
        self.inner = httpx.AsyncHTTPTransport(trust_env=False)
        self.dropped = False
        self.event_ids = []

    async def handle_async_request(self, request):
        audit = request.url.path.endswith('/shield_record_integrity_failure')
        if audit:
            self.event_ids.append(json.loads(request.content)['p_event_id'])
        response = await self.inner.handle_async_request(request)
        if audit and response.status_code == 200 and not self.dropped:
            self.dropped = True
            await response.aread()
            await response.aclose()
            raise httpx.ReadTimeout('Controlled lost audit acknowledgement', request=request)
        return response

    async def aclose(self):
        await self.inner.aclose()


def test_live_lost_audit_acknowledgement_does_not_duplicate(ingestion, settings):
    doc, _ = upload(ingestion, 'lost-audit-ack')
    key = object_key(UUID(doc['uploaded_by']), UUID(doc['id']), 'txt')
    changed = ingestion.upstream.put('/storage/v1/object/' + BUCKET + '/' + key,
        headers={'apikey': settings.supabase_secret_key.get_secret_value(), 'Content-Type': 'text/plain'},
        content=b'Synthetic tampered bytes')
    assert changed.status_code == 200
    transport = DropFirstAuditAcknowledgement()
    with TestClient(create_app(settings, transport)) as api:
        assert api.post('/api/v1/documents/' + doc['id'] + '/approve',
                        headers=ingestion.headers('admin'), json={}).status_code == 409
    assert transport.dropped and len(transport.event_ids) == 2
    assert len(set(transport.event_ids)) == 1
    events = integrity_events(ingestion, doc['id'])
    assert len(events) == 1 and events[0]['id'] == transport.event_ids[0]
    assert ingestion.api.get('/api/v1/documents/' + doc['id'],
                             headers=ingestion.headers('admin')).json()['review_status'] == 'pending'


def test_live_audit_retry_association_and_direct_user_write_denial(ingestion, settings):
    doc, _ = upload(ingestion, 'audit-permissions')
    key = object_key(UUID(doc['uploaded_by']), UUID(doc['id']), 'txt')
    changed = ingestion.upstream.put('/storage/v1/object/' + BUCKET + '/' + key,
        headers={'apikey': settings.supabase_secret_key.get_secret_value(), 'Content-Type': 'text/plain'},
        content=b'Synthetic tampered bytes')
    assert changed.status_code == 200
    assert ingestion.api.post('/api/v1/documents/' + doc['id'] + '/approve',
                             headers=ingestion.headers('admin'), json={}).status_code == 409
    original = integrity_events(ingestion, doc['id'])
    assert len(original) == 1
    payload = {'p_actor': ingestion.manifest['accounts']['admin']['id'], 'p_document_id': doc['id'],
               'p_event_id': original[0]['id'], 'p_failure': 'sha256_mismatch',
               'p_expected_sha256': doc['sha256'], 'p_storage_path': key,
               'p_observed_sha256': hashlib.sha256(b'Synthetic tampered bytes').hexdigest()}
    for _ in range(2):
        response = ingestion.upstream.post('/rest/v1/rpc/shield_record_integrity_failure',
            headers={'apikey': settings.supabase_secret_key.get_secret_value()}, json=payload)
        assert response.status_code == 200 and response.json() == original[0]['id']
    for role in ('student', 'admin'):
        assert ingestion.upstream.post('/rest/v1/rpc/shield_record_integrity_failure',
            headers=ingestion.headers(role), json=payload).status_code == 403
        assert ingestion.upstream.post('/rest/v1/security_events', headers=ingestion.headers(role), json={
            'user_id': payload['p_actor'], 'document_id': doc['id'], 'event_type': 'document_integrity_failure',
            'decision': 'deny', 'reason': 'client supplied raw data'}).status_code == 403
        updated = ingestion.upstream.patch('/rest/v1/security_events', headers=ingestion.headers(role),
            params={'id': 'eq.' + original[0]['id']}, json={'reason': 'client supplied raw data'})
        assert updated.status_code in (200, 204, 403)
    assert integrity_events(ingestion, doc['id']) == original
    other, _ = upload(ingestion, 'audit-association')
    wrong = {**payload, 'p_document_id': other['id'], 'p_expected_sha256': other['sha256'],
             'p_storage_path': object_key(UUID(other['uploaded_by']), UUID(other['id']), 'txt')}
    assert ingestion.upstream.post('/rest/v1/rpc/shield_record_integrity_failure',
        headers={'apikey': settings.supabase_secret_key.get_secret_value()}, json=wrong).status_code == 409
    assert integrity_events(ingestion, other['id']) == []
    assert integrity_events(ingestion, doc['id']) == original


def test_live_concurrent_review_has_one_winner_and_one_audit_event(ingestion, settings):
    doc, _ = upload(ingestion, 'concurrent')
    path = '/api/v1/documents/' + doc['id']

    def review(operation):
        return ingestion.api.post(path + '/' + operation, headers=ingestion.headers('admin'),
                                   json={} if operation == 'approve' else {'reason': 'synthetic rejection'}).status_code

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(review, ['approve', 'reject']))
    assert sorted(results) == [200, 409]
    response = ingestion.upstream.get('/rest/v1/security_events', headers={
        'apikey': settings.supabase_secret_key.get_secret_value()},
        params={'document_id': 'eq.' + doc['id'], 'select': 'event_type,decision'})
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 2  # One registration, one committed review.
    assert sum(e['event_type'] in ('document_approved', 'document_rejected') for e in events) == 1
