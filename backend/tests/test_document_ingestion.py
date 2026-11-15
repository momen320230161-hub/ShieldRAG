import hashlib
import io
from datetime import datetime, timezone
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.core.config import Settings
from app.core.upload_limits import MAX_FILE_BYTES, MAX_REVIEW_BODY, MAX_UPLOAD_BODY
from app.main import create_app

STUDENT = '11111111-1111-4111-8111-111111111111'
ADMIN = '22222222-2222-4222-8222-222222222222'
OTHER = '33333333-3333-4333-8333-333333333333'
TOKENS = {'student': STUDENT, 'admin': ADMIN, 'other': OTHER}


def pdf_bytes():
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(output)
    return output.getvalue()


class Cloud:
    """HTTP boundary fake; production services/gateway/dependencies stay in use."""

    def __init__(self):
        self.documents = {}
        self.objects = {}
        self.events = []
        self.calls = []
        self.failure = None
        self.cleanup_fails = False
        self.race = False
        self.integrity_events = {}
        self.audit_failure = None
        self.storage_response = None

    def __call__(self, request):
        import json

        self.calls.append(request)
        path = request.url.path
        privileged = request.headers.get('apikey') == 'sb_secret_synthetic'
        if privileged:
            assert 'authorization' not in request.headers
        else:
            assert request.headers['apikey'] == 'sb_publishable_synthetic'
        token = request.headers.get('authorization', '').removeprefix('Bearer ')
        user_id = TOKENS.get(token)
        role = 'admin' if token == 'admin' else 'student'
        if path == '/auth/v1/user':
            return httpx.Response(200, json={'id': user_id, 'user_metadata': {'role': 'admin'}})
        if path == '/rest/v1/profiles':
            return httpx.Response(200, json=[{'id': user_id, 'role': role}])
        if path == '/rest/v1/documents':
            if privileged and self.failure == 'unresolved':
                return httpx.Response(500, json={'message': 'sensitive details'})
            rows = list(self.documents.values())
            if request.url.params.get('id'):
                doc_id = request.url.params['id'].removeprefix('eq.')
                rows = [d for d in rows if d['id'] == doc_id]
            if not privileged:
                rows = [d for d in rows if role == 'admin' or d['uploaded_by'] == user_id
                        or (d['review_status'] == 'approved' and d['visibility'] == 'public')]
            return httpx.Response(200, json=rows)
        assert privileged, 'Only trusted server requests may write or access Storage'
        if path.startswith('/storage/v1/object/'):
            if request.method == 'DELETE':
                if self.cleanup_fails:
                    return httpx.Response(500, json={'message': 'sensitive storage failure'})
                for key in json.loads(request.content)['prefixes']:
                    self.objects.pop(key, None)
                return httpx.Response(200, json=[])
            if request.method == 'POST':
                key = path.split('/shieldrag-documents/', 1)[1]
                assert request.headers['x-upsert'] == 'false'
                if key in self.objects:
                    return httpx.Response(409, json={'error': 'Duplicate'})
                self.objects[key] = request.content
                if self.failure == 'upload_timeout':
                    raise httpx.ReadTimeout('sensitive upstream details', request=request)
                return httpx.Response(200, json={'Key': key})
            key = path.split('/shieldrag-documents/', 1)[1]
            if self.storage_response is not None:
                status, payload = self.storage_response
                return httpx.Response(status, json=payload)
            return httpx.Response(200, content=self.objects[key]) if key in self.objects else httpx.Response(404)
        payload = json.loads(request.content)
        if path.endswith('/shield_record_integrity_failure'):
            assert payload['p_actor'] == ADMIN
            if self.audit_failure == 'database':
                return httpx.Response(500, json={'code': 'XX000', 'message': 'sensitive database body'})
            if self.audit_failure == 'unavailable':
                return httpx.Response(503, json={'message': 'sensitive upstream body'})
            doc = self.documents[payload['p_document_id']]
            assert doc['sha256'] == payload['p_expected_sha256']
            assert doc['storage_path'] == payload['p_storage_path']
            reasons = {'sha256_mismatch': 'SHA-256 mismatch detected',
                       'stored_object_missing': 'Stored object is missing',
                       'stored_size_exceeded': 'Stored object exceeds size limit',
                       'stored_hash_missing': 'Stored SHA-256 is missing',
                       'invalid_storage_reference': 'Stored object reference is invalid'}
            event_id = payload['p_event_id']
            if event_id not in self.integrity_events:
                self.integrity_events[event_id] = {
                    'id': event_id, 'user_id': ADMIN, 'document_id': doc['id'],
                    'event_type': 'document_integrity_failure', 'decision': 'deny',
                    'reason': reasons[payload['p_failure']]}
                self.events.append('document_integrity_failure')
                if self.audit_failure == 'lost_response':
                    raise httpx.ReadTimeout('sensitive upstream details', request=request)
            if self.audit_failure == 'malformed_ack':
                return httpx.Response(200, json={'unexpected': 'sensitive response body'})
            return httpx.Response(200, json=event_id)
        if path.endswith('/shield_register_document'):
            if self.failure == 'definite':
                return httpx.Response(422, json={'code': 'PT422', 'message': 'sensitive details'})
            if self.failure == 'sql_failure':
                return httpx.Response(500, json={'code': '23514', 'message': 'sensitive details'})
            if self.failure == 'unknown_absent':
                return httpx.Response(500, json={'message': 'sensitive details'})
            doc = {'id': payload['p_id'], 'uploaded_by': payload['p_actor'],
                   'original_name': payload['p_original_name'], 'storage_path': payload['p_storage_path'],
                   'sha256': payload['p_sha256'], 'visibility': payload['p_visibility'],
                   'review_status': 'pending', 'index_status': 'not_indexed',
                   'reviewed_by': None, 'reviewed_at': None,
                   'created_at': datetime.now(timezone.utc).isoformat()}
            self.documents[doc['id']] = doc
            self.events.append('document_uploaded')
            if self.failure == 'lost_transport_commit':
                raise httpx.ReadTimeout('sensitive upstream details', request=request)
            if self.failure in ('lost_commit', 'unresolved'):
                return httpx.Response(500, json={'message': 'sensitive details'})
            return httpx.Response(200, json=[doc])
        if path.endswith('/shield_review_document'):
            doc = self.documents[payload['p_id']]
            if self.race:
                return httpx.Response(409, json={'code': 'PT409'})
            assert payload['p_actor'] == ADMIN
            assert doc['review_status'] == 'pending'
            if payload['p_decision'] == 'approved':
                assert payload['p_verified_sha256'] == doc['sha256']
            doc.update(review_status=payload['p_decision'], reviewed_by=payload['p_actor'],
                       reviewed_at=datetime.now(timezone.utc).isoformat(), index_status='not_indexed')
            self.events.append('document_' + payload['p_decision'])
            return httpx.Response(200, json=[doc])
        raise AssertionError(path)


