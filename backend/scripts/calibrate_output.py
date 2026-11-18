"""Fit a bounded output operating point and verify a locked candidate on paired offline routes."""
import argparse
import csv
import json
import math
from pathlib import Path

from pydantic import SecretStr

from app.core.config import Settings
from app.security.agent import SecurityAgent
from app.security.classifier import BUNDLE_DIGESTS, Classifier, OUTPUT_CALIBRATION as D, READONLY_POLICY as E, REVISIONS
from app.security.dataset import records, split_records, stage_of
from app.security.rules import inspect_readonly_output, inspect_rules
from evaluation.benchmark import OUTPUT_PROVENANCE, ROOT, load_benchmark
from evaluation.runner import run
from scripts.qualify_security import A, benchmark, check_separation, digest, encoded, read_data, save

DATA = ROOT.parent / 'output-calibration'


def table(name):
    with (DATA / name).open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream, delimiter='\t'))


def settings():
    return Settings.model_construct(gemini_api_key=SecretStr(''), supabase_secret_key=SecretStr(''),
                                    supabase_publishable_key=SecretStr('offline-publishable'))


def hashes():
    return {name: digest((DATA / name).read_bytes().replace(b'\r\n', b'\n'))
            for name in ('protocol.md', 'questions.tsv', 'controls.tsv')}


def control_rows(split):
    return [r for r in table('controls.tsv') if r['split'] == split]


def development():
    prev = split_records(records())
    _, task062 = read_data()
    # These extra training families post-date A and were never used to fit A's weights.
    post_a = [r for r in prev['train'] if r['source'] == 'project_synthetic_task061']
    output = [r for r in prev['validation'] + post_a if not r['label'] and stage_of(r) == 'output']
    return output + [r for r in task062 if r['split'] != 'validation' and not r['label']
                     and r['stage'] == 'output']


def assess_controls(model, rows):
    agent = SecurityAgent(settings())
    agent._classifier = model
    results = []
    for r in rows:
        decision = agent.analyze([r['text']], 'output')[0]
        results.append({'group': r['group'], 'language': r['language'], 'decision': decision.decision,
                        'reason': decision.reason_code, 'margin': decision.risk_score})
    return results


def fit(directory):
    model = Classifier(revision=A)
    benign = development()
    inputs = control_rows('calibration')
    incumbent_controls = assess_controls(model, inputs)
    controls = []
    for r, observation in zip(inputs, incumbent_controls, strict=True):
        rule = inspect_readonly_output(r['text'])
        controls.append({**observation, 'decision': 'block', 'reason': rule.reason_code, 'margin': None}
                        if rule else observation)
    dependent = [r['margin'] for r in controls if r['margin'] is not None]
    if len(dependent) < 6 or any(r['decision'] == 'allow' for r in controls):
        raise ValueError('Insufficient retained calibration controls')
    buffer = (model.threshold - model.review_threshold) / 4
    cap = min(model.threshold - buffer, min(dependent) - buffer)
    config = settings()
    margins = [model.margins([r['text']])[0] for r in benign
               if not (inspect_rules(r['text'], 'output', config) or inspect_readonly_output(r['text']))]
    recoverable = [m for m in margins if model.review_threshold <= m < cap]
    if not recoverable:
        raise ValueError('No development gain inside safety bounds')
    cut = math.nextafter(max(recoverable), math.inf)
    artifact = json.loads((REVISIONS[A] / 'classifier.json').read_bytes())
    artifact['stage_thresholds'] = {'output': {'threshold': model.threshold, 'review_threshold': cut}}
    raw = encoded(artifact)
    manifest = json.loads((REVISIONS[A] / 'manifest.json').read_bytes())
    manifest.update(model_revision=D, sha256=digest(raw), parent_sha256=model.digest,
                    calibration_sha256=digest(encoded([benign, control_rows('calibration')])))
    bundle = directory / 'calibration-4'
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / 'classifier.json').write_bytes(raw)
    save(bundle / 'manifest.json', manifest)
    lock = {'inputs': hashes(), 'candidate_sha256': digest(raw), 'parent_sha256': model.digest,
            'calibration_sha256': manifest['calibration_sha256'], 'benign_rows': len(benign),
            'controls': controls, 'incumbent_controls': incumbent_controls,
            'recovered_calibration_spans': len(recoverable),
            'review_before': model.review_threshold, 'review_after': cut, 'block': model.threshold}
    save(directory / 'lock.json', lock)
    print('Locked output review', cut, 'artifact', digest(raw))


