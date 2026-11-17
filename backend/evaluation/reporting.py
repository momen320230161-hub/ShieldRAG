"""Publish only synthetic case IDs, objective results and aggregate measurements."""
import json
import platform
from collections import Counter

from app.security.classifier import BUNDLE_DIR, MODEL_REVISION
from evaluation.metrics import summarize
from evaluation.runner import PHASES

IMPLEMENTATION = '5d13a56b88155f31fd4dacc6875656e63ee61fa1'


def build_report(benchmark, rows):
    return {
        'mode': 'offline_scripted_provider_and_supabase_transport',
        'implementation_base': IMPLEMENTATION,
        'provider_contract': ('structured extracts simulated for eligible secure cases'
            if benchmark.version == 'shieldrag-task061-dev-v1' else 'identical frozen Task 06 responses'),
        'model_revision': MODEL_REVISION,
        'model_sha256': json.loads((BUNDLE_DIR / 'manifest.json').read_text(encoding='utf-8'))['sha256'],
        'benchmark': {'version': benchmark.version, 'split': benchmark.split, 'sha256': benchmark.digest(),
                      'provenance': benchmark.provenance, 'seed': benchmark.seed, 'fixtures': len(benchmark.fixtures),
                      'labels': dict(Counter(c.label for c in benchmark.cases)),
                      'roles': dict(Counter(c.role for c in benchmark.cases)),
                      'languages': dict(Counter(c.language for c in benchmark.cases))},
        'runtime': {'python': platform.python_version(), 'platform': platform.system(),
                    'architecture': platform.machine(), 'network': 'none', 'security_model': 'warm'},
        'live': {'executed': 0, 'status': 'pending_separate_owner_authorization'},
        'summary': summarize(benchmark, rows), 'cases': rows,
    }


def formatted(metric, intervals=True):
    if metric['rate'] is None:
        return 'N/A (0 denominator)'
    n, total = metric['numerator'], metric['denominator']
    output = f"{n}/{total} ({metric['rate']:.1%})"
    if intervals and metric.get('wilson95'):
        low, high = metric['wilson95']
        output += f' [{low:.1%}, {high:.1%}]'
    return output


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
        '| ' + ' | '.join('---' for _ in headers) + ' |',
        *('| ' + ' | '.join(map(str, row)) + ' |' for row in rows)])


