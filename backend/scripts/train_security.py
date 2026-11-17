"""Explicit synthetic-only training: python -m scripts.train_security.

Group splits precede fitting. Candidate/threshold selection sees validation only;
the untouched test split is evaluated once after selecting a fixed candidate.
"""
import hashlib
import json
import time
from itertools import product
from pathlib import Path

import numpy as np
import scipy.sparse as sparse
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score
from sklearn.svm import LinearSVC

from app.core.config import Settings
from app.security.classifier import BUNDLE_DIR, MODEL_REVISION, VERSION, Classifier
from app.security.dataset import SEED, records, split_records, stage_of
from app.security.features import FEATURES, vectorizer
from app.security.rules import inspect_rules
from evaluation.benchmark import load_benchmark

REPORTS = Path(__file__).resolve().parents[1]/'security_evaluation/task061'


def metrics(y,p):
    tn,fp,fn,tp=confusion_matrix(y,p,labels=[0,1]).ravel()
    return {'precision':precision_score(y,p,zero_division=0),'recall':recall_score(y,p,zero_division=0),
        'f1':f1_score(y,p,zero_division=0),'macro_f1':f1_score(y,p,average='macro',zero_division=0),
        'confusion_matrix':[[int(tn),int(fp)],[int(fn),int(tp)]],
        'false_positive_rate':float(fp/max(tn+fp,1)),'false_negative_rate':float(fn/max(tp+fn,1))}


def choose_thresholds(y, margins, rule_blocks):
    """Retain every validation control before optimizing benign availability."""
    positives = y.astype(bool)
    values = sorted(set([0.0, *map(float, margins)]))
    cuts = [values[0]-1, *[(a+b)/2 for a,b in zip(values, values[1:])], values[-1]+1]
    scored = [(cut, rule_blocks | (margins >= cut)) for cut in cuts]
    review, review_pred = max((row for row in scored[:-1] if row[1][positives].all()),
        key=lambda row: (-int(row[1][~positives].sum()), row[0]))

    def block_rank(row):
        cut, pred = row
        tp, fp = int(pred[positives].sum()), int(pred[~positives].sum())
        fn, tn = int(positives.sum()) - tp, int((~positives).sum()) - fp
        macro = (tp / max(2*tp+fp+fn, 1) + tn / max(2*tn+fp+fn, 1))
        return macro, -fp, tp, -abs(cut)

    threshold, block_pred = max((row for row in scored if row[0] > review), key=block_rank)
    return {'threshold': threshold, 'review_threshold': review, 'validation': metrics(y, block_pred),
            'validation_non_allow': metrics(y, review_pred), 'validation_classifier': metrics(y, margins>=threshold)}


def calibrate(y, margins, rules, stages, old_allows):
    shared = choose_thresholds(y, margins, rules)
    stage_thresholds = {}
    block = np.full(len(y),shared['threshold'])
    review = np.full(len(y),shared['review_threshold'])
    for stage in ('input','context'):
        mask = stages == stage
        if int((mask & (y == 1) & ~rules).sum()) < 6:
            raise ValueError('Insufficient classifier-dependent stage validation controls')
        cuts = choose_thresholds(y[mask],margins[mask],rules[mask])
        stage_thresholds[stage] = {key: cuts[key] for key in ('threshold','review_threshold')}
        block[mask], review[mask] = cuts['threshold'], cuts['review_threshold']
    denied = rules | (margins >= review)
    return {'threshold': shared['threshold'], 'review_threshold': shared['review_threshold'],
            'stage_thresholds': stage_thresholds, 'validation': metrics(y,rules | (margins >= block)),
            'validation_non_allow': metrics(y,denied), 'validation_classifier': metrics(y,margins >= block),
            'new_benign_refusals': int((old_allows & denied).sum())}


def development_probes():
    suite = load_benchmark(REPORTS/'development.json')
    fixtures = {fixture.id: fixture for fixture in suite.fixtures}
    for case in suite.cases:
        if case.label != 'benign' or case.category == 'translation':
            continue
        texts = [fixtures[key].text for key in case.sources]
        yield case.id, 'input', case.question
        for text in texts:
            yield case.id, 'context', text
        for span in (texts if len(texts) > 1 else [case.mock_answer]):
            yield case.id, 'output', span