@pytest.fixture
def cloud():
    return Cloud()


@pytest.fixture
def api(cloud):
    settings = Settings(_env_file=None, supabase_url='https://synthetic.supabase.co',
                        supabase_publishable_key='sb_publishable_synthetic',
                        supabase_secret_key='sb_secret_synthetic')
    with TestClient(create_app(settings, httpx.MockTransport(cloud))) as client:
        yield client


def headers(role='student'):
    return {'Authorization': 'Bearer ' + role}


def upload(api, data=b'synthetic UTF-8 text\n', name='synthetic.txt', mime='text/plain',
           visibility='public', role='student'):
    return api.post('/api/v1/documents', headers=headers(role), data={'visibility': visibility},
                    files={'file': (name, data, mime)})


@pytest.mark.parametrize('name,mime,data', [('synthetic.txt', 'text/plain', b'valid text'),
    ('synthetic.pdf', 'application/pdf', pdf_bytes()), ('synthetic.TXT', 'text/plain', b'\xef\xbb\xbftext')])
def test_upload_success_private_key_hash_and_initial_state(api, cloud, name, mime, data):
    response = upload(api, data, name, mime, 'restricted')
    assert response.status_code == 201, response.text
    result = response.json()
    assert result['uploaded_by'] == STUDENT
    assert result['sha256'] == hashlib.sha256(data).hexdigest()
    assert result['review_status'] == 'pending'
    assert result['index_status'] == 'not_indexed'
    assert result['visibility'] == 'restricted'
    assert 'storage_path' not in result and 'content' not in result
    assert cloud.events == ['document_uploaded']
    key = next(iter(cloud.objects))
    assert key == f'ingestions/{STUDENT}/{result["id"]}.{name.rsplit(".",1)[1].lower()}'
    assert cloud.objects[key] == data


