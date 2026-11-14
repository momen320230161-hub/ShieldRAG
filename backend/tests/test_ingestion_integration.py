"""Real Storage + FastAPI ingestion. Requires explicit opt-in and server key."""
import hashlib
import io
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID

import pytest
from pypdf import PdfWriter

from app.db.document_store import BUCKET, object_key
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
                    'document_uploaded', 'document_approved', 'document_rejected') for event in audit.json()):
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
        headers=ingestion.headers('admin'), json={}).status_code == 409
    response = ingestion.api.get('/api/v1/documents/' + doc['id'], headers=ingestion.headers('admin'))
    assert response.json()['review_status'] == 'pending'


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
