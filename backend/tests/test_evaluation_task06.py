import json

import pytest
from pydantic import ValidationError

from app.security.dataset import records
from evaluation.benchmark import Benchmark, ROOT, load_benchmark
from evaluation.metrics import latency, paired_binary, proportion, summarize
from evaluation.reporting import build_report, write
from evaluation.runner import SERVER, Scenario, Trace, run, score_response


@pytest.fixture(scope='module')
def experiment():
    benchmark = load_benchmark()
    return benchmark, run(benchmark)


@pytest.mark.parametrize('defect', ['duplicate_id', 'duplicate_case', 'bad_label', 'unknown_source', 'forbidden'])
def test_manifest_rejects_bad_identity_label_and_scope(defect):
    body = load_benchmark().model_dump(mode='json')
    if defect == 'duplicate_id':
        body['cases'].append(body['cases'][0])
    elif defect == 'duplicate_case':
        body['cases'].append({**body['cases'][0], 'id': 'second-id'})
    elif defect == 'bad_label':
        body['cases'][0]['label'] = 'attack'
    elif defect == 'unknown_source':
        body['cases'][0]['sources'] = ['nonexistent']
    else:
        next(c for c in body['cases'] if c['id'] == 'b-admin')['role'] = 'student'
        # Keep the experimental case unique to reach the role/evidence validation.
        next(c for c in body['cases'] if c['id'] == 'b-admin')['question'] += ' Please use the reference.'
    with pytest.raises(ValidationError):
        Benchmark.model_validate(body)


def test_benchmark_has_no_exact_overlap_with_existing_examples_or_debug_cases():
    benchmark = load_benchmark()
    debug = load_benchmark(ROOT / 'benchmark/development.json')
    normalize = lambda text: ' '.join(text.casefold().split())
    old = {normalize(row['text']) for row in records()}
    new = {normalize(case.question) for case in benchmark.cases} | {normalize(f.text) for f in benchmark.fixtures}
    assert not new & old
    assert not {c.id for c in benchmark.cases} & {c.id for c in debug.cases}


def test_paired_http_routes_obey_fixture_scope(experiment):
    benchmark, rows = experiment
    indexed = {(row['id'], row['pipeline']): row for row in rows}
    for mode in ('baseline', 'secure'):
        for case in ('a-restricted-record', 'a-pending-access', 'a-rejected-access', 'b-missing'):
            result = indexed[case, mode]
            assert not result['authorization_failure']
            assert not result['retrieved_chunk_ids'] and result['logical_calls']['generation'] == 0
        result = indexed['b-admin', mode]
        fixture = next(f for f in benchmark.fixtures if f.id == 'b-admin-ref-1')
        assert result['retrieved_chunk_ids'] == [fixture.chunk_id]
        if mode == 'baseline':
            assert result['status'] == 'answered'
            assert result['citations'] == [{'chunk_id': fixture.chunk_id, 'valid': True, 'relevant': True}]
        else:
            # The shared authorization check retrieved the permitted chunk.
            # Either non-allow action must withhold the content after context screening.
            assert result['status'] == 'blocked' and result['decision'] in ('block', 'review')
            assert result['audit']['last_stage'] == 'context' and not result['citations']
    assert not any(r['unexpected_retrieval'] or r['authorization_failure'] for r in rows)
    assert summarize(benchmark, rows)['complete']


def test_synthetic_output_fault_and_real_pipeline_audit(experiment):
    _, rows = experiment
    indexed = {(row['id'], row['pipeline']): row for row in rows}
    baseline = indexed['a-answer-contamination', 'baseline']
    secure = indexed['a-answer-contamination', 'secure']
    assert baseline['attack_success'] and baseline['citations'][0]['valid']
    assert not secure['attack_success'] and secure['status'] == 'blocked'
    assert secure['audit']['acknowledged']
    indirect = indexed['a-indirect-pdf', 'secure']
    assert indirect['status'] == 'blocked' and indirect['logical_calls']['generation'] == 0

    for result in rows:
        if result['pipeline'] == 'secure':
            assert result['audit']['acknowledged']
            assert result['audit']['unique_events'] == 1


