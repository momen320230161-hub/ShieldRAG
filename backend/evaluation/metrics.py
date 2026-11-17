"""Descriptive proportions, paired comparisons and benchmark denominators."""
from collections import Counter
from math import sqrt
from random import Random
from statistics import mean, median, pstdev

from evaluation.runner import PHASES


def proportion(numerator, denominator):
    if not 0 <= numerator <= denominator:
        raise ValueError('Invalid count')
    if not denominator:
        return {'numerator': numerator, 'denominator': denominator, 'rate': None, 'wilson95': None}
    p = numerator / denominator
    z = 1.959963984540054
    scale = 1 + z*z / denominator
    center = (p + z*z / (2*denominator)) / scale
    half = z * sqrt(p*(1-p)/denominator + z*z/(4*denominator**2)) / scale
    return {'numerator': numerator, 'denominator': denominator, 'rate': p,
            'wilson95': [max(0.0, center - half), min(1.0, center + half)]}


def percentile(values, q):
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def latency(values):
    return {'N': len(values), 'mean': mean(values), 'median': median(values),
            'p95': percentile(values, .95), 'sd': pstdev(values)} if values else {
                'N': 0, 'mean': None, 'median': None, 'p95': None, 'sd': None}


def count(rows, predicate):
    return proportion(sum(bool(predicate(row)) for row in rows), len(rows))


def detection(rows):
    decisions = [r for r in rows if r['decision'] is not None]
    if not decisions:
        return None
    targets = [r for r in decisions if r['label'] == 'attack']
    benign = [r for r in decisions if r['label'] == 'benign']
    tp = sum(r['decision'] != 'allow' for r in targets)
    fp = sum(r['decision'] != 'allow' for r in benign)
    fn, tn = len(targets) - tp, len(benign) - fp
    return {'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn, 'counts': dict(Counter(r['decision'] for r in decisions)),
            'precision': proportion(tp, tp + fp), 'recall': proportion(tp, tp + fn),
            'f1': 2*tp/(2*tp + fp + fn) if 2*tp + fp + fn else None,
            'false_positive_rate': proportion(fp, fp + tn), 'false_negative_rate': proportion(fn, fn + tp)}


def group_attack(rows):
    return {'attempted': len(rows), 'valid': sum(r['valid'] for r in rows),
            'success': count([r for r in rows if r['valid']], lambda r: r['attack_success']),
            'blocked': count([r for r in rows if r['valid']], lambda r: r['status'] == 'blocked'),
            'non_allow_detection': count([r for r in rows if r['valid'] and r['decision']],
                                         lambda r: r['decision'] != 'allow')}


def quality(rows):
    answerable = [r for r in rows if r['expected_behavior'] == 'answer']
    unanswerable = [r for r in rows if r['expected_behavior'] == 'abstain']
    citations = [c for r in rows for c in r['citations']]
    present = sum(r['rubric']['facts_present'] for r in answerable)
    total = sum(r['rubric']['facts_total'] for r in answerable)
    return {'availability': count(rows, lambda r: r['available']),
            'supported': count(rows, lambda r: r['supported']),
            'insufficient_evidence': count(rows, lambda r: r['status'] == 'insufficient_evidence'),
            'security_block': count(rows, lambda r: r['status'] == 'blocked'),
            'answerable_availability': count(answerable, lambda r: r['available']),
            'expected_abstention': count(unanswerable, lambda r: r['status'] == 'insufficient_evidence'),
            'all_reference_facts': count(answerable, lambda r: r['rubric']['complete']),
            'fact_coverage': {'numerator': present, 'denominator': total, 'rate': present / total if total else None},
            'grounded_proxy': count(answerable, lambda r: r['rubric']['grounded_proxy']),
            'extractive': count(answerable, lambda r: r['extractive']),
            'multi_extract': count(answerable, lambda r: r['multi_extract']),
            # Citations in a response are clustered. Counts are descriptive, without Wilson intervals.
            'citation_validity': descriptive_citations(citations, 'valid'),
            'citation_relevance': descriptive_citations(citations, 'relevant')}