@pytest.mark.parametrize('name,mime,data,status', [
    ('empty.txt', 'text/plain', b'', 422), ('spaces.txt', 'text/plain', b'   \n', 422),
    ('binary.txt', 'text/plain', b'abc\x00def', 422), ('invalid.txt', 'text/plain', b'\xff\xfe', 422),
    ('spoof.pdf', 'application/pdf', b'not a PDF', 422),
    ('spoof.txt', 'text/plain', pdf_bytes(), 422),
    ('spoof.pdf', 'text/plain', pdf_bytes(), 415),
    ('wrong.txt', 'application/octet-stream', b'valid text', 415),
    ('corrupt.pdf', 'application/pdf', b'%PDF-1.7\nnot-a-pdf\n%%EOF', 422),
    ('truncated.pdf', 'application/pdf', pdf_bytes()[:-10], 422),
    ('polyglot.pdf', 'application/pdf', pdf_bytes() + b'bad trailer', 422),
    ('../escape.txt', 'text/plain', b'text', 422),
    ('a\\escape.txt', 'text/plain', b'text', 422), ('C:escape.txt', 'text/plain', b'text', 422),
    ('CON.txt', 'text/plain', b'text', 422), ('a..txt', 'text/plain', b'text', 422),
    ('file.exe', 'application/x-msdownload', b'MZ123', 422),
])
def test_file_validation_rejects_without_storage_writes(api, cloud, name, mime, data, status):
    response = upload(api, data, name, mime)
    assert response.status_code == status
    assert not cloud.objects and not cloud.documents and not cloud.events
    assert not any('/storage/' in call.url.path for call in cloud.calls)


def test_file_and_request_size_limits(api, cloud):
    assert upload(api, b'a' * MAX_FILE_BYTES).status_code == 201
    assert upload(api, b'a' * (MAX_FILE_BYTES + 1)).status_code == 413
    response = api.post('/api/v1/documents', headers={**headers(),
                         'Content-Length': str(MAX_UPLOAD_BODY + 1)}, content=b'')
    assert response.status_code == 413


def test_chunked_request_is_limited_before_multipart_spooling(api):
    def body():
        yield b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="large.txt"\r\nContent-Type: text/plain\r\n\r\n'
        yield b'a' * (MAX_UPLOAD_BODY + 1)
        yield b'\r\n--boundary--\r\n'

    response = api.post('/api/v1/documents', headers={**headers(),
                        'Content-Type': 'multipart/form-data; boundary=boundary'}, content=body())
    assert response.status_code == 413


def test_encrypted_pdf_is_rejected(api, cloud):
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt('synthetic password')
    output = io.BytesIO()
    writer.write(output)
    assert upload(api, output.getvalue(), 'encrypted.pdf', 'application/pdf').status_code == 422
    assert not cloud.objects


def test_pdf_with_invalid_content_reference_is_rejected(api, cloud):
    from pypdf.generic import NameObject, TextStringObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=72, height=72)
    page[NameObject('/Contents')] = TextStringObject('not a content stream')
    output = io.BytesIO()
    writer.write(output)
    assert upload(api, output.getvalue(), 'invalid.pdf', 'application/pdf').status_code == 422
    assert not cloud.objects


def test_review_rejects_extra_fields_and_empty_reason(api, cloud):
    doc_id = upload(api).json()['id']
    for operation, body in [('approve', {'sha256': 'untrusted'}), ('reject', {'reason': '   '}),
                             ('reject', {'reason': 'x', 'reviewed_by': OTHER})]:
        assert api.post(f'/api/v1/documents/{doc_id}/{operation}',
                        headers=headers('admin'), json=body).status_code == 422
    assert cloud.events == ['document_uploaded']


def test_review_json_body_is_bounded(api, cloud):
    doc_id = upload(api).json()['id']
    assert api.post(f'/api/v1/documents/{doc_id}/reject', headers=headers('admin'),
                    json={'reason': 'a' * (MAX_REVIEW_BODY + 1)}).status_code == 413
    assert cloud.events == ['document_uploaded']