@pytest.mark.parametrize('fault,expected_status,event_count', [
    ('malformed', 'unavailable', 1), ('audit_failure', 'unavailable', 2), ('lost_ack', 'answered', 1),
])
def test_development_faults_are_isolated(fault, expected_status, event_count):
    debug = load_benchmark(ROOT / 'benchmark/development.json')
    rows = run(debug, fault=fault)
    secure = next(r for r in rows if r['pipeline'] == 'secure')
    assert secure['status'] == expected_status
    assert secure['audit']['unique_events'] == event_count
    if fault == 'lost_ack':
        assert secure['audit']['attempts'] == 2 and secure['audit']['acknowledged']


def test_forbidden_marker_on_malformed_error_is_detected_and_withheld_from_report():
    benchmark = load_benchmark()
    case = next(c for c in benchmark.cases if c.id == 'a-restricted-record')
    scenario = Scenario(case, {f.id: f for f in benchmark.fixtures}, Trace())
    row = score_response(case, scenario, 'secure', 503, {'answer': case.marker}, 1)
    assert not row['valid'] and row['authorization_failure']
    assert case.marker not in json.dumps(row)


def test_proportions_zero_denominator_and_wilson():
    assert proportion(0, 0) == {'numerator': 0, 'denominator': 0, 'rate': None, 'wilson95': None}
    assert proportion(0, 22)['wilson95'] == pytest.approx([0, .148655], abs=1e-6)
    assert proportion(10, 10)['wilson95'] == pytest.approx([.722467, 1], abs=1e-6)
    assert proportion(1, 4)['rate'] == .25
    with pytest.raises(ValueError):
        proportion(1, 0)


def test_paired_binary_and_latency():
    assert paired_binary([(True, False), (True, True), (False, True), (True, False)], bool) == {
        'N': 4, 'both': 1, 'neither': 0, 'baseline_only': 2, 'secure_only': 1, 'secure_minus_baseline': -.25}
    assert paired_binary([], bool)['secure_minus_baseline'] is None
    assert latency([])['median'] is None
    assert latency([1, 2, 3])['p95'] == pytest.approx(2.9)


def test_incomplete_runs_are_excluded_from_paired_denominator(experiment):
    benchmark, rows = experiment
    summary = summarize(benchmark, rows[:-1])
    assert not summary['complete'] and summary['missing_requests'] == 1
    assert summary['valid_pairs'] == len(benchmark.cases) - 1
    with pytest.raises(ValueError):
        summarize(benchmark, [rows[0], rows[0]])


def test_measured_detection_false_positives_and_attack_success(experiment):
    benchmark, rows = experiment
    metrics = summarize(benchmark, rows)['pipelines']
    base, secure = metrics['baseline'], metrics['secure']
    assert base['detection'] is None
    assert secure['detection']['false_positive_rate']['numerator'] == sum(
        r['label'] == 'benign' and r['decision'] in ('review', 'block') for r in rows)
    assert base['attacks']['success']['numerator'] == sum(
        r['pipeline'] == 'baseline' and r['attack_success'] is True for r in rows)
    assert secure['attacks']['success']['numerator'] == 0
    assert secure['quality']['security_block']['numerator'] > 0
    assert secure['physical_provider_calls'] == 0
    assert secure['billable_tokens'] is None and secure['monetary_cost'] is None


def test_sanitized_report_round_trip(tmp_path, experiment):
    benchmark, rows = experiment
    report = build_report(benchmark, rows)
    write(report, tmp_path)
    serialized = (tmp_path / 'results.json').read_text(encoding='utf-8')
    markdown = (tmp_path / 'comparison.md').read_text(encoding='utf-8')
    assert json.loads(serialized) == report
    assert '"answer":' not in serialized and '"quote":' not in serialized and SERVER not in serialized
    for case in benchmark.cases:
        assert case.question not in serialized + markdown
        assert not case.marker or case.marker not in serialized + markdown
    for fixture in benchmark.fixtures:
        assert fixture.text not in serialized + markdown
