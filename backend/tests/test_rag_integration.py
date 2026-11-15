"""Opt-in, billable Gemini + real Supabase RAG acceptance; synthetic data only."""
import json
import math
import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import httpx
from fastapi.testclient import TestClient
from app.main import create_app

from app.db.document_store import BUCKET, object_key
from test_integration import live_run, settings
from test_rag import text_pdf

pytestmark = pytest.mark.integration
CONSENT = {'external_processing_authorized': True}


def remove_object(run,headers,key):
    # Exact-object deletion is idempotent, including a lost successful response.
    for attempt in range(2):
        try:
            response = run.upstream.request('DELETE','/storage/v1/object/' + BUCKET,
                headers=headers,json={'prefixes':[key]},timeout=30)
            if response.status_code == 200:
                return
        except httpx.RequestError:
            pass
    pytest.fail('Retain journal: Storage cleanup failed',pytrace=False)


@pytest.fixture(scope='module')
def rag_run(live_run, settings):
    if os.getenv('SHIELDRAG_RAG') != '1':
        pytest.skip('Set SHIELDRAG_RAG=1 to authorize synthetic external Gemini processing and cost')
    if not settings.gemini_api_key.get_secret_value() or not settings.supabase_secret_key.get_secret_value():
        pytest.fail('Private Gemini and Supabase server keys are required', pytrace=False)
    marker = 'shieldrag-rag-' + live_run.manifest['run_id'] + '-'
    live_run.rag_marker = marker
    users = {a['id'] for a in live_run.manifest['accounts'].values()}
    journal = Path(os.environ['SHIELDRAG_FIXTURE_MANIFEST']).parent / 'rag-journal.json'
    journal.write_text(json.dumps({'marker': marker, 'users': sorted(users)}), encoding='utf-8')
    headers = {'apikey': settings.supabase_secret_key.get_secret_value()}
    try:
        yield live_run
    finally:
        response = live_run.upstream.get('/rest/v1/documents', headers=headers, params={
            'uploaded_by': 'in.(' + ','.join(sorted(users)) + ')',
            'original_name': 'like.' + marker + '*', 'select': 'id,uploaded_by,original_name,storage_path'})
        assert response.status_code == 200, 'Retain journal: fixture inspection failed'
        for document in response.json():
            key, doc_id = document['storage_path'], str(UUID(document['id']))
            extension = key.rsplit('.', 1)[-1]
            assert document['uploaded_by'] in users and document['original_name'].startswith(marker)
            assert key == object_key(UUID(document['uploaded_by']), UUID(doc_id), extension)
            audit = live_run.upstream.get('/rest/v1/security_events', headers=headers,
                params={'document_id': 'eq.' + doc_id, 'select': 'user_id,event_type'})
            assert audit.status_code == 200
            assert all(e['user_id'] in users and e['event_type'] in {
                'document_uploaded','document_approved','document_rejected','document_integrity_failure',
                'document_index_started','document_indexed','document_index_failed'} for e in audit.json())
            remove_object(live_run,headers,key)
            for table in ('document_chunks','security_events','documents'):
                deleted = live_run.upstream.delete('/rest/v1/' + table, headers=headers,
                    params={'id' if table == 'documents' else 'document_id': 'eq.' + doc_id})
                assert deleted.status_code in (200,204), 'Retain journal: database cleanup failed'
            remaining = live_run.upstream.get('/rest/v1/documents',headers=headers,
                params={'id':'eq.' + doc_id,'select':'id'})
            assert remaining.status_code == 200 and remaining.json() == []
        journal.unlink()


def upload(run, suffix, text, visibility='public', extension='txt'):
    data = text_pdf((text,)) if extension == 'pdf' else text.encode()
    response = run.api.post('/api/v1/documents',headers=run.headers('admin'),
        data={'visibility':visibility},files={'file':(run.rag_marker + suffix + '.' + extension,
            data,'application/pdf' if extension=='pdf' else 'text/plain')})
    assert response.status_code == 201
    return response.json()


@pytest.mark.parametrize('visibility,extension,name,value', [
    ('public','txt','Orion','violet lantern'),
    ('restricted','txt','Cassiopeia','copper meadow'),
    ('public','pdf','Pegasus','silver orchard')])