@pytest.mark.parametrize('extra', ['uploaded_by', 'role', 'sha256', 'review_status', 'storage_path'])
def test_client_cannot_supply_server_fields(api, cloud, extra):
    response = api.post('/api/v1/documents', headers=headers(),
                        data={'visibility': 'public', extra: 'untrusted'},
                        files={'file': ('safe.txt', b'text', 'text/plain')})
    assert response.status_code in (400, 422)
    assert not cloud.objects


def test_authentication_and_single_file_contract(api, cloud):
    assert api.post('/api/v1/documents', files={'file': ('safe.txt', b'text', 'text/plain')}).status_code == 401
    response = api.post('/api/v1/documents', headers=headers(), files=[
        ('file', ('one.txt', b'one', 'text/plain')), ('file', ('two.txt', b'two', 'text/plain'))])
    assert response.status_code in (400, 422)
    assert not cloud.objects
    assert upload(api, visibility='untrusted').status_code == 422


def test_metadata_ownership_and_safe_response(api, cloud):
    doc_id = upload(api, visibility='restricted').json()['id']
    for role in ('student', 'admin'):
        response = api.get('/api/v1/documents/' + doc_id, headers=headers(role))
        assert response.status_code == 200
        assert 'storage_path' not in response.json()
    assert api.get('/api/v1/documents/' + doc_id, headers=headers('other')).status_code == 404
    assert api.get('/api/v1/documents/' + doc_id).status_code == 401


@pytest.mark.parametrize('decision,body', [('approve', {}), ('reject', {'reason': 'synthetic rejection'})])
def test_admin_review_and_duplicate_transition(api, cloud, decision, body):
    doc_id = upload(api).json()['id']
    path = f'/api/v1/documents/{doc_id}/{decision}'
    assert api.post(path, headers=headers(), json=body).status_code == 403
    assert not any('/authenticated/' in call.url.path for call in cloud.calls)
    response = api.post(path, headers=headers('admin'), json=body)
    assert response.status_code == 200
    assert response.json()['reviewed_by'] == ADMIN
    assert response.json()['reviewed_at']
    assert response.json()['index_status'] == 'not_indexed'
    assert response.json()['review_status'] == ('approved' if decision == 'approve' else 'rejected')
    assert api.post(path, headers=headers('admin'), json=body).status_code == 409
    assert len(cloud.events) == 2


def test_tampering_missing_object_and_review_race(api, cloud):
    doc_id = upload(api).json()['id']
    key = next(iter(cloud.objects))
    original = cloud.objects[key]
    cloud.objects[key] = b'tampered'
    path = f'/api/v1/documents/{doc_id}/approve'
    assert api.post(path, headers=headers('admin'), json={}).status_code == 409
    cloud.objects.pop(key)
    assert api.post(path, headers=headers('admin'), json={}).status_code == 409
    cloud.objects[key] = original
    cloud.race = True
    assert api.post(path, headers=headers('admin'), json={}).status_code == 409
    assert cloud.documents[doc_id]['review_status'] == 'pending'
    assert cloud.events == ['document_uploaded', 'document_integrity_failure', 'document_integrity_failure']
    assert {e['reason'] for e in cloud.integrity_events.values()} == {
        'SHA-256 mismatch detected', 'Stored object is missing'}


def test_integrity_failure_persists_exact_safe_reviewer_event(api, cloud):
    import json

    doc_id = upload(api, data=b'original private file bytes').json()['id']
    cloud.objects[next(iter(cloud.objects))] = b'tampered private file bytes'
    path = f'/api/v1/documents/{doc_id}/approve'
    assert api.post(path, headers=headers('student'), json={}).status_code == 403
    assert api.post(path, json={}).status_code == 401
    assert not cloud.integrity_events
    assert api.post(path, headers=headers('admin'), json={}).status_code == 409
    assert cloud.documents[doc_id]['review_status'] == 'pending'
    assert cloud.documents[doc_id]['reviewed_by'] is None
    assert len(cloud.integrity_events) == 1
    event = next(iter(cloud.integrity_events.values()))
    UUID(event['id'])
    assert event == {'id': event['id'], 'user_id': ADMIN, 'document_id': doc_id,
                     'event_type': 'document_integrity_failure', 'decision': 'deny',
                     'reason': 'SHA-256 mismatch detected'}
    encoded = json.dumps(event)
    for forbidden in ('private file bytes', 'sb_secret_', 'sb_publishable_', 'storage_path', 'Authorization'):
        assert forbidden not in encoded
    assert not any(call.url.path.endswith('/shield_review_document') for call in cloud.calls)


