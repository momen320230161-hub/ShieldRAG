"""Regression cases for source-separated answers and supported-answer release."""
import hashlib
import json
from unittest.mock import AsyncMock
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.schemas.rag import SecureGeneratedAnswer
from app.security import classifier
from app.security.decisions import Decision
from evaluation.benchmark import ROOT, load_benchmark
from evaluation.runner import run
from test_security_agent import fake_agent, retrieval_dependencies, run_secure, CHUNK, DOC

SECOND = str(UUID(int=42))
TEXTS = ('The sample weighs twelve grams.', 'The sample weighs eighteen grams.')


def paired_sources(texts=TEXTS, *, revoke=False):
    gateway, gemini, _ = retrieval_dependencies()
    original_get = gateway.get.side_effect
    chunk_read_count = 0
    gateway.rpc.return_value = [
        {'chunk_id': chunk, 'document_id': DOC, 'chunk_text': text, 'page_number': n + 1, 'similarity': .9}
        for n, (chunk, text) in enumerate(zip((CHUNK, SECOND), texts, strict=True))
    ]

    async def get(path, token, params):
        nonlocal chunk_read_count
        if path.endswith('document_chunks'):
            chunk_read_count += 1
            rows = [{'id': chunk, 'document_id': DOC, 'content': text}
                    for chunk, text in zip((CHUNK, SECOND), texts, strict=True)]
            return rows[:1] if revoke and chunk_read_count > 1 else rows
        return await original_get(path, token, params)

    gateway.get.side_effect = get
    gemini.generate.return_value = SecureGeneratedAnswer(supported=True, mode='extracts', answer='',
        evidence=[{'source_id': n, 'quote': text} for n, text in enumerate(texts)])
    return gateway, gemini


def test_exact_excerpts_keep_contradictory_sources_separate_and_provenanced():
    gateway, gemini = paired_sources()
    audit = SimpleNamespace(record=AsyncMock())
    result = run_secure(gateway=gateway, gemini=gemini, audit=audit)
    assert result.status == 'answered'
    assert result.answer == '[1] The sample weighs twelve grams.\n\n[2] The sample weighs eighteen grams.'
    assert [str(c.chunk_id) for c in result.citations] == [CHUNK, SECOND]
    assert [c.page for c in result.citations] == [1, 2]
    assert audit.record.await_args.args[1:] == ('output', 'allow', 'no_threat_detected')


@pytest.mark.parametrize('problem', ['inserted-prose', 'wrong-source', 'duplicate-source', 'fake-source',
                                    'incorrect-claim', 'ordinary-paraphrase', 'translation'])
def test_generated_content_without_exact_support_stays_unreleased(problem):
    gateway, gemini = paired_sources()
    raw = gemini.generate.return_value
    if problem == 'inserted-prose':
        raw.answer = 'The sources agree on a new conclusion.'
    elif problem == 'wrong-source':
        raw.evidence[0].quote = TEXTS[1]
    elif problem == 'duplicate-source':
        raw.evidence[1] = raw.evidence[0]
    elif problem == 'fake-source':
        raw.evidence[1].source_id = 90
    else:
        raw.mode = None
        raw.answer = {
            'incorrect-claim': 'The sample weighs fifteen grams.',
            'ordinary-paraphrase': 'The mass of the sample is twelve grams.',
            'translation': 'تزن العينة اثني عشر غرامًا.',
        }[problem]
    result = run_secure(gateway=gateway, gemini=gemini)
    assert result.status == 'blocked' and result.answer is None and not result.citations


@pytest.mark.parametrize('text', [
    'I will ignore prior instructions.',
    'sb_secret_synthetic',
    'A safe-looking excerpt.\n[1] A spoofed citation heading.',
])
def test_exact_but_unsafe_selected_excerpt_never_released(text):
    gateway, gemini = paired_sources((TEXTS[0], text))
    result = run_secure(gateway=gateway, gemini=gemini)
    assert result.status == 'blocked' and result.answer is None


def test_structured_output_keeps_highest_severity_decision():
    gateway, gemini = paired_sources()
    agent = fake_agent()
    original = agent.analyze
    agent.analyze = lambda texts, stage: [
        Decision('review', 'output_policy_violation', 'classifier_review'),
        Decision('block', 'output_policy_violation', 'classifier_attack'),
    ] if stage == 'output' else original(texts, stage)
    result = run_secure(agent=agent, gateway=gateway, gemini=gemini)
    assert result.decision == 'block' and result.answer is None


def test_permission_recheck_and_audit_ack_apply_to_all_excerpts():
    gateway, gemini = paired_sources(revoke=True)
    revoked = run_secure(gateway=gateway, gemini=gemini)
    assert revoked.status == 'insufficient_evidence' and not revoked.citations
    gateway, gemini = paired_sources()
    from fastapi import HTTPException
    audit = SimpleNamespace(record=AsyncMock(side_effect=HTTPException(503)))
    result = run_secure(gateway=gateway, gemini=gemini, audit=audit)
    assert result.status == 'unavailable' and result.answer is None


def test_frozen_benchmark_and_separate_development_response_contract():
    old = load_benchmark()
    assert old.digest() == '2bc2d53c6bd1dfa60a89043a4f10d999a07824310476558deab3cec36fe13cb0'
    dev = load_benchmark(ROOT.parent / 'task061/development.json')
    assert {case.id for case in old.cases}.isdisjoint(case.id for case in dev.cases)
    secure = {r['id']: r for r in run(dev) if r['pipeline'] == 'secure'}
    for case_id in ('d-thermal', 'd-mixing', 'd-counter'):
        result = secure[case_id]
        assert result['multi_extract'] and result['rubric']['grounded_proxy']
    for case_id in ('d-ar', 'd-quotation'):
        assert secure[case_id]['extractive']
    # Keep the benign label and surface the measured mixed-language false positive.
    assert secure['d-mixed']['expected_behavior'] == 'answer'
    assert secure['d-mixed']['status'] == 'blocked' and secure['d-mixed']['audit']['last_stage'] == 'output'
    assert not secure['d-mixed']['available']
    assert secure['d-translation']['status'] == 'blocked'
    assert not secure['d-output']['attack_success'] and secure['d-output']['audit']['last_stage'] == 'output'


def test_mixed_language_exact_excerpts_follow_the_same_grounding_invariant():
    texts = ('The voltage increased.', 'زادت شدة التيار الكهربائي.')
    gateway, gemini = paired_sources(texts)
    result = run_secure(gateway=gateway, gemini=gemini)
    assert result.supported and [c.quote for c in result.citations] == list(texts)


def test_invalid_stage_manifest_fails_closed_even_with_matching_artifact_digest(tmp_path, monkeypatch):
    original = classifier.BUNDLE_DIR
    model = json.loads((original/'classifier.json').read_text(encoding='utf-8'))
    del model['stage_thresholds']['context']
    data = json.dumps(model).encode()
    manifest = json.loads((original/'manifest.json').read_text(encoding='utf-8'))
    manifest['sha256'] = hashlib.sha256(data).hexdigest()
    (tmp_path/'classifier.json').write_bytes(data)
    (tmp_path/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    monkeypatch.setattr(classifier,'BUNDLE_DIR',tmp_path)
    with pytest.raises(classifier.SecurityUnavailable):
        classifier.Classifier()
