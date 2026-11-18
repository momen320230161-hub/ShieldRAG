"""Release lock, model identity, and exact operating-point regression tests."""
import json
import math

import pytest

from app.security import classifier
from app.security.agent import SecurityAgent
from evaluation.benchmark import ROOT, load_benchmark
from scripts.qualify_security import A, B, C, REPORTS, benchmark, choose, read_data
from test_rag import settings


@pytest.fixture(scope='module')
def lock():
    return json.loads((REPORTS / 'selection.json').read_bytes())


@pytest.mark.parametrize('revision', [A, B, C])
@pytest.mark.parametrize('stage', ['input', 'context', 'output'])
def test_every_locked_cut_is_inclusive(revision, stage, lock, monkeypatch):
    snapshot = lock['candidates'][revision]
    model = classifier.Classifier(revision=revision)
    assert model.digest == snapshot['digest']
    block, review = snapshot['stage_cuts_block_review'].get(stage, [snapshot['block'], snapshot['review']])
    agent = SecurityAgent(settings())
    agent._classifier = model
    margins = [math.nextafter(review, -math.inf), review, math.nextafter(block, -math.inf), block]
    monkeypatch.setattr(model, 'margins', lambda texts: margins)
    actual = agent.analyze(['The marble is smooth.'] * len(margins), stage)
    assert [d.decision for d in actual] == ['allow', 'review', 'review', 'block']


def test_unknown_or_mispaired_revision_fails_closed():
    with pytest.raises(classifier.SecurityUnavailable):
        classifier.Classifier(revision='unregistered')
    with pytest.raises(classifier.SecurityUnavailable):
        classifier.Classifier(revision=C, directory=classifier.REVISIONS[A])


def test_self_consistent_manifest_cannot_replace_shipped_bundle(tmp_path, monkeypatch):
    raw = (classifier.REVISIONS[C] / 'classifier.json').read_bytes()
    manifest = json.loads((classifier.REVISIONS[C] / 'manifest.json').read_bytes())
    manifest['model_revision'] = A
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    (tmp_path / 'classifier.json').write_bytes(raw)
    monkeypatch.setattr(classifier, 'BUNDLE_DIR', tmp_path)
    with pytest.raises(classifier.SecurityUnavailable):
        classifier.Classifier()


def test_fresh_selection_and_historical_veto_are_separate(lock):
    families, _ = read_data()
    suite = benchmark(families)
    assert suite.digest() == lock['qualification_route_digest']
    assert choose(lock['candidates']) == lock['selected'] == C
    assert lock['selected_sha256'] == classifier.Classifier(revision=C).digest
    assert classifier.Classifier().revision == A
    old = json.loads((ROOT / 'reports/results.json').read_bytes())
    candidate = json.loads((REPORTS / 'historical/results.json').read_bytes())
    retained = json.loads((REPORTS / 'retained/historical/results.json').read_bytes())

    def supported(report):
        assert report['benchmark']['sha256'] == load_benchmark().digest()
        assert report['summary']['complete']
        rows = [r for r in report['cases'] if r['pipeline'] == 'secure']
        assert all(r['audit']['acknowledged'] and not r['authorization_failure']
                   and not r['unexpected_retrieval'] and not r['attack_success'] for r in rows)
        return {r['id'] for r in rows if r['label'] == 'benign' and r['supported']}

    assert supported(old) == supported(retained)
    assert len(supported(candidate)) < len(supported(old))


def test_arabic_education_compatibility_veto(lock):
    question = 'ما هو حقن التعليمات في نماذج اللغة؟'
    agent = SecurityAgent(settings())
    assert agent.analyze([question], 'input')[0].decision == 'allow'
    agent._classifier = classifier.Classifier(revision=lock['selected'])
    assert agent.analyze([question], 'input')[0].decision == 'review'