def test_lost_audit_acknowledgement_retries_same_server_id_once(api, cloud):
    import json

    doc_id = upload(api).json()['id']
    cloud.objects[next(iter(cloud.objects))] = b'tampered'
    cloud.audit_failure = 'lost_response'
    assert api.post(f'/api/v1/documents/{doc_id}/approve', headers=headers('admin'), json={}).status_code == 409
    attempts = [json.loads(r.content)['p_event_id'] for r in cloud.calls
                if r.url.path.endswith('/shield_record_integrity_failure')]
    assert len(attempts) == 2 and len(set(attempts)) == 1
    assert len(cloud.integrity_events) == 1
    assert cloud.documents[doc_id]['review_status'] == 'pending'


@pytest.mark.parametrize('failure,count,attempts', [('database', 0, 1), ('unavailable', 0, 2),
                                                   ('malformed_ack', 1, 2)])
def test_unconfirmed_integrity_audit_fails_closed(api, cloud, caplog, failure, count, attempts):
    doc_id = upload(api).json()['id']
    cloud.objects[next(iter(cloud.objects))] = b'tampered'
    cloud.audit_failure = failure
    response = api.post(f'/api/v1/documents/{doc_id}/approve', headers=headers('admin'), json={})
    assert response.status_code == 503
    assert response.json()['detail'] == 'Integrity audit could not be confirmed; approval denied'
    assert cloud.documents[doc_id]['review_status'] == 'pending'
    assert cloud.documents[doc_id]['reviewed_by'] is None
    assert len(cloud.integrity_events) == count
    assert sum(r.url.path.endswith('/shield_record_integrity_failure') for r in cloud.calls) == attempts
    assert not any(r.url.path.endswith('/shield_review_document') for r in cloud.calls)
    assert 'persistence unconfirmed' in caplog.text
    assert 'sensitive' not in response.text + caplog.text


def test_separate_http_review_attempts_are_distinct_audit_events(api, cloud):
    doc_id = upload(api).json()['id']
    cloud.objects[next(iter(cloud.objects))] = b'tampered'
    for _ in range(2):
        assert api.post(f'/api/v1/documents/{doc_id}/approve', headers=headers('admin'), json={}).status_code == 409
    assert len(cloud.integrity_events) == 2
    assert cloud.documents[doc_id]['review_status'] == 'pending'


@pytest.mark.parametrize('status,payload,expected,reason', [
    (400, {'statusCode': '404', 'error': 'not_found', 'message': 'sensitive'}, 409, 'Stored object is missing'),
    (400, {'statusCode': '400', 'error': 'BadRequest', 'message': 'sensitive'}, 503, None),
    (403, {'message': 'sensitive'}, 503, None), (500, {'message': 'sensitive'}, 503, None)])
def test_only_confirmed_storage_failure_is_audited(api, cloud, status, payload, expected, reason):
    doc_id = upload(api).json()['id']
    cloud.storage_response = status, payload
    response = api.post(f'/api/v1/documents/{doc_id}/approve', headers=headers('admin'), json={})
    assert response.status_code == expected
    assert cloud.documents[doc_id]['review_status'] == 'pending'
    assert len(cloud.integrity_events) == (1 if reason else 0)
    if reason:
        assert next(iter(cloud.integrity_events.values()))['reason'] == reason
    assert 'sensitive' not in response.text


@pytest.mark.parametrize('field', ['event_type', 'event_id', 'decision', 'user_id'])
def test_client_cannot_choose_integrity_event_fields(api, cloud, field):
    doc_id = upload(api).json()['id']
    response = api.post(f'/api/v1/documents/{doc_id}/approve', headers=headers('admin'), json={field: 'untrusted'})
    assert response.status_code == 422 and not cloud.integrity_events


@pytest.mark.parametrize('failure,reason', [
    ('hash_missing', 'Stored SHA-256 is missing'), ('oversized', 'Stored object exceeds size limit'),
    ('invalid_reference', 'Stored object reference is invalid')])
