"""Plot sanitized Task 06 results with optional Matplotlib 3.10.8."""
import argparse
import json
from pathlib import Path

from evaluation.benchmark import ROOT


def plot(report, output):
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    from matplotlib.ticker import PercentFormatter

    colors = ('#275d85', '#a94d19')
    modes = ('baseline', 'secure')
    comparison = report['summary']['pipelines']
    fig, axs = plt.subplots(2, 2, figsize=(12, 8), layout='constrained')
    fig.suptitle('ShieldRAG Task 06 | Controlled offline comparison', fontsize=16)
    fig.supxlabel('Scripted responses and synthetic authorization. Physical provider calls: 0.', fontsize=10)

    stages = sorted(comparison['secure']['attack_stages'])
    groups = [
        (axs[0, 0], 'Attack objective observed', stages,
         lambda mode, stage: comparison[mode]['attack_stages'][stage]['success']),
        (axs[0, 1], 'Benign outcomes', ['Availability', 'Security block'],
         lambda mode, label: comparison[mode]['quality'][{
             'Availability': 'availability', 'Security block': 'security_block'}[label]]),
    ]
    for ax, title, labels, metric in groups:
        for i, mode in enumerate(modes):
            measured = [metric(mode, label) for label in labels]
            positions = [j + (i - .5) * .36 for j in range(len(labels))]
            bars = ax.bar(positions, [m['rate'] or 0 for m in measured], .34, label=mode.capitalize(), color=colors[i])
            ax.bar_label(bars, [f"{m['numerator']}/{m['denominator']}" if m['denominator'] else 'N/A'
                                for m in measured], padding=4)
        ax.set_xticks(range(len(labels)), labels)
        ax.set_ylim(0, 1.19)
        ax.yaxis.set_major_formatter(PercentFormatter(1))
        ax.set_title(title)
    axs[0, 1].legend(loc='upper right', frameon=False)

    detection = comparison['secure']['detection']
    matrix = [[detection['tn'], detection['fp']], [detection['fn'], detection['tp']]]
    ax = axs[1, 0]
    ax.imshow(matrix, cmap='Blues', vmin=0, vmax=max(max(row) for row in matrix))
    for i in range(2):
        for j in range(2):
            ax.text(j, i, matrix[i][j], ha='center', va='center',
                    color='white' if matrix[i][j] >= 14 else '#111827', fontsize=14)
    ax.set_xticks([0, 1], ['Allow', 'Block or review'])
    ax.set_yticks([0, 1], ['Benign', 'Attack'])
    ax.set_title('Secure non-allow decisions')
    ax.set_ylabel('Benchmark label')

    ax = axs[1, 1]
    times = [[row['total_ms'] for row in report['cases'] if row['pipeline'] == mode] for mode in modes]
    ax.boxplot(times, tick_labels=[mode.capitalize() for mode in modes], showmeans=True)
    ax.set_title('Local end-to-end latency')
    ax.set_ylabel('Milliseconds')
    ax.grid(axis='y', alpha=.25)
    fig.savefig(output, dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=ROOT / 'reports/results.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/comparison.png')
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding='utf-8'))
    if not report['summary']['complete']:
        raise SystemExit('A complete offline report is required for plotting')
    plot(report, args.output)


if __name__ == '__main__':
    main()
