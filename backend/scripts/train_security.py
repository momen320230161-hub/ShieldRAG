"""Explicit synthetic-only training: python -m scripts.train_security.

Group splits precede fitting. Candidate/threshold selection sees validation only;
the untouched test split is evaluated once after selecting a fixed candidate.
"""
import hashlib
import json
import time
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


def metrics(y,p):
    tn,fp,fn,tp=confusion_matrix(y,p,labels=[0,1]).ravel()
    return {'precision':precision_score(y,p,zero_division=0),'recall':recall_score(y,p,zero_division=0),
        'f1':f1_score(y,p,zero_division=0),'macro_f1':f1_score(y,p,average='macro',zero_division=0),
        'confusion_matrix':[[int(tn),int(fp)],[int(fn),int(tp)]],
        'false_positive_rate':float(fp/max(tn+fp,1)),'false_negative_rate':float(fn/max(tp+fn,1))}


def choose_thresholds(y,margins,rule_blocks):
    """Require the original policy's validation recall (all 21 attacks)."""
    values=sorted(set([0.0,*map(float,margins)]))
    candidates=[values[0]-1,*[(a+b)/2 for a,b in zip(values,values[1:])],values[-1]+1,0.0]
    results=[(threshold,metrics(y,rule_blocks | (margins>=threshold))) for threshold in candidates]
    review,non_allow=max((item for item in results if item[1]['recall']==1.0),
        key=lambda item:(-item[1]['false_positive_rate'],item[0]))
    threshold,block=max((item for item in results if item[0]>review),
        key=lambda item:(item[1]['macro_f1'],-item[1]['false_positive_rate'],item[1]['recall'],-abs(item[0])))
    return {'threshold':threshold,'review_threshold':review,'validation':block,'validation_non_allow':non_allow,
            'validation_classifier':metrics(y,margins>=threshold)}


def main():
    rows=records(); splits=split_records(rows)
    transforms=[vectorizer(f[0]) for f in FEATURES]
    text=lambda part:[r['text'] for r in splits[part]]
    X={'train':sparse.hstack([t.fit_transform(text('train')) for t in transforms],format='csr')}
    for part in ('validation','test'):
        X[part]=sparse.hstack([t.transform(text(part)) for t in transforms],format='csr')
    y={part:np.array([r['label'] for r in data]) for part,data in splits.items()}
    candidates={'logistic_regression':LogisticRegression(C=1,class_weight='balanced',solver='liblinear',random_state=SEED,max_iter=2000),
                'linear_svc':LinearSVC(C=.5,class_weight='balanced',random_state=SEED,max_iter=5000)}
    settings=Settings(_env_file=None,supabase_url='https://example.supabase.co',
                      supabase_publishable_key='sb_publishable_synthetic')
    rule_blocks=np.array([inspect_rules(row['text'],stage_of(row),settings) is not None
                          for row in splits['validation']])
    measured={}
    for name,model in candidates.items():
        model.fit(X['train'],y['train'])
        measured[name]=choose_thresholds(y['validation'],model.decision_function(X['validation']),rule_blocks)
    selected=max(measured,key=lambda name:(-measured[name]['validation_non_allow']['false_positive_rate'],
        measured[name]['validation']['macro_f1'],
        -measured[name]['validation']['false_positive_rate'],measured[name]['validation']['recall']))
    model=candidates[selected]; threshold=measured[selected]['threshold']
    artifact={'candidate':selected,'threshold':threshold,'review_threshold':measured[selected]['review_threshold'],
        'weights':model.coef_[0].tolist(),'intercept':float(model.intercept_[0]),'features':[]}
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
        np.testing.assert_allclose(reconstructed,model.decision_function(X[part]),rtol=1e-10,atol=1e-10)
    margins=model.decision_function(X['test']); predicted=margins>=threshold
    review=margins>=artifact['review_threshold']
    report={'version':VERSION,'model_revision':MODEL_REVISION,'seed':SEED,'synthetic_only':True,'external_benchmark':None,
        'selection_scope':'Validation only; preserve 21/21 rule-or-margin attack recall, then maximize benign availability and rank block macro F1',
        'frozen_test_sha256':hashlib.sha256(
            json.dumps(splits['test'],ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
        'splits':{part:{'groups':sorted({r['group'] for r in data}),'benign':sum(r['label']==0 for r in data),
            'malicious':sum(r['label']==1 for r in data),'ids':[r['id'] for r in data]} for part,data in splits.items()},
        'candidates':measured,'selected':selected,'threshold':threshold,'review_threshold':artifact['review_threshold'],
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
    out=Path(__file__).resolve().parents[1]/'security_evaluation'
    out.mkdir(exist_ok=True)
    (out/'classifier-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'split-manifest.json').write_text(json.dumps({part:[r['id'] for r in data] for part,data in splits.items()},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'selected':selected,'validation':measured[selected],'test':report['test_classifier'],
        'test_examples':len(splits['test']),'artifact_bytes':len(raw)}))


if __name__=='__main__':
    main()
