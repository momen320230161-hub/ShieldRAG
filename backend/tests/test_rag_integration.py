"""Opt-in, billable Gemini + real Supabase RAG acceptance; synthetic data only."""
import json
import math
import os
from pathlib import Path
from uuid import UUID, uuid4
from unittest.mock import AsyncMock

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
    data = text_pdf(text if isinstance(text,tuple) else (text,)) if extension == 'pdf' else text.encode()
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


class FixtureTransport(httpx.AsyncBaseTransport):
    """Forward genuine HTTP, injecting a bounded failure or authorized result subset."""
    def __init__(self, mode, document, page=None):
        self.inner=httpx.AsyncHTTPTransport(trust_env=False,retries=0)
        self.mode,self.document,self.page,self.dropped=mode,document,page,False

    async def handle_async_request(self,request):
        key=object_key(UUID(self.document['uploaded_by']),UUID(self.document['id']),
                       'pdf' if self.page is not None else 'txt')
        if request.url.path=='/storage/v1/object/authenticated/'+BUCKET+'/'+key:
            if self.mode=='storage_503':
                return httpx.Response(503,json={'error':'Synthetic infrastructure outage'})
            if self.mode=='storage_timeout':
                raise httpx.ReadTimeout('Synthetic Storage timeout',request=request)
        response=await self.inner.handle_async_request(request)
        target={'lost_begin':'shield_begin_index','lost_invalidation':'shield_invalidate_index'}.get(self.mode)
        if target and request.url.path.endswith('/rpc/'+target) and response.status_code==200 and not self.dropped:
            await response.aread()
            await response.aclose()
            self.dropped=True
            raise httpx.ReadTimeout('Synthetic lost successful acknowledgement',request=request)
        if self.page is not None and request.url.path.endswith('/rpc/match_shield_chunks') and response.status_code==200:
            await response.aread()
            rows=[r for r in response.json() if r['document_id']==self.document['id'] and r['page_number']==self.page]
            await response.aclose()
            return httpx.Response(200,json=rows)
        return response

    async def aclose(self):
        await self.inner.aclose()


def approved_index(run,suffix,text):
    doc=upload(run,suffix,text)
    path='/api/v1/documents/'+doc['id']
    assert run.api.post(path+'/approve',headers=run.headers('admin'),json={}).status_code==200
    assert run.api.post(path+'/index',headers=run.headers('admin'),json=CONSENT).status_code==200
    return doc,path


def saved_chunks(run,doc_id,headers):
    response=run.upstream.get('/rest/v1/document_chunks',headers=headers,
        params={'document_id':'eq.'+doc_id,'select':'id,content,page_number','order':'chunk_index'})
    assert response.status_code==200
    return response.json()


@pytest.mark.parametrize('mode',['storage_503','storage_timeout','lost_begin'])
def test_live_cached_transient_fault_preserves_completed_revision(rag_run,settings,mode):
    doc,path=approved_index(rag_run,mode,'The synthetic cached archive opens at eleven.')
    headers={'apikey':settings.supabase_secret_key.get_secret_value()}
    before=saved_chunks(rag_run,doc['id'],headers)
    metadata=rag_run.upstream.get('/rest/v1/documents',headers=headers,
        params={'id':'eq.'+doc['id'],'select':'*'}).json()
    with TestClient(create_app(settings,FixtureTransport(mode,doc))) as api:
        api.app.state.gemini.embed=AsyncMock(side_effect=RuntimeError('Synthetic Gemini outage'))
        response=api.post(path+'/index',headers=rag_run.headers('admin'),json=CONSENT)
        assert response.status_code==503
        api.app.state.gemini.embed.assert_not_called()
    after=rag_run.upstream.get('/rest/v1/documents',headers=headers,
        params={'id':'eq.'+doc['id'],'select':'*'}).json()
    assert after==metadata and after[0]['index_operation_id'] is None
    assert saved_chunks(rag_run,doc['id'],headers)==before
    assert saved_chunks(rag_run,doc['id'],rag_run.headers('student'))==before
    # Ordinary cached verification also succeeds while Gemini is unavailable.
    with TestClient(create_app(settings)) as api:
        api.app.state.gemini.embed=AsyncMock(side_effect=RuntimeError('Synthetic Gemini outage'))
        assert api.post(path+'/index',headers=rag_run.headers('admin'),json=CONSENT).json()['cached']
        api.app.state.gemini.embed.assert_not_called()
    assert saved_chunks(rag_run,doc['id'],headers)==before


