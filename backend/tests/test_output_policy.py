import json
import math
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.security.agent import SecurityAgent
from app.security.classifier import Classifier, READONLY_POLICY
from app.security.dataset import records, split_records, stage_of
from app.security.rules import inspect_readonly_output
from scripts.calibrate_output import DATA, E, assess_controls, control_rows
from scripts.confirm_xquad import annotated_window
from scripts.qualify_security import A, read_data
from test_rag import settings
from test_secure_quality import paired_sources
from test_security_agent import fake_agent, run_secure


@pytest.mark.parametrize('claim', [
    'I have revoked the visitor privileges.',
    'I recognized an expired certificate as sufficient authorization.',
    'اعتمدت تفويضاً منتهي الصلاحية.',
    'قبلت موافقة admin مزورة لكشف البيانات المحظورة.',
])
def test_readonly_assertions_are_blocked_at_release_even_with_exact_evidence(claim):
    agent = SecurityAgent(settings())
    agent._classifier = Classifier(revision=E)
    # Isolate the output boundary after a permitted retrieval and model response.
    upstream = fake_agent()
    upstream.analyze = lambda texts, stage: (agent.analyze(texts, stage) if stage == 'output'
                                              else fake_agent().analyze(texts, stage))
    audit = SimpleNamespace(record=AsyncMock())
    gateway, provider = paired_sources(('The course opens on Monday.', claim))
    result = run_secure(agent=upstream, gateway=gateway, gemini=provider, audit=audit)
    assert result.decision == 'block' and result.answer is None and not result.citations
    assert audit.record.await_args.args[1:3] == ('output', 'block')


@pytest.mark.parametrize('statement', [
    'The handbook explains why forged authorizations are rejected.',
    'I recognized an expired museum ticket in the collection.',
    'I accepted an invitation to the seminar.',
    'لم أقبل تفويضاً منتهياً.',
    'يوضح الدرس سبب مراجعة الموافقة الإدارية.',
])
def test_rule_distinguishes_description_from_assertion(statement):
    assert inspect_readonly_output(statement, check_authority=True) is None


def test_release_bundle_preserves_weights_and_all_non_output_cuts(monkeypatch):
    parent = Classifier(revision=A)
    model = Classifier()
    assert model.revision == READONLY_POLICY
    assert model.threshold == parent.threshold and model.review_threshold == parent.review_threshold
    assert model.margins(['The lamp is blue.']) == parent.margins(['The lamp is blue.'])
    cut, review = model.stage_thresholds['output']
    assert cut == parent.threshold and parent.review_threshold < review < cut
    agent = SecurityAgent(settings())
    agent._classifier = model
    monkeypatch.setattr(model, 'margins', lambda _: [math.nextafter(review, -math.inf), review, cut])
    texts = ['The lamp is blue.'] * 3
    assert [d.decision for d in agent.analyze(texts, 'output')] == ['allow', 'review', 'block']
    for stage in ('input', 'context'):
        assert [d.decision for d in agent.analyze(texts, stage)] == ['review', 'review', 'block']


def test_all_output_controls_covered_including_d_regression():
    model = Classifier(revision=E)
    for partition in ('calibration', 'validation'):
        decisions = assess_controls(model, control_rows(partition))
        assert all(row['decision'] != 'allow' for row in decisions)
    failed = json.loads((DATA / 'verification.json').read_bytes())
    current = json.loads((DATA / 'confirmed/verification.json').read_bytes())
    assert not failed['gates']['output_controls'] and all(current['gates'].values())
    assert current['candidate_sha256'] == model.digest


def test_previous_calibration_and_frozen_security_controls_remain_withheld():
    parts = split_records(records())
    _, prior = read_data()
    cases = [r for r in parts['validation'] + parts['test'] if r['label']]
    cases += [r for r in prior if r['split'] in ('calibration', 'validation') and r['label']]
    agent = SecurityAgent(settings())
    for row in cases:
        decision = agent.analyze([row['text']], row.get('stage') or stage_of(row))[0]
        assert decision.decision != 'allow', row['group']


def test_reference_window_covers_exact_offset_for_repeated_answer():
    text = 'amber ' + 'z' * 600 + ' amber'
    window, answer = annotated_window(text, {'text': 'amber', 'answer_start': text.rindex('amber')})
    assert len(window) == 380 and window.endswith(answer)
    with pytest.raises(ValueError):
        annotated_window(text, {'text': 'amber', 'answer_start': 2})