def descriptive_citations(citations, key):
    n = sum(c[key] for c in citations)
    return {'numerator': n, 'denominator': len(citations), 'rate': n / len(citations) if citations else None}


def metrics(rows):
    valid = [r for r in rows if r['valid']]
    attacks = [r for r in rows if r['label'] == 'attack']
    benign = [r for r in valid if r['label'] == 'benign']
    return {'attempted': len(rows), 'valid': len(valid), 'invalid': len(rows) - len(valid),
            'detection': detection(valid), 'attacks': group_attack(attacks),
            'attack_stages': {key: group_attack([r for r in attacks if r['stage'] == key])
                              for key in sorted({r['stage'] for r in attacks})},
            'attack_categories': {key: group_attack([r for r in attacks if r['category'] == key])
                                  for key in sorted({r['category'] for r in attacks})},
            'authorization_failures': count(rows, lambda r: r['authorization_failure']),
            'unexpected_retrieval': count(rows, lambda r: r['unexpected_retrieval']),
            'quality': quality(benign),
            'quality_categories': {key: quality([r for r in benign if r['category'] == key])
                                   for key in sorted({r['category'] for r in benign})},
            'total_ms': latency([r['total_ms'] for r in rows]),
            'phase_ms': {phase: latency([r['phase_ms'][phase] for r in rows if r['phase_ms'][phase] is not None])
                         for phase in PHASES},
            'logical_calls': {key: sum(r['logical_calls'][key] for r in rows) for key in ('embedding', 'generation')},
            'physical_provider_calls': 0, 'billable_tokens': None, 'monetary_cost': None}


def paired_binary(pairs, predicate):
    states = Counter((bool(predicate(b)), bool(predicate(s))) for b, s in pairs)
    n = len(pairs)
    return {'N': n, 'both': states[True, True], 'neither': states[False, False],
            'baseline_only': states[True, False], 'secure_only': states[False, True],
            'secure_minus_baseline': (states[False, True] - states[True, False]) / n if n else None}


def paired_latency(pairs, seed):
    values = [secure['total_ms'] - baseline['total_ms'] for baseline, secure in pairs]
    result = latency(values)
    if len(values) < 2:
        return {**result, 'bootstrap95_mean': None}
    rng = Random(seed)
    resamples = [mean(rng.choices(values, k=len(values))) for _ in range(2000)]
    return {**result, 'bootstrap95_mean': [percentile(resamples, .025), percentile(resamples, .975)]}


def summarize(benchmark, rows):
    index = {}
    ids = {c.id for c in benchmark.cases}
    for row in rows:
        key = row['id'], row['pipeline']
        if key in index or key[0] not in ids or key[1] not in ('baseline', 'secure'):
            raise ValueError('Unexpected or duplicate result row')
        index[key] = row
    pairs = [(index[c.id, 'baseline'], index[c.id, 'secure']) for c in benchmark.cases
             if all(index.get((c.id, mode), {}).get('valid') for mode in ('baseline', 'secure'))]
    attacks = [(b, s) for b, s in pairs if b['label'] == 'attack']
    benign = [(b, s) for b, s in pairs if b['label'] == 'benign']
    return {'expected_requests': len(ids) * 2, 'executed_requests': len(rows),
            'missing_requests': len(ids) * 2 - len(rows), 'valid_pairs': len(pairs),
            'complete': len(pairs) == len(ids),
            'pipelines': {mode: metrics([r for r in rows if r['pipeline'] == mode])
                          for mode in ('baseline', 'secure')},
            'paired': {'attack_success': paired_binary(attacks, lambda r: r['attack_success']),
                       'benign_availability': paired_binary(benign, lambda r: r['available']),
                       'latency_delta_ms': paired_latency(pairs, benchmark.seed)}}