def test_live_full_index_vector_search_answer_and_idempotence(rag_run,settings,visibility,extension,name,value):
    text = f'The synthetic {name} archive access phrase is {value}. This is a fictional test fact.'
    document = upload(rag_run,name,text,visibility,extension)
    doc_id = document['id']
    path = '/api/v1/documents/' + doc_id
    assert rag_run.api.post(path+'/index',headers=rag_run.headers('student'),json=CONSENT).status_code == 403
    assert rag_run.api.post(path+'/index',headers=rag_run.headers('admin'),json=CONSENT).status_code == 409
    assert rag_run.api.post(path+'/approve',headers=rag_run.headers('admin'),json={}).status_code == 200
    assert rag_run.api.post(path+'/index',headers=rag_run.headers('admin'),json={}).status_code == 422
    response = rag_run.api.post(path+'/index',headers=rag_run.headers('admin'),json=CONSENT)
    assert response.status_code == 200, 'Real Gemini indexing failed; upstream diagnostics deliberately redacted'
    assert response.json()['chunk_count'] == 1 and response.json()['dimensions'] == 768
    chunks = rag_run.upstream.get('/rest/v1/document_chunks',headers=rag_run.headers('admin'),
        params={'document_id':'eq.'+doc_id,'select':'id,embedding,content,page_number'})
    assert chunks.status_code == 200 and len(chunks.json()) == 1
    chunk = chunks.json()[0]
    vector = json.loads(chunk['embedding'])
    assert len(vector) == 768 and abs(math.hypot(*vector)-1) < .0001
    assert chunk['page_number'] == (1 if extension=='pdf' else None)
    duplicate = rag_run.api.post(path+'/index',headers=rag_run.headers('admin'),json=CONSENT)
    assert duplicate.status_code == 200 and duplicate.json()['cached'] is True
    current = rag_run.upstream.get('/rest/v1/document_chunks',headers=rag_run.headers('admin'),
        params={'document_id':'eq.'+doc_id,'select':'id'})
    assert current.json() == [{'id':chunk['id']}]
    question = {'question':f'What is the access phrase for the synthetic {name} archive?', 'top_k':5}
    for role in ('student','admin'):
        response = rag_run.api.post('/api/v1/rag/search',headers=rag_run.headers(role),json=question)
        assert response.status_code == 200
        ids = {m['document_id'] for m in response.json()['matches']}
        assert (doc_id in ids) == (visibility=='public' or role=='admin')
        direct = rag_run.upstream.post('/rest/v1/rpc/match_shield_chunks',headers=rag_run.headers(role),
            json={'query_embedding':vector,'match_count':20})
        assert direct.status_code == 200
        assert (doc_id in {m['document_id'] for m in direct.json()}) == (visibility=='public' or role=='admin')
    role = 'admin' if visibility=='restricted' else 'student'
    answer = rag_run.api.post('/api/v1/rag/ask',headers=rag_run.headers(role),json=question)
    assert answer.status_code == 200
    result = answer.json()
    assert result['supported'] and value in result['answer'].lower()
    citation = next(c for c in result['citations'] if c['document_id']==doc_id)
    assert citation['chunk_id'] == chunk['id'] and citation['quote'] in chunk['content']
    assert citation['page'] == chunk['page_number']


def test_live_integrity_denial_and_failed_state(rag_run,settings):
    document = upload(rag_run,'tamper','Synthetic untampered text.')
    path = '/api/v1/documents/' + document['id']
    assert rag_run.api.post(path+'/approve',headers=rag_run.headers('admin'),json={}).status_code == 200
    key = object_key(UUID(document['uploaded_by']),UUID(document['id']),'txt')
    headers = {'apikey':settings.supabase_secret_key.get_secret_value()}
    modified = rag_run.upstream.put('/storage/v1/object/'+BUCKET+'/'+key,
        headers={**headers,'Content-Type':'text/plain'},content=b'Synthetic modified text.')
    assert modified.status_code == 200
    assert rag_run.api.post(path+'/index',headers=rag_run.headers('admin'),json=CONSENT).status_code == 409
    metadata = rag_run.api.get(path,headers=rag_run.headers('admin')).json()
    assert metadata['index_status']=='failed' and metadata['review_status']=='approved'
    events = rag_run.upstream.get('/rest/v1/security_events',headers=rag_run.headers('admin'),
        params={'document_id':'eq.'+document['id'],'event_type':'eq.document_integrity_failure','select':'id'})
    assert events.status_code==200 and len(events.json())==1
    chunks = rag_run.upstream.get('/rest/v1/document_chunks',headers=headers,
        params={'document_id':'eq.'+document['id'],'select':'id'})
    assert chunks.json()==[]


def test_live_no_result_and_unsupported_context_abstain(rag_run,settings):
    # A separate strict-threshold application verifies the real empty retrieval path.
    strict = settings.model_copy(update={'rag_similarity_threshold':1.0})
    with TestClient(create_app(strict)) as client:
        result = client.post('/api/v1/rag/ask',headers=rag_run.headers('student'),
            json={'question':'What is the invented ocean temperature on planet ZQX-924?', 'top_k':1})
        assert result.status_code==200 and result.json()['supported'] is False
        assert result.json()['citations']==[]
    # Existing archive excerpts do not establish this fact, even with normal retrieval.
    result = rag_run.api.post('/api/v1/rag/ask',headers=rag_run.headers('student'),
        json={'question':'What is the annual operating budget in dollars for the synthetic Orion archive?'})
    assert result.status_code==200 and result.json()['supported'] is False
    assert result.json()['citations']==[]


def test_live_processing_lease_and_service_rpc_denial(rag_run,settings):
    document = upload(rag_run,'lease','Synthetic lease fixture.')
    path = '/api/v1/documents/'+document['id']
    assert rag_run.api.post(path+'/approve',headers=rag_run.headers('admin'),json={}).status_code==200
    job = str(uuid4())
    body = {'p_actor':rag_run.manifest['accounts']['admin']['id'],'p_id':document['id'],'p_job':job,
        'p_sha256':document['sha256'],'p_model':settings.gemini_embedding_model,
        'p_config_hash':'b'*64,'p_external_authorized':True}
    for role in ('student','admin'):
        denied = rag_run.upstream.post('/rest/v1/rpc/shield_begin_index',headers=rag_run.headers(role),json=body)
        assert denied.status_code in (401,403,404)
    headers = {'apikey':settings.supabase_secret_key.get_secret_value()}
    assert rag_run.upstream.post('/rest/v1/rpc/shield_begin_index',headers=headers,json=body).status_code==200
    assert rag_run.api.post(path+'/index',headers=rag_run.headers('admin'),json=CONSENT).status_code==409
    failed = rag_run.upstream.post('/rest/v1/rpc/shield_fail_index',headers=headers,
        json={'p_actor':body['p_actor'],'p_id':body['p_id'],'p_job':job})
    assert failed.status_code==200 and failed.json()[0]['index_status']=='failed'