def replay(suite, model):
    pairs = run(suite, classifier=model)
    if len(pairs) != 2 * len(suite.cases) or any(
        not r['valid'] or r['unexpected_retrieval'] or r['authorization_failure'] for r in pairs
    ):
        raise ValueError('Incomplete route verification or scope failure')
    if any(r['pipeline'] == 'baseline' and r['expected_behavior'] == 'answer'
           and not r['rubric']['grounded_proxy'] for r in pairs):
        raise ValueError('Scripted baseline did not return the expected supported answer')
    rows = [r for r in pairs if r['pipeline'] == 'secure']
    if any(not r['audit']['acknowledged'] or any(not c['valid'] for c in r['citations']) for r in rows):
        raise ValueError('Audit or citation failure')
    supported = [r['id'] for r in rows if r['label'] == 'benign' and r['rubric']['grounded_proxy']]
    lang = {c.id: c.language for c in suite.cases}
    return {'suite_digest': suite.digest(), 'policy_digest': model.digest,
            'supported': sorted(supported), 'by_language': {x: sum(lang[k] == x for k in supported)
                         for x in ('en', 'ar', 'mixed')}, 'secure_requests': len(rows),
            'blocked': {r['id']: [r['decision'], r['audit']['last_stage']] for r in rows if r['status'] == 'blocked'},
            'achieved_objectives': [r['id'] for r in rows if r['attack_success']],
            'multi_extracts': [r['id'] for r in rows if r['multi_extract']],
            'valid_citations': sum(len(r['citations']) for r in rows)}


def confirmed_bundle(directory):
    """E differs from the rejected D only by an additional deterministic denial."""
    data = json.loads((directory / 'calibration-4/classifier.json').read_bytes())
    manifest = json.loads((directory / 'calibration-4/manifest.json').read_bytes())
    data['output_guard'] = 'read-only-authority-v1'
    raw = encoded(data)
    if digest(raw) != BUNDLE_DIGESTS[E]:
        raise ValueError('Derived release artifact differs from shipped E')
    target = directory / 'calibration-5'
    target.mkdir(exist_ok=True)
    (target / 'classifier.json').write_bytes(raw)
    save(target / 'manifest.json', {**manifest, 'model_revision': E, 'sha256': digest(raw),
                                    'numerical_parent_sha256': manifest['sha256']})
    return Classifier(revision=E, directory=target)


def verify(directory, output, confirm=False):
    lock = json.loads((directory / 'lock.json').read_bytes())
    model = Classifier(revision=D, directory=directory / 'calibration-4')
    incumbent = Classifier(revision=A)
    if (lock != json.loads((DATA / 'lock.json').read_bytes())
            or model.digest != lock['candidate_sha256'] or lock['inputs'] != hashes()
            or incumbent.digest != lock['parent_sha256']):
        raise ValueError('Release lock mismatch')
    if confirm:
        model = confirmed_bundle(directory)
    questions = [{**q, 'split': 'validation'} for q in table('questions.tsv')]
    qualification = benchmark(questions, version='shieldrag-output-validation-v1', provenance=OUTPUT_PROVENANCE)
    positives = control_rows('validation')
    held = [{'group': q['group'], 'text': q[field]} for q in questions for field in ('question','context','span')]
    _, old_rows = read_data()
    prior = split_records(records())
    # Prior parts are already partitioned. Combine them here to check only the new boundary.
    overlap = check_separation(prior['train'] + prior['validation'] + old_rows + control_rows('calibration'),
                               [], held + positives)
    report = {'candidate_sha256': model.digest, 'max_cross_partition_jaccard': overlap}
    fit_controls = assess_controls(model, control_rows('calibration'))
    controls = assess_controls(model, positives)
    report.update(calibration_controls=fit_controls, qualification_controls=controls,
                  incumbent_controls=assess_controls(incumbent, positives))
    old_families, _ = read_data()
    suites = {'fresh': qualification, 'previous_qualification': benchmark(old_families),
              'excerpts': load_benchmark(ROOT.parent / 'task061/development.json'), 'historical': load_benchmark()}
    if suites['historical'].digest() != '2bc2d53c6bd1dfa60a89043a4f10d999a07824310476558deab3cec36fe13cb0':
        raise ValueError('Historical benchmark mismatch')
    checks = {'output_controls': all(r['decision'] != 'allow' for r in controls + fit_controls),
              'classifier_dependent_controls': sum(r['margin'] is not None for r in controls) >= 6}
    for name, suite in suites.items():
        before, after = (replay(suite, m) for m in (incumbent, model))
        report[name] = {'incumbent': before, 'candidate': after}
        checks[name] = (set(before['supported']) <= set(after['supported']) and not after['achieved_objectives']
                        and all(after['blocked'].get(k) == v for k, v in before['blocked'].items() if v[0] == 'block'))
    checks['fresh_gain'] = len(report['fresh']['candidate']['supported']) > len(report['fresh']['incumbent']['supported'])
    checks['historical_floor'] = len(report['historical']['candidate']['supported']) >= 9
    report['gates'] = checks
    output.mkdir(parents=True, exist_ok=True)
    save(output / 'verification.json', report)
    print(json.dumps(checks))
    for suite in suites:
        print(suite, *(len(report[suite][r]['supported']) for r in ('incumbent','candidate')))
    if not all(checks.values()):
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('fit', 'verify', 'confirm'))
    parser.add_argument('--bundle-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    if args.operation == 'fit':
        fit(args.bundle_dir)
    else:
        verify(args.bundle_dir, args.output_dir or args.bundle_dir, confirm=args.operation == 'confirm')


if __name__ == '__main__':
    main()
