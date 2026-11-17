"""Regenerate the offline Task 06 JSON and Markdown comparison."""
import argparse
from pathlib import Path

from evaluation.benchmark import ROOT, load_benchmark
from evaluation.reporting import build_report, write
from evaluation.runner import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--suite', choices=('historical', 'development'), default='historical')
    args = parser.parse_args()
    output = ROOT.parent / 'task061'
    benchmark = load_benchmark(output / 'development.json') if args.suite == 'development' else load_benchmark()
    report = build_report(benchmark, run(benchmark))
    write(report, args.output_dir or output / args.suite)
    summary = report['summary']
    print(f"{summary['valid_pairs']}/{len(benchmark.cases)} valid paired cases; "
          f"{summary['executed_requests']}/{summary['expected_requests']} requests executed")
    if not summary['complete'] or any(
        m['authorization_failures']['numerator'] or m['unexpected_retrieval']['numerator']
        for m in summary['pipelines'].values()
    ):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
