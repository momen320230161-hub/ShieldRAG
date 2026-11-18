"""Evaluate the frozen bundle and rules; never fit or select parameters here."""
import json
import time
import tempfile
from pathlib import Path

import numpy as np

from app.core.config import Settings
from app.security.agent import SecurityAgent
from app.security.classifier import Classifier
from app.security.dataset import records,split_records,stage_of
from scripts.train_security import metrics


def main():
    parts=split_records(records());model=Classifier()
    config=Settings(_env_file=None,supabase_url='https://example.supabase.co',
                    supabase_publishable_key='sb_publishable_synthetic',gemini_api_key='',supabase_secret_key='')
    agent=SecurityAgent(config);agent._model()
    results=[];latencies=[]
    for row in parts['test']:
        stage=stage_of(row)
        start=time.perf_counter();decision=agent.analyze([row['text']],stage)[0]
        latencies.append((time.perf_counter()-start)*1000)
        results.append({'id':row['id'],'text':row['text'],'expected':row['label'],'kind':row['kind'],
            'decision':decision.decision,'reason_code':decision.reason_code,'margin':decision.risk_score,
            'correct_non_allow':(decision.decision!='allow')==bool(row['label'])})
    y=[r['label'] for r in parts['test']]
    prediction=[r['decision']!='allow' for r in results]
    validation=parts['validation'];margins=[]
    for i in range(0,len(validation),11):margins.extend(model.margins([r['text'] for r in validation[i:i+11]]))
    report={'scope':'Previously inspected frozen synthetic test set; development comparison only',
        'test_counts':{'benign':sum(x==0 for x in y),'malicious':sum(x==1 for x in y)},
        'agent_non_allow_metrics':metrics(y,prediction),'decision_counts':{v:sum(r['decision']==v for r in results) for v in ('allow','review','block')},
        'per_kind':{kind:{'count':sum(r['kind']==kind for r in results),
            'correct_non_allow':sum(r['kind']==kind and r['correct_non_allow'] for r in results)} for kind in ('benign','direct','indirect')},
        'errors':[r for r in results if not r['correct_non_allow']],
        'validation_threshold_sweep':[{'threshold':threshold,**metrics([r['label'] for r in validation],np.asarray(margins)>=threshold)}
            for threshold in (model.review_threshold,model.threshold,model.threshold+.25)],
        'latency_ms':{'mean':float(np.mean(latencies)),'p95':float(np.percentile(latencies,95)),
            'scope':'Warm local rule+classifier per-text latency, no network; not deployment throughput'},
        'limitations':'The original test set was inspected before Task 05.1. Its unchanged examples and families were excluded from fitting, candidate selection and threshold selection. No independent external benchmark was run.'}
    report['model_revision'] = model.revision
    report['model_sha256'] = model.digest
    path=Path(tempfile.mkdtemp(prefix='shieldrag-agent-'))/'agent-report.json'
    print(f'Agent report: {path}')
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('test_counts','agent_non_allow_metrics','decision_counts','latency_ms')}))


if __name__=='__main__':main()
