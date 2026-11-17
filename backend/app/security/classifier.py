"""Load bounded JSON numeric parameters, never pickle/joblib or uploaded models."""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import scipy.sparse as sparse
import sklearn

from app.security.features import FEATURES, vectorizer

VERSION='shield-security-v1'
# The deployed audit RPC accepts VERSION as its schema/policy identifier.
MODEL_REVISION='shield-security-calibration-2'
BUNDLE_DIR=Path(__file__).resolve().parent/'artifacts'


class SecurityUnavailable(Exception):
    pass


class Classifier:
    def __init__(self):
        try:
            model_path=BUNDLE_DIR/'classifier.json'
            manifest_path=BUNDLE_DIR/'manifest.json'
            if model_path.is_symlink() or manifest_path.is_symlink():
                raise ValueError('Artifact symlink')
            if model_path.stat().st_size>4_000_000 or manifest_path.stat().st_size>8192:
                raise ValueError('Artifact bounds')
            data=model_path.read_bytes()
            manifest=json.loads(manifest_path.read_bytes())
            if (hashlib.sha256(data).hexdigest()!=manifest['sha256'] or manifest['version']!=VERSION
                    or manifest['model_revision']!=MODEL_REVISION
                    or manifest['sklearn_version']!=sklearn.__version__):
                raise ValueError('Artifact identity')
            model=json.loads(data)
            self.version=VERSION
            self.threshold=float(model['threshold'])
            self.review_threshold=float(model['review_threshold'])
            stages=model['stage_thresholds']
            if not isinstance(stages,dict) or set(stages)!= {'input','context'}:
                raise ValueError('Stage policy schema')
            self.stage_thresholds={stage: (float(cuts['threshold']),float(cuts['review_threshold']))
                for stage,cuts in stages.items()}
            if (not math.isfinite(self.threshold) or not math.isfinite(self.review_threshold)
                    or not -100<self.review_threshold<self.threshold<100
                    or any(not -100<review<block<100 for block,review in self.stage_thresholds.values())
                    or model['candidate'] not in ('logistic_regression','linear_svc')
                    or len(model['features'])!=2):
                raise ValueError('Model schema')
            self.transforms=[]
            count=0
            for spec,(analyzer,limit,_) in zip(model['features'],FEATURES):
                words=spec['vocabulary']
                if (spec['analyzer']!=analyzer or not isinstance(words,list) or not 1<=len(words)<=limit
                        or any(not isinstance(w,str) or not 1<=len(w)<=200 for w in words)
                        or len(set(words))!=len(words)):
                    raise ValueError('Feature schema')
                idf=np.asarray(spec['idf'],dtype=float)
                if idf.shape!=(len(words),) or not np.isfinite(idf).all() or (idf<=0).any():
                    raise ValueError('Feature weights')
                transform=vectorizer(analyzer,{word:i for i,word in enumerate(words)})
                transform.idf_=idf
                self.transforms.append(transform)
                count+=len(words)
            self.weights=np.asarray(model['weights'],dtype=float)
            self.intercept=float(model['intercept'])
            if (self.weights.shape!=(count,) or not np.isfinite(self.weights).all()
                    or not math.isfinite(self.intercept) or np.abs(self.weights).max()>1e6):
                raise ValueError('Linear parameters')
        except Exception:
            raise SecurityUnavailable('Security model unavailable') from None

    def margins(self,texts):
        try:
            if len(texts)>11 or any(not isinstance(t,str) or len(t)>20000 for t in texts):
                raise ValueError('Inference bounds')
            features=sparse.hstack([t.transform(texts) for t in self.transforms],format='csr')
            result=np.asarray(features@self.weights+self.intercept).ravel()
            if not np.isfinite(result).all():
                raise ValueError('Nonfinite inference')
            return result.tolist()
        except Exception:
            raise SecurityUnavailable('Security inference unavailable') from None
