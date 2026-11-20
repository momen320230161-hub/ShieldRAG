"""One explicitly invoked, bounded Task 06.3 pilot. Never collected by the normal pytest suite."""
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from time import perf_counter

import pytest

from app.services import rag, secure_rag
from evaluation.benchmark import ROOT, load_benchmark
from test_integration import live_run, settings
from test_integration import test_fixture_password_login_jwt_and_trusted_role as check_role
from test_integration import test_fixture_direct_postgrest_documents_and_chunks as check_scope
from test_integration import test_fixture_vector_rpc_has_positive_and_negative_assertions as check_rpc
from test_rag_integration import rag_run, upload

CASES = ('d-thermal', 'd-mixing', 'd-ar', 'd-mixed', 'd-translation', 'b-admin', 'a-restricted-record')
LIMIT = {'RETRIEVAL_DOCUMENT': 8, 'RETRIEVAL_QUERY': 14, 'generation': 14, 'attempts': 108}
pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    not os.getenv('SHIELDRAG_TASK063'), reason='Requires explicit Task 06.3 pilot authorization')]
EVENTS = {'security_agent_allowed', 'security_agent_blocked', 'security_agent_error',
          'prompt_injection_detected', 'indirect_injection_detected'}


def test_task063(rag_run, settings, monkeypatch):
    run = rag_run
    assert os.environ.get('SHIELDRAG_TASK063') == run.manifest['run_id']
    folder = Path(os.environ['SHIELDRAG_FIXTURE_MANIFEST']).parent
    journal = folder / 'owned.json'
    # An exclusive marker prevents re-running billable requests under this manifest.
    (folder / 'started').touch(exist_ok=False)
    auth = {'apikey': settings.supabase_secret_key.get_secret_value()}
    owned = {'documents': {}, 'events': []}
    rows = []
    counts = Counter()
    attempts = Counter()
    result = {'cases': rows, 'usage': counts, 'attempts_by_operation': attempts, 'indexed_sources': []}
    api = run.api
    state = api.app.state
    assert state.security_agent._model().digest == 'fa68f0c166edf201a0a80412f53bb10ef5c863f05f6306d9d1e81d4e29c3887e'
    suites = [load_benchmark(), load_benchmark(ROOT.parent / 'task061/development.json')]
    cases = {c.id: c for suite in suites for c in suite.cases if c.id in CASES}
    fixtures = {f.id: f for suite in suites for f in suite.fixtures if any(f.id in c.sources for c in cases.values())}
    assert len(fixtures) == 8 and len(cases) == 7
    texts = {f.text for f in fixtures.values()}
    questions = {c.question for c in cases.values()}
    actor_ids = [a['id'] for a in run.manifest['accounts'].values()]
    operation = None
    role = None
    timings = Counter()
    audit_args = []

    def save():
        journal.write_text(json.dumps(owned), encoding='utf-8')
        (folder/'observations.json').write_text(json.dumps(result), encoding='utf-8')

    def take(key):
        assert counts[key] < LIMIT[key], 'Pilot budget reached'
        counts[key] += 1

    def read(path, params, headers=auth):
        response = run.upstream.get('/rest/v1/'+path, headers=headers, params=params)
        assert response.status_code == 200
        return response.json()

    def events():
        return read('security_events', {'user_id': 'in.('+','.join(actor_ids)+')',
                    'select': 'id,user_id,document_id,event_type,decision,reason'})

    def timed(target, name, phase):
        original = getattr(target, name)
        async def observe(*args, **kwargs):
            start = perf_counter()
            try:
                return await original(*args, **kwargs)
            finally:
                timings[phase] += round((perf_counter()-start)*1000, 2)
        monkeypatch.setattr(target, name, observe)

    embed, generate, call = state.gemini.embed, state.gemini.generate, state.gemini._call
    async def embedding(values, task):
        nonlocal operation
        assert len(values) == 1 and values[0] in (texts if task == 'RETRIEVAL_DOCUMENT' else questions)
        take(task)
        operation = task
        return await embed(values, task)

    async def generation(question, sources, **kwargs):
        nonlocal operation
        permitted = {run.rag_marker+k+'.txt': fixtures[k].text for k in owned['documents']
                     if role == 'admin' or fixtures[k].visibility == 'public'}
        assert question in questions and all(permitted.get(s['document_name']) == s['text'] for s in sources)
        take('generation')
        operation = 'generation'
        return await generate(question, sources, **kwargs)

    async def bounded(fn):
        n = 0
        async def attempt():
            nonlocal n
            assert n < 3
            take('attempts')
            n += 1
            attempts[operation] += 1
            if n > 1:
                counts['retries'] += 1
            try:
                return await fn()
            except Exception:
                counts['provider_errors'] += 1
                raise
        return await call(attempt)

    monkeypatch.setattr(state.gemini, 'embed', embedding)
    monkeypatch.setattr(state.gemini, 'generate', generation)
    monkeypatch.setattr(state.gemini, '_call', bounded)
    timed(state.gemini, 'generate', 'generation')
    timed(rag, 'search', 'retrieval')
    timed(secure_rag, 'search', 'retrieval')
    analyze = state.security_agent.analyze
    def screened(values, stage):
        start = perf_counter()
        try:
            return analyze(values, stage)
        finally:
            timings[stage+'_screen'] += round((perf_counter()-start)*1000, 2)
    monkeypatch.setattr(state.security_agent, 'analyze', screened)
    record = state.security_store.record
    async def audit(principal, stage, decision, reason, document_id=None):
        await record(principal, stage, decision, reason, document_id)
        audit_args.append((stage, decision, reason))
    monkeypatch.setattr(state.security_store, 'record', audit)
    timed(state.security_store, 'record', 'audit')
    try:
        assert api.get('/api/v1/me',headers={'Authorization':'Bearer invalid'}).status_code == 401
        for role_name in ('student','admin'):
            check_role(run, role_name)
            check_scope(run, role_name)
            check_rpc(run, role_name)
        result['auth_and_seed_rls'] = True
        for key, f in fixtures.items():
            doc = upload(run,key,f.text,visibility=f.visibility)
            doc_id = doc['id']
            path = '/api/v1/documents/'+doc_id
            meta = read('documents', {'id':'eq.'+doc_id,'select':'storage_path,sha256,uploaded_by'})[0]
            assert meta['sha256'] == hashlib.sha256(f.text.encode()).hexdigest()
            owned['documents'][key] = {'id':doc_id, **meta}
            save()
            assert api.post(path+'/approve',headers=run.headers('admin'),json={}).status_code == 200
            try:
                indexed = api.post(path+'/index',headers=run.headers('admin'),json={'external_processing_authorized':True})
            except OSError as exc:
                result['setup_error'] = {'step': 'index', 'fixture': key,
                                         'exception_type': type(exc).__name__,
                                         'platform_error': getattr(exc, 'winerror', None)}
                raise
            if indexed.status_code != 200:
                result['setup_error'] = {'step':'index','fixture':key,'http':indexed.status_code}
                raise AssertionError('Index unavailable')
            assert indexed.json()['chunk_count'] == 1
            chunks = read('document_chunks',{'document_id':'eq.'+doc_id,'select':'id,content,page_number'})
            assert len(chunks)==1 and chunks[0]['content']==f.text and chunks[0]['page_number'] is None
            current = read('documents',{'id':'eq.'+doc_id,'select':'index_status,indexed_sha256'})[0]
            assert current == {'index_status':'indexed','indexed_sha256':meta['sha256']}
            owned['documents'][key]['chunk_id'] = chunks[0]['id']
            result['indexed_sources'].append(key)
            save()
        for role_name in ('student','admin'):
            visible = read('document_chunks',{'select':'id'},run.headers(role_name))
            ids = {r['id'] for r in visible}
            assert all((d['chunk_id'] in ids) == (fixtures[k].visibility=='public' or role_name=='admin')
                       for k,d in owned['documents'].items())
        result['indexed_role_isolation'] = True
        for i, key in enumerate(CASES):
            case = cases[key]
            role = case.role
            for route in (('ask','secure-ask') if i%2==0 else ('secure-ask','ask')):
                before = {e['id'] for e in events()}
                timings.clear()
                audit_args.clear()
                start = perf_counter()
                response = api.post('/api/v1/rag/'+route,headers=run.headers(role),json={'question':case.question,'top_k':5})
                row = {'case':key,'route':route,'role':role,'http':response.status_code,
                       'ms':round((perf_counter()-start)*1000,2),'phase_ms':dict(timings)}
                rows.append(row)
                save()
                if response.status_code != 200:
                    continue
                body = response.json()
                citations = body['citations']
                answer = body.get('answer') or ''
                targets = []
                for c in citations:
                    target = next(k for k,d in owned['documents'].items() if d['chunk_id']==c['chunk_id'])
                    d = owned['documents'][target]
                    assert c['document_id']==d['id'] and c['document_name']==run.rag_marker+target+'.txt'
                    assert c['page'] is None and c['quote'] and c['quote'] in fixtures[target].text
                    assert role=='admin' or fixtures[target].visibility=='public'
                    targets.append(target)
                if role=='student':
                    assert 'EVAL06_RESTRICTED_GARNET' not in json.dumps(body)
                multi = len(citations)>=2 and answer=='\n\n'.join(f"[{j}] {c['quote']}" for j,c in enumerate(citations,1))
                row.update(status=body.get('status','answered' if body['supported'] else 'insufficient_evidence'),
                           supported=body['supported'],decision=body.get('decision'),citation_count=len(citations),
                           cited_fixtures=targets, all_expected_sources=(
                               set(case.expected_evidence) <= set(targets) if case.expected_evidence else None),
                           multi_excerpt=multi, all_expected_facts=all(any(v.casefold() in answer.casefold()
                           for v in variants) for variants in case.facts) if case.facts else None)
                if route=='secure-ask':
                    if body['supported']:
                        assert multi or any(answer in c['quote'] for c in citations)
                    delta = [e for e in events() if e['id'] not in before]
                    assert len(audit_args)==len(delta)==1
                    stage, decision, reason = audit_args[0]
                    e = delta[0]
                    assert e['user_id']==run.manifest['accounts'][role]['id'] and e['reason']==reason+';policy=shield-security-v1'
                    assert e['decision'] == ('deny' if decision == 'block' else decision)
                    assert body['decision'] == ('review' if body['status'] == 'unavailable' else decision)
                    expected_type = ('security_agent_allowed' if decision=='allow' else
                                     {'input':'prompt_injection_detected','context':'indirect_injection_detected',
                                      'output':'security_agent_blocked','error':'security_agent_error'}[stage])
                    assert e['event_type']==expected_type
                    row.update(audit_verified=True,audit_stage=stage,audit_reason=reason)
                save()
        assert len(rows) == 14 and all(row['http'] == 200 for row in rows)
        assert all(row.get('audit_verified') for row in rows if row['route'] == 'secure-ask')
    finally:
        inventory = events()
        owned['events'] = [e['id'] for e in inventory]
        save()
        for e in inventory:
            if e['event_type'] in EVENTS:
                assert e['user_id'] in actor_ids
                assert e['document_id'] is None or e['document_id'] in [d['id'] for d in owned['documents'].values()]
                deleted = run.upstream.delete('/rest/v1/security_events',headers=auth,params={'id':'eq.'+e['id'],'user_id':'eq.'+e['user_id']})
                assert deleted.status_code in (200,204)
        # rag_run removes exact owned objects/documents; live_run revokes the two sessions.