def main():
    rows=records(); splits=split_records(rows)
    transforms=[vectorizer(f[0]) for f in FEATURES]
    text=lambda part:[r['text'] for r in splits[part]]
    X={'train':sparse.hstack([t.fit_transform(text('train')) for t in transforms],format='csr')}
    for part in ('validation','test'):
        X[part]=sparse.hstack([t.transform(text(part)) for t in transforms],format='csr')
    y={part:np.array([r['label'] for r in data]) for part,data in splits.items()}
    types={'logistic_regression':LogisticRegression, 'linear_svc':LinearSVC}
    settings=Settings(_env_file=None,supabase_url='https://example.supabase.co',
                      supabase_publishable_key='sb_publishable_synthetic',gemini_api_key='',supabase_secret_key='')
    validation=splits['validation']
    rule_blocks=np.array([inspect_rules(row['text'],stage_of(row),settings) is not None for row in validation])
    stages=np.array([stage_of(row) for row in validation])
    previous=json.loads((REPORTS/'previous-validation.json').read_text(encoding='utf-8'))
    original={row['id']: row['decision'] for row in previous['cases']}
    if set(original) != {row['id'] for row in validation}:
        raise ValueError('Previous-policy reference must exactly cover validation IDs')
    old_allows=np.array([row['label']==0 and original[row['id']]=='allow' for row in validation])
    multilingual_inputs = old_allows & (stages == 'input') & np.array([
        any('\u0600' <= char <= '\u06ff' for char in row['text']) for row in validation])
    probes = list(development_probes())
    probe_texts = [text for _,_,text in probes]
    x_probes = sparse.hstack([t.transform(probe_texts) for t in transforms],format='csr')
    probe_rules = [inspect_rules(text, stage, settings) is not None for _,stage,text in probes]

    def rank(row):
        return (-row['new_multilingual_input_refusals'], -len(row['development_refusal_ids']),
                -row['validation_non_allow']['false_positive_rate'], -row['new_benign_refusals'], row['validation']['macro_f1'],
                -row['validation']['false_positive_rate'], row['validation']['recall'])

    development = np.array([r['source']=='project_synthetic_task061' for r in splits['train']])
    word_count = len(transforms[0].vocabulary_)
    measured, winners = {}, {}
    for word_scale in (.25, .5, 1., 2., 4.):
        scale = np.ones(X['train'].shape[1])
        scale[:word_count] = word_scale
        x_train, x_validation = (X[part].multiply(scale).tocsr() for part in ('train', 'validation'))
        for (name, factory), regularization, development_weight in product(types.items(), (.1, .5, 2., 16.), (.25, .5, 1., 2.)):
            model = factory(C=regularization, class_weight='balanced', random_state=SEED, max_iter=5000)
            model.fit(x_train,y['train'],sample_weight=np.where(development,development_weight,1.))
            validation_margins = model.decision_function(x_validation)
            result = calibrate(y['validation'],validation_margins,rule_blocks,stages,old_allows)
            stage_cuts = result['stage_thresholds']
            input_cut = stage_cuts['input']['review_threshold']
            result['new_multilingual_input_refusals'] = int(
                ((rule_blocks | (validation_margins >= input_cut)) & multilingual_inputs).sum())
            result['development_refusal_ids'] = sorted({
                case_id for (case_id, stage, _), margin, rule in zip(
                    probes, model.decision_function(x_probes.multiply(scale)), probe_rules, strict=True)
                if rule or margin >= stage_cuts.get(stage,result)['review_threshold']})
            if name not in measured or rank(result) > rank(measured[name]):
                measured[name] = {**result, 'word_scale': word_scale, 'C': regularization,
                                  'development_weight': development_weight}
                winners[name] = model, scale
    selected = max(measured, key=lambda name: rank(measured[name]))
    model, scale = winners[selected]
    threshold = measured[selected]['threshold']
    artifact={'candidate':selected,'threshold':threshold,'review_threshold':measured[selected]['review_threshold'],
        'stage_thresholds':measured[selected]['stage_thresholds'],
        'weights':(model.coef_[0]*scale).tolist(),'intercept':float(model.intercept_[0]),'features':[]}
    for transform,(analyzer,_,_) in zip(transforms,FEATURES):
        artifact['features'].append({'analyzer':analyzer,'vocabulary':transform.get_feature_names_out().tolist(),
                                    'idf':transform.idf_.tolist()})
    raw=json.dumps(artifact,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    dataset_raw=json.dumps(rows,ensure_ascii=False,sort_keys=True).encode()
    BUNDLE_DIR.mkdir(parents=True,exist_ok=True)
    (BUNDLE_DIR/'classifier.json').write_bytes(raw)
    manifest={'version':VERSION,'model_revision':MODEL_REVISION,'sha256':hashlib.sha256(raw).hexdigest(),'seed':SEED,
        'dataset_sha256':hashlib.sha256(dataset_raw).hexdigest(),'sklearn_version':sklearn.__version__,
        'source':'project-authored synthetic families; no external benchmark or private content'}
    (BUNDLE_DIR/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    runtime=Classifier()
    # Serialization must preserve the trained estimator's decision function.
    for part in splits:
        reconstructed=[]
        for start in range(0,len(splits[part]),11):
            reconstructed.extend(runtime.margins(text(part)[start:start+11]))
        np.testing.assert_allclose(reconstructed,model.decision_function(X[part].multiply(scale)),rtol=1e-10,atol=1e-10)
    margins=model.decision_function(X['test'].multiply(scale))
    test_cuts=[artifact['stage_thresholds'].get(stage_of(row),artifact) for row in splits['test']]
    predicted=margins>=np.array([cuts['threshold'] for cuts in test_cuts])
    review=margins>=np.array([cuts['review_threshold'] for cuts in test_cuts])
    report={'version':VERSION,'model_revision':MODEL_REVISION,'seed':SEED,'synthetic_only':True,'external_benchmark':None,
        'selection_scope':'Validation stage thresholds retain all controls; candidate ranking first preserves prior multilingual inputs and minimizes extractable development refusals, then ranks validation availability and block metrics',
        'frozen_test_sha256':hashlib.sha256(
            json.dumps(splits['test'],ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
        'splits':{part:{'groups':sorted({r['group'] for r in data}),'benign':sum(r['label']==0 for r in data),
            'malicious':sum(r['label']==1 for r in data),'ids':[r['id'] for r in data]} for part,data in splits.items()},
        'candidates':measured,'selected':selected,'threshold':threshold,'review_threshold':artifact['review_threshold'],
        'stage_thresholds':artifact['stage_thresholds'],
        'test_classifier':metrics(y['test'],predicted),'test_non_allow_including_review':metrics(y['test'],review),
        'per_kind':{},'errors':[],'artifact_bytes':len(raw),'artifact_sha256':manifest['sha256']}
    for kind in ('benign','direct','indirect'):
        indices=[i for i,r in enumerate(splits['test']) if r['kind']==kind]
        report['per_kind'][kind]={'count':len(indices),'correct_at_block_threshold':sum(bool(predicted[i])==bool(y['test'][i]) for i in indices)}
    for row,guess,margin in zip(splits['test'],predicted,margins):
        if bool(guess)!=bool(row['label']):
            report['errors'].append({'id':row['id'],'text':row['text'],'expected':row['label'],
                'predicted':int(guess),'margin':float(margin)})
    latencies=[]
    for value in text('test'):
        start=time.perf_counter(); runtime.margins([value]); latencies.append((time.perf_counter()-start)*1000)
    report['latency_ms']={'mean':float(np.mean(latencies)),'p95':float(np.percentile(latencies,95)),
                          'scope':'single-process local per-example inference; not deployment load'}
    out=REPORTS
    out.mkdir(exist_ok=True)
    (out/'classifier-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'split-manifest.json').write_text(json.dumps({part:[r['id'] for r in data] for part,data in splits.items()},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'selected':selected,'validation':measured[selected],'test':report['test_classifier'],
        'test_examples':len(splits['test']),'artifact_bytes':len(raw)}))


if __name__=='__main__':
    main()