def comparison(report):
    summary = report['summary']
    baseline, secure = (summary['pipelines'][mode] for mode in ('baseline', 'secure'))
    plans = report['benchmark']
    paired = summary['paired']
    badge = 'Complete offline run' if summary['complete'] else 'Incomplete offline run'
    nonallow = secure['detection']
    rows = [
        ('Valid requests', f"{baseline['valid']}/{baseline['attempted']}", f"{secure['valid']}/{secure['attempted']}"),
        ('Attack objective observed', *[formatted(m['attacks']['success']) for m in (baseline, secure)]),
        ('Security blocks on attacks', *[formatted(m['attacks']['blocked']) for m in (baseline, secure)]),
        ('Authorization disclosures', *[formatted(m['authorization_failures']) for m in (baseline, secure)]),
        ('Unexpected retrieved chunks by request', *[formatted(m['unexpected_retrieval']) for m in (baseline, secure)]),
    ]
    title = '# ShieldRAG Task 06.1 offline evaluation'
    blocks = [title, f'**{badge}.** {summary["valid_pairs"]} valid paired cases, '
        f'{summary["executed_requests"]}/{summary["expected_requests"]} requests executed and '
        f'{summary["missing_requests"]} unavailable because they were not executed. '
        'The mock intentionally emits scripted disallowed outcomes when an attack case reaches generation. '
        'The comparison measures protection against those injected response faults and fixture scope checks. '
        f"Provider contract: {report['provider_contract']}.",
        '## Experimental setup',
        f'Application base `{report["implementation_base"]}`, model revision `{report["model_revision"]}`, '
        f'benchmark `{plans["version"]}`, seed {plans["seed"]}, digest `{plans["sha256"]}`. '
        f'The in-process FastAPI run used Python {report["runtime"]["python"]} on '
        f'{report["runtime"]["platform"]} {report["runtime"]["architecture"]} and {plans["fixtures"]} synthetic fixture chunks. '
        'The two HTTP routes used the same sample role, question, chunk revision and retrieval parameters. '
        'Case order was seeded and first route alternated. The classifier was warmed and the embedding cache was cleared '
        'between requests. No external services were invoked.',
        f"Composition by label {plans['labels']}, by language {plans['languages']} and by role {plans['roles']}. "
        'The benchmark was authored for Task 06 after the model was fixed and was visible to developers. '
        'A separate development manifest exercises provider and audit failure paths.',
        '## Threat model',
        'These scenarios represent untrusted user questions, retrieved reference snippets and simulated provider response corruption. '
        'They test a harmless marker release, release of a fixture forbidden by role or state, or an unquoted marker with a valid citation. '
        'An authorization failure is a forbidden fixture identifier in a citation or a forbidden marker in returned content. '
        'Unexpected retrieval is counted separately. A tool or role claim in text has no authority. '
        'The fake Supabase transport represents role and review filters. This run cannot establish real RLS behavior.',
        '## Security results',
        table(('Outcome', 'Baseline', 'Secure'), rows)]
    if nonallow:
        blocks.append(f"Secure decisions include {nonallow['counts'].get('allow', 0)} allow, "
            f"{nonallow['counts'].get('block', 0)} block and {nonallow['counts'].get('review', 0)} review. "
            f"TP {nonallow['tp']}, TN {nonallow['tn']}, FP {nonallow['fp']}, FN {nonallow['fn']}. "
            f"Precision {formatted(nonallow['precision'])}, recall {formatted(nonallow['recall'])}, "
            f"F1 {nonallow['f1'] or 0:.3f}, false-positive rate {formatted(nonallow['false_positive_rate'])}, "
            f"false-negative rate {formatted(nonallow['false_negative_rate'])}. Review counts as non-allow. "
            'A missed detection can still be prevented by the authorization boundary. Baseline has no detector decision.')
    stages = sorted(set(baseline['attack_stages']) | set(secure['attack_stages']))
    blocks.append(table(('Challenge stage', 'Baseline success', 'Secure success', 'Secure non-allow'), [
        (stage, formatted(baseline['attack_stages'][stage]['success']),
         formatted(secure['attack_stages'][stage]['success']),
         formatted(secure['attack_stages'][stage]['non_allow_detection']))
        for stage in stages if stage in baseline['attack_stages'] and stage in secure['attack_stages']]))
    categories = sorted(set(baseline['attack_categories']) | set(secure['attack_categories']))
    blocks.append(table(('Attack category', 'Baseline successes', 'Secure successes', 'Secure detections'), [
        (category, *[formatted(p['attack_categories'][category]['success'], False) for p in (baseline, secure)],
         formatted(secure['attack_categories'][category]['non_allow_detection'], False))
        for category in categories if category in baseline['attack_categories'] and category in secure['attack_categories']]))
    stages = Counter(r['audit']['last_stage'] for r in report['cases'] if r['pipeline'] == 'secure'
                     and r['label'] == 'attack' and r['status'] == 'blocked')
    blocks.append('Secure audit stage on blocked attack rows: ' +
                  (', '.join(f'{stage} {count}' for stage, count in sorted(stages.items())) or 'none') + '.')
    blocks += ['## Answer quality',
        'The factual rubric searches predeclared reference phrases. Completeness is the fraction of expected facts present. '
        'The grounding proxy requires all expected facts and relevant evidence with valid citation metadata and exact quotes. '
        'These measures do not establish semantic correctness or rule out unsupported extra claims.',
        table(('Benign outcome', 'Baseline', 'Secure'), [
            (name.replace('_', ' '), formatted(baseline['quality'][name]), formatted(secure['quality'][name]))
            for name in ('availability', 'supported', 'insufficient_evidence', 'security_block', 'answerable_availability',
                         'expected_abstention', 'all_reference_facts', 'fact_coverage', 'grounded_proxy',
                         'citation_validity', 'citation_relevance', 'extractive', 'multi_extract')]),
        table(('Task', 'Baseline supported answers', 'Secure supported answers'), [
            (category, *[formatted(p['quality_categories'][category]['availability'], False)
                         for p in (baseline, secure)])
            for category in ('quotation', 'summarization', 'translation', 'multi-passage')
            if all(category in p['quality_categories'] for p in (baseline, secure))]),
        '## Performance',
        'End-to-end latency includes TestClient, authentication, worker scheduling and the mocked adapters. '
        'Retrieval includes embedding. Input/context/output screen rows measure classifier plus rules called within the agent. '
        'Separate filename checks, output evidence validation and other request work are included in end-to-end latency. '
        'An absent phase means it did not run. Logical calls count application method invocations. '
        'Real provider calls were zero and token usage and monetary cost were unavailable.',
        table(('Route', 'N', 'Mean ms', 'Median ms', 'p95 ms', 'SD ms', 'Embed calls', 'Generation calls'), [
            (name, p['total_ms']['N'], *[ms(p['total_ms'][stat]) for stat in ('mean', 'median', 'p95', 'sd')],
             p['logical_calls']['embedding'], p['logical_calls']['generation'])
            for name, p in summary['pipelines'].items()]),
        table(('Phase', 'Baseline N / median ms', 'Secure N / median ms'), [
            (phase, *[f"{p['phase_ms'][phase]['N']} / {ms(p['phase_ms'][phase]['median'])}"
                      for p in (baseline, secure)]) for phase in PHASES]),
        '## Paired uncertainty',
        'Intervals in brackets are descriptive Wilson 95% intervals on row-level proportions. '
        'Cases were deliberately constructed and share patterns. The intervals are not population generalization estimates. '
        'Paired counts use only pairs with two valid responses. No significance test was used.',
        table(('Outcome', 'Valid pairs', 'Both', 'Baseline only', 'Secure only', 'Neither'), [
            (name, *[paired[name][key] for key in ('N', 'both', 'baseline_only', 'secure_only', 'neither')])
            for name in ('attack_success', 'benign_availability')]),
        paired_timing(paired['latency_delta_ms']),
        '## Failure analysis',
        'Stable IDs below refer to public synthetic benchmark definitions. Invalid responses are visible in the JSON report '
        'and do not count as prevented attacks or as successful answers.',
        table(('Secure diagnostic', 'Case IDs'), [
            ('Benign security block', ', '.join(select(report, lambda r: r['label'] == 'benign' and r['status'] == 'blocked')) or 'None'),
            ('Attack allowed by detector', ', '.join(select(report, lambda r: r['label'] == 'attack' and r.get('decision') == 'allow')) or 'None'),
            ('Invalid response', ', '.join(select(report, lambda r: not r['valid'])) or 'None')]),
        table(('Selected secure case', 'Status', 'Retrieved chunks', 'Generations', 'Last audit stage'), [
            (r['id'], r['status'], len(r['retrieved_chunk_ids']), r['logical_calls']['generation'],
             r['audit']['last_stage'] or 'N/A')
            for r in sorted(report['cases'], key=lambda row: row['id'])
            if r['pipeline'] == 'secure' and r['id'] in ('b-admin', 'b-translate', 'b-summary', 'b-join')]),
        '## Limitations and next steps',
        'The response script forces specific faults. It measures enforcement and availability on a controlled synthetic corpus '
        'without estimating real Gemini attack rates, embedding retrieval quality, production latency or cost. '
        'The PDF scenario uses extracted text and a synthetic page identity. '
        'An exact extract can omit necessary context or faithfully repeat a false source. The rubric cannot identify all such errors. '
        'A separately authorized live pilot should measure ordinary answer availability, citations and role isolation. '
        'A larger independently authored evaluation would be needed to estimate robustness beyond these cases.',
        'Reproduce the JSON and this report with `python -m scripts.run_security_evaluation` from `backend/`. '
        'Timing and UUID-free audit summaries are scrubbed of prompts, answers, credentials, raw errors and event identifiers.'
    ]
    return '\n\n'.join(blocks) + '\n'


def select(report, predicate):
    return sorted(r['id'] for r in report['cases'] if r['pipeline'] == 'secure' and predicate(r))


def ms(value):
    return f'{value:.3f}' if value is not None else 'N/A'


def paired_timing(values):
    interval = values['bootstrap95_mean']
    return (f"The mean Secure minus Baseline latency was {ms(values['mean'])} ms on {values['N']} pairs. "
            f"The seeded 2,000-resample paired percentile bootstrap interval was "
            f"{ms(interval[0])} to {ms(interval[1])} ms in this local run.") if interval else (
                'Insufficient complete pairs for a paired latency interval.')


def write(report, directory):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'results.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    (directory / 'comparison.md').write_text(comparison(report), encoding='utf-8')
