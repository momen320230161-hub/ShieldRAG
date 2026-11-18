"""Fit one fixed candidate and lock selection on separate synthetic qualification families."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import sklearn
from pydantic import SecretStr
from scipy.sparse import hstack
from sklearn.svm import LinearSVC

from app.core.config import Settings
from app.security.agent import SecurityAgent
from app.security.classifier import Classifier, VERSION
from app.security.dataset import SEED, records, split_records, stage_of
from app.security.features import FEATURES, normalize, vectorizer
from app.security.rules import inspect_rules
from evaluation.benchmark import Benchmark, QUALIFICATION_PROVENANCE, ROOT
from evaluation.runner import run
from scripts.train_security import choose_thresholds

REPORTS = ROOT.parent / 'task062'
A = 'shield-security-calibration-1'
B = 'shield-security-calibration-2'
C = 'shield-security-calibration-3'
STAGES = ('input', 'context', 'output')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def save(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())


def read_data():
    def read(name):
        with (REPORTS / name).open(encoding='utf-8', newline='') as stream:
            return list(csv.DictReader(stream, delimiter='\t'))

    families = read('families.tsv')
    rows = []
    for item in families:
        if item['span'] not in item['context']:
            raise ValueError('Expected exact academic span')
        for stage, field in zip(STAGES, ('question', 'context', 'span'), strict=True):
            rows.append({**{k: item[k] for k in ('group', 'split', 'language')},
                         'stage': stage, 'label': 0, 'text': item[field]})
    rows.extend({**row, 'label': 1} for row in read('controls.tsv'))
    groups = {}
    for row in rows:
        if groups.setdefault(row['group'], row['split']) != row['split']:
            raise ValueError('Family crosses partitions')
    return families, rows


def check_separation(fit, calibration, validation):
    """Reject normalized duplicates and high character 4-gram Jaccard overlap across partitions."""
    def shingles(text):
        value = normalize(text)
        return {value[i:i + 4] for i in range(max(1, len(value) - 3))}

    previous = []
    maximum = 0.0
    for part in (fit, calibration, validation):
        current = [(r['group'], shingles(r['text'])) for r in part]
        for group, grams in current:
            for old_group, other in previous:
                overlap = len(grams & other) / max(len(grams | other), 1)
                maximum = max(maximum, overlap)
                if group == old_group or overlap >= .80:
                    raise ValueError(f'Cross-partition overlap: {group}, {old_group}')
        previous.extend(current)
    return maximum


def fit_bundle(fit, calibration, directory, settings):
    transforms = [vectorizer(analyzer) for analyzer, _, _ in FEATURES]
    features = hstack([t.fit_transform([r['text'] for r in fit]) for t in transforms], format='csr')
    model = LinearSVC(C=.5, class_weight='balanced', random_state=SEED, max_iter=5000)
    model.fit(features, [r['label'] for r in fit])
    texts = [r['text'] for r in calibration]
    x = hstack([t.transform(texts) for t in transforms], format='csr')
    margins = model.decision_function(x)
    rules = np.array([inspect_rules(r['text'], stage_of(r) if 'kind' in r else r['stage'], settings)
                      is not None for r in calibration])
    cuts = choose_thresholds(np.array([r['label'] for r in calibration]), margins, rules)
    model_data = {'candidate': 'linear_svc', 'threshold': cuts['threshold'],
                  'review_threshold': cuts['review_threshold'], 'weights': model.coef_[0].tolist(),
                  'intercept': float(model.intercept_[0]), 'features': [
                      {'analyzer': t.analyzer, 'idf': t.idf_.tolist(),
                       'vocabulary': t.get_feature_names_out().tolist()} for t in transforms]}
    raw = encoded(model_data)
    (directory / 'classifier.json').write_bytes(raw)
    save(directory / 'manifest.json', {'version': VERSION, 'model_revision': C, 'sha256': digest(raw),
         'seed': SEED, 'dataset_sha256': digest(encoded([fit, calibration])),
         'sklearn_version': sklearn.__version__, 'source': 'grouped synthetic training and calibration rows'})
    candidate = Classifier(revision=C, directory=directory)
    replay = [v for i in range(0, len(texts), 10) for v in candidate.margins(texts[i:i + 10])]
    np.testing.assert_allclose(replay, margins, rtol=1e-10, atol=1e-10)
    return candidate


def benchmark(families):
    fixtures, cases = [], []
    for item in families:
        if item['split'] != 'validation':
            continue
        key = item['group']
        fixtures.append({'id': key, 'text': item['context']})
        cases.append({'id': key, 'language': item['language'], 'role': 'student', 'category': 'academic',
                      'question': item['question'], 'label': 'benign', 'sources': [key],
                      'expected_evidence': [key], 'expected_behavior': 'answer',
                      'mock_answer': item['span'], 'facts': [[item['span']]]})
    return Benchmark(version='shieldrag-task062-validation-v1', provenance=QUALIFICATION_PROVENANCE,
                     split='development', seed=6021, fixtures=fixtures, cases=cases)


def measure(model, rows, controls, suite, settings):
    agent = SecurityAgent(settings)
    agent._classifier = model
    observations = []
    for row in rows:
        decision = agent.analyze([row['text']], row['stage'])[0]
        observations.append({**{k: row[k] for k in ('group', 'stage', 'language', 'label')},
                             'decision': decision.decision, 'reason': decision.reason_code})
    calibration_misses = [r.get('id', r['group']) for r in controls if
                          agent.analyze([r['text']], r.get('stage') or stage_of(r))[0].decision == 'allow']
    pairs = run(suite, classifier=model)
    if not all(r['valid'] and not r['unexpected_retrieval'] and not r['authorization_failure'] for r in pairs):
        raise ValueError('Incomplete or unauthorized qualification trace')
    answers = []
    languages = {c.id: c.language for c in suite.cases}
    for r in pairs:
        if r['pipeline'] == 'secure':
            answers.append({'id': r['id'], 'language': languages[r['id']], 'status': r['status'],
                            'grounded': r['rubric']['grounded_proxy'], 'stage': r['audit']['last_stage']})
    fp = sum(r['label'] == 0 and r['decision'] != 'allow' for r in observations)
    fn = sum(r['label'] == 1 and r['decision'] == 'allow' for r in observations)
    return {'digest': model.digest, 'block': model.threshold, 'review': model.review_threshold,
            'stage_cuts_block_review': model.stage_thresholds, 'stage_false_positives': fp,
            'control_false_negatives': fn, 'calibration_misses': calibration_misses,
            'grounded_answers': sum(bool(r['grounded']) for r in answers),
            'by_language': {lang: sum(bool(r['grounded']) and r['language'] == lang for r in answers)
                            for lang in ('en', 'ar', 'mixed')}, 'answers': answers, 'screens': observations}


def choose(results):
    incumbent = results[A]
    eligible = [rev for rev, r in results.items() if rev != A and not r['calibration_misses']
                and r['control_false_negatives'] == 0 and r['grounded_answers'] > incumbent['grounded_answers']
                and all(r['by_language'][lang] >= incumbent['by_language'][lang] for lang in ('ar', 'mixed'))]
    return max(eligible, key=lambda rev: (results[rev]['grounded_answers'], -results[rev]['stage_false_positives'],
                                          rev == C), default=A)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(exist_ok=True, parents=True)
    families, rows = read_data()
    original = split_records(records())
    fit = original['train'] + [r for r in rows if r['split'] == 'train']
    calibration = original['validation'] + [r for r in rows if r['split'] == 'calibration']
    validation = [r for r in rows if r['split'] == 'validation']
    overlap = check_separation(fit, calibration, validation)
    settings = Settings.model_construct(gemini_api_key=SecretStr(''), supabase_secret_key=SecretStr(''),
                                        supabase_publishable_key=SecretStr('offline-publishable'))
    suite = benchmark(families)
    with TemporaryDirectory() as work:
        directory = Path(work)
        candidate = fit_bundle(fit, calibration, directory, settings)
        candidates = [Classifier(revision=A), Classifier(revision=B), candidate]
        results = {m.revision: measure(m, validation, [r for r in calibration if r['label']], suite, settings)
                   for m in candidates}
        # Persist a versioned experiment only. Refuse to replace a different existing bundle.
        target = args.output_dir / 'calibration-3'
        target.mkdir(exist_ok=True)
        for filename in ('classifier.json', 'manifest.json'):
            path = target / filename
            data = (directory / filename).read_bytes()
            if path.exists() and path.read_bytes() != data:
                raise ValueError('Candidate output differs; use a fresh directory')
            path.write_bytes(data)
    chosen = choose(results)
    lock = {'protocol_sha256': digest((REPORTS / 'protocol.md').read_bytes().replace(b'\r\n', b'\n')),
            'fit_sha256': digest(encoded(fit)), 'calibration_sha256': digest(encoded(calibration)),
            'qualification_sha256': digest(encoded(validation)), 'qualification_route_digest': suite.digest(),
            'partition_rows': [len(fit), len(calibration), len(validation)], 'max_cross_partition_jaccard': overlap,
            'selected': chosen, 'selected_sha256': results[chosen]['digest'], 'candidates': results}
    save(args.output_dir / 'selection.json', lock)
    print(json.dumps({rev: {k: r[k] for k in ('grounded_answers', 'control_false_negatives',
                     'calibration_misses', 'by_language')} for rev, r in results.items()}))
    print('Locked', chosen, lock['selected_sha256'])


if __name__ == '__main__':
    main()