def test_other_confirmed_integrity_failures_are_safely_audited(api, cloud, failure, reason):
    doc_id = upload(api).json()['id']
    if failure == 'hash_missing':
        cloud.documents[doc_id]['sha256'] = None
    elif failure == 'oversized':
        cloud.objects[next(iter(cloud.objects))] = b'a' * (MAX_FILE_BYTES + 1)
    else:
        cloud.documents[doc_id]['storage_path'] = 'invalid/reference.txt'
    assert api.post(f'/api/v1/documents/{doc_id}/approve', headers=headers('admin'), json={}).status_code == 409
    assert cloud.documents[doc_id]['review_status'] == 'pending'
    assert len(cloud.integrity_events) == 1
    assert next(iter(cloud.integrity_events.values()))['reason'] == reason


def test_retrieval_catalog_excludes_pending_rejected_and_student_restricted(api, cloud):
    public_id = upload(api).json()['id']
    restricted_id = upload(api, visibility='restricted').json()['id']
    rejected_id = upload(api).json()['id']
    assert api.get('/api/v1/documents', headers=headers()).json()['items'] == []
    for doc_id in (public_id, restricted_id):
        assert api.post(f'/api/v1/documents/{doc_id}/approve', headers=headers('admin'), json={}).status_code == 200
    assert api.post(f'/api/v1/documents/{rejected_id}/reject', headers=headers('admin'), json={'reason':'unsafe'}).status_code == 200
    assert {d['id'] for d in api.get('/api/v1/documents', headers=headers()).json()['items']} == {public_id}
    assert {d['id'] for d in api.get('/api/v1/documents', headers=headers('admin')).json()['items']} == {public_id, restricted_id}
    assert api.get('/api/v1/documents/' + public_id, headers=headers('other')).status_code == 200
    assert api.get('/api/v1/documents/' + rejected_id, headers=headers('other')).status_code == 404


@pytest.mark.parametrize('failure,status', [('definite', 422), ('sql_failure', 503)])
def test_compensation_on_definite_database_failure(api, cloud, failure, status):
    cloud.failure = failure
    assert upload(api).status_code == status
    assert not cloud.objects and not cloud.documents
    assert sum(call.method == 'DELETE' for call in cloud.calls) == 1


def test_upload_collision_never_deletes_existing_object(api, cloud, monkeypatch):
    from app.services import documents

    document_id = UUID('44444444-4444-4444-8444-444444444444')
    monkeypatch.setattr(documents, 'uuid4', lambda: document_id)
    key = f'ingestions/{STUDENT}/{document_id}.txt'
    cloud.objects[key] = b'existing document bytes'
    assert upload(api).status_code == 503
    assert cloud.objects[key] == b'existing document bytes'
    assert not any(call.method == 'DELETE' for call in cloud.calls)


@pytest.mark.parametrize('failure,expected', [('lost_commit', 201), ('lost_transport_commit', 201),
                                            ('unknown_absent', 503), ('unresolved', 503)])
def test_uncertain_commit_does_not_delete_a_possible_committed_object(api, cloud, failure, expected):
    cloud.failure = failure
    response = upload(api)
    assert response.status_code == expected
    assert cloud.objects
    assert not any(call.method == 'DELETE' for call in cloud.calls)
    assert 'sensitive' not in response.text and 'sb_secret_' not in response.text


def test_uncertain_storage_upload_is_not_blindly_deleted(api, cloud, caplog):
    cloud.failure = 'upload_timeout'
    response = upload(api)
    assert response.status_code == 503
    assert cloud.objects and not cloud.documents
    assert not any(call.method == 'DELETE' for call in cloud.calls)
    assert 'reconciliation' in caplog.text and 'sensitive' not in response.text


def test_failed_compensation_is_bounded_and_logged(api, cloud, caplog):
    cloud.failure = 'definite'
    cloud.cleanup_fails = True
    response = upload(api)
    assert response.status_code == 422
    assert sum(call.method == 'DELETE' for call in cloud.calls) == 2
    assert 'reconciliation' in caplog.text
    assert 'sb_secret_' not in caplog.text and 'sensitive' not in response.text


def test_missing_secret_fails_closed_for_writes_only(cloud):
    settings = Settings(_env_file=None, supabase_url='https://synthetic.supabase.co',
                        supabase_publishable_key='sb_publishable_synthetic')
    with TestClient(create_app(settings, httpx.MockTransport(cloud))) as client:
        assert upload(client).status_code == 503
        assert client.get('/health').status_code == 200
        assert client.get('/api/v1/me', headers=headers()).status_code == 200
    assert not cloud.objects
