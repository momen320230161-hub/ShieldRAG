"""Run all published English and Arabic XQuAD rows through matched offline routes."""
import argparse
import json
from pathlib import Path

from app.security.classifier import BUNDLE_DIGESTS, Classifier
from evaluation.benchmark import XQUAD_PROVENANCE
from scripts.calibrate_output import E, replay
from scripts.qualify_security import A, benchmark, digest, save

UPSTREAM = '7d30520c717524000f0d9d2f9c10a069acd9d285'
FILES = {'en': 'e4c57d1c9143aaa1c5d265ba5987a65f4e69528d2a98f29d6e75019b10344f29',
         'ar': 'abdabd7afed5c635d99cca0f3f0d0c9d9ed0bc77451e963c2e4e0638c29e486d'}


def annotated_window(context, annotation):
    answer = annotation['text']
    start = annotation['answer_start']
    if not 0 < len(answer) <= 380 or context[start:start + len(answer)] != answer:
        raise ValueError('Invalid reference offset or oversized span')
    left = max(0, min(start - (380 - len(answer)) // 2, len(context) - 380))
    window = context[left:left + 380]
    if answer not in window:
        raise ValueError('Reference is outside the fixture window')
    return window, answer


def examples(root, language):
    raw = (root / f'xquad.{language}.json').read_bytes().replace(b'\r\n', b'\n')
    if digest(raw) != FILES[language]:
        raise ValueError('Unexpected XQuAD file digest')
    cases = []
    for article in json.loads(raw)['data']:
        for paragraph in article['paragraphs']:
            for qa in paragraph['qas']:
                context, answer = annotated_window(paragraph['context'], qa['answers'][0])
                cases.append({'split': 'validation', 'group': 'xq-' + qa['id'], 'language': language,
                              'question': qa['question'], 'context': context, 'span': answer})
    if len(cases) != 1190 or len({r['group'] for r in cases}) != len(cases):
        raise ValueError('Incomplete language edition or repeated identity')
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--candidate-dir', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    old = Classifier(revision=A)
    new = Classifier(revision=E, directory=args.candidate_dir)
    if new.digest != BUNDLE_DIGESTS[E]:
        raise ValueError('External confirmation requires the pinned release artifact')
    results = {'upstream': UPSTREAM, 'files': FILES, 'incumbent_digest': old.digest,
               'candidate_digest': new.digest, 'languages': {}}
    for language in FILES:
        cases = examples(args.data_dir, language)
        answered = {A: set(), E: set()}
        citations = {A: 0, E: 0}
        for i in range(0, len(cases), 100):
            suite = benchmark(cases[i:i + 100], version='shieldrag-xquad-v1', provenance=XQUAD_PROVENANCE)
            for model in (old, new):
                result = replay(suite, model)
                answered[model.revision].update(result['supported'])
                citations[model.revision] += result['valid_citations']
        before, after = answered[A], answered[E]
        results['languages'][language] = {
            'total': len(cases), 'incumbent_supported': len(before), 'candidate_supported': len(after),
            'gained_ids': sorted(after - before), 'lost_ids': sorted(before - after),
            'valid_citations': citations, 'secure_audits_per_policy': len(cases)}
        print(language, len(before), len(after), 'lost', len(before - after), flush=True)
    results['passed'] = all(v['candidate_supported'] > v['incumbent_supported'] and not v['lost_ids']
                            for v in results['languages'].values())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    save(args.output, results)
    if not results['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