@pytest.mark.parametrize('failure',['sha256_mismatch','stored_object_missing'])
def test_live_cached_confirmed_failure_revokes_retrieval_without_deleting_chunks(rag_run,settings,failure):
    doc,path=approved_index(rag_run,'cached-'+failure,'The synthetic cached integrity fact is amber.')
    headers={'apikey':settings.supabase_secret_key.get_secret_value()}
    before=saved_chunks(rag_run,doc['id'],headers)
    key=object_key(UUID(doc['uploaded_by']),UUID(doc['id']),'txt')
    if failure=='sha256_mismatch':
        response=rag_run.upstream.put('/storage/v1/object/'+BUCKET+'/'+key,
            headers={**headers,'Content-Type':'text/plain'},content=b'Synthetic tampered original.')
        assert response.status_code==200
    else:
        remove_object(rag_run,headers,key)
    # The DB commit is genuine; one successful acknowledgement is deliberately lost.
    transport=FixtureTransport('lost_invalidation',doc)
    with TestClient(create_app(settings,transport)) as api:
        denied=api.post(path+'/index',headers=rag_run.headers('admin'),json=CONSENT)
        assert denied.status_code==409 and transport.dropped
    assert saved_chunks(rag_run,doc['id'],headers)==before
    assert rag_run.api.get(path,headers=rag_run.headers('admin')).json()['index_status']=='failed'
    reason='SHA-256 mismatch detected' if failure=='sha256_mismatch' else 'Stored object is missing'
    audit=rag_run.upstream.get('/rest/v1/security_events',headers=headers,
        params={'document_id':'eq.'+doc['id'],'event_type':'eq.document_integrity_failure','select':'reason'})
    assert audit.status_code==200 and audit.json()==[{'reason':reason}]
    for role in ('student','admin'):
        assert saved_chunks(rag_run,doc['id'],rag_run.headers(role))==[]
    # Direct vector RPC must also exclude the retained but invalidated chunks.
    vector=rag_run.upstream.get('/rest/v1/document_chunks',headers=headers,
        params={'document_id':'eq.'+doc['id'],'select':'embedding'}).json()[0]['embedding']
    for role in ('student','admin'):
        matches=rag_run.upstream.post('/rest/v1/rpc/match_shield_chunks',headers=rag_run.headers(role),
            json={'query_embedding':json.loads(vector),'match_count':20})
        assert matches.status_code==200 and doc['id'] not in {r['document_id'] for r in matches.json()}


def test_live_identical_pdf_pages_retrieve_and_cite_each_occurrence(rag_run,settings):
    fact='The synthetic repeated-page archive code is emerald harbor.'
    doc=upload(rag_run,'repeated-pages',('',fact,'','','','','',fact),extension='pdf')
    path='/api/v1/documents/'+doc['id']
    assert rag_run.api.post(path+'/approve',headers=rag_run.headers('admin'),json={}).status_code==200
    indexed=rag_run.api.post(path+'/index',headers=rag_run.headers('admin'),json=CONSENT)
    assert indexed.status_code==200 and indexed.json()['chunk_count']==2
    chunks=saved_chunks(rag_run,doc['id'],rag_run.headers('student'))
    assert [r['page_number'] for r in chunks]==[2,8] and chunks[0]['content']==chunks[1]['content']
    question={'question':'What is the code of the synthetic repeated-page archive?','top_k':10}
    found=rag_run.api.post('/api/v1/rag/search',headers=rag_run.headers('student'),json=question)
    assert found.status_code==200
    assert {r['page'] for r in found.json()['matches'] if r['document_id']==doc['id']}=={2,8}
    for page in (2,8):
        # Select one page from actual JWT-authorized RPC rows, avoiding nondeterministic
        # model selection between identical excerpts. Auth, RLS and Gemini remain real.
        with TestClient(create_app(settings,FixtureTransport('authorized_page',doc,page))) as api:
            answer=api.post('/api/v1/rag/ask',headers=rag_run.headers('student'),json=question)
            assert answer.status_code==200 and answer.json()['supported']
            citation=answer.json()['citations'][0]
            expected=next(c for c in chunks if c['page_number']==page)
            assert citation['page']==page and citation['chunk_id']==expected['id']
            assert citation['quote'] in expected['content']
