"""Replay the fixed Task 06.2 choice after verifying its qualification lock."""
import argparse
import json
from pathlib import Path

from app.security.classifier import Classifier, MODEL_REVISION
from evaluation.benchmark import ROOT, load_benchmark
from evaluation.reporting import build_report, write
from evaluation.runner import run
from scripts.qualify_security import A, B, REPORTS, save


def archived_traces(historical):
    cases = [c for c in historical.cases if c.id in {'b-constraint', 'b-ar', 'b-roles'}]
    if len(cases) != 3:
        raise ValueError('Missing regression case')
    subset = historical.model_copy(update={'cases': cases})
    traces = {}
    for revision, archive in ((A, ROOT / 'reports'), (B, ROOT.parent / 'task061/historical')):
        prior = json.loads((archive / 'results.json').read_bytes())
        expected = {r['id']: r for r in prior['cases'] if r['pipeline'] == 'secure'}
        model = Classifier(revision=revision)
        observed = run(subset, classifier=model, diagnostics=True)
        traces[revision] = {}
        for row in observed:
            if row['pipeline'] != 'secure':
                continue
            keys = ('status', 'decision', 'logical_calls', 'audit', 'retrieved_chunk_ids', 'citations')
            if any(row[k] != expected[row['id']][k] for k in keys):
                raise ValueError('Trace differs from archived execution')
            trace = {k: row[k] for k in (*keys, 'screens', 'grounding', 'source_rule_checks')}
            for stage in ('input', 'context', 'output'):
                trace['screens'].setdefault(stage, None)
            traces[revision][row['id']] = trace
    return traces


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--retained', action='store_true', help='Audit the runtime policy after the release veto')
    args = parser.parse_args()
    lock = json.loads((REPORTS / 'selection.json').read_bytes())
    revision = MODEL_REVISION if args.retained else lock['selected']
    model = Classifier(revision=revision)
    if model.digest != lock['candidates'][revision]['digest']:
        raise ValueError('Locked artifact mismatch')
    historical = load_benchmark()
    if historical.digest() != '2bc2d53c6bd1dfa60a89043a4f10d999a07824310476558deab3cec36fe13cb0':
        raise ValueError('Frozen historical manifest mismatch')
    development = load_benchmark(ROOT.parent / 'task061/development.json')
    for name, suite in (('development', development), ('historical', historical)):
        rows = run(suite, classifier=model)
        report = build_report(suite, rows)
        report.update(model_revision=model.revision, model_sha256=model.digest,
                      implementation_base='8ac119f1d547257c9a23e4c42551c75ae869cfe8')
        write(report, args.output_dir / name)
        if not report['summary']['complete'] or any(r['unexpected_retrieval'] or r['authorization_failure']
                                                   for r in rows):
            raise ValueError('Invalid or unauthorized comparison')
        secure = [r for r in rows if r['pipeline'] == 'secure']
        print(name, 'supported benign', sum(r['label'] == 'benign' and r['available'] for r in secure),
              'attack objectives achieved', sum(bool(r['attack_success']) for r in secure))
    if not args.retained:
        save(args.output_dir / 'regression-traces.json', archived_traces(historical))


if __name__ == '__main__':
    main()
