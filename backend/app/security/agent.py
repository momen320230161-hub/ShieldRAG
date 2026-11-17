import threading
import asyncio

from app.security.classifier import Classifier, SecurityUnavailable
from app.security.decisions import Decision
from app.security.rules import inspect_rules, normalize


class SecurityAgent:
    def __init__(self,settings):
        self.settings=settings
        self._classifier=None
        self._load_lock=threading.Lock()
        self.request_limit=asyncio.Semaphore(2)

    def _model(self):
        if self._classifier is None:
            with self._load_lock:
                if self._classifier is None:
                    self._classifier=Classifier()
        return self._classifier

    def analyze(self,texts,stage):
        try:
            if stage not in ('input','context','output') or not 1<=len(texts)<=10:
                raise SecurityUnavailable('Security analysis bounds')
            if sum(len(t) for t in texts)>20000 or any(not isinstance(t,str) for t in texts):
                raise SecurityUnavailable('Security analysis bounds')
            # Required model integrity is verified even when a rule would block.
            model=self._model()
            rules=[inspect_rules(t,stage,self.settings) for t in texts]
            margins=model.margins([normalize(t) for t in texts])
            block,review=model.stage_thresholds.get(stage,(model.threshold,model.review_threshold))
            decisions=[]
            for rule,margin in zip(rules,margins):
                if rule is not None:
                    decisions.append(rule)
                    continue
                action='block' if margin>=block else 'review' if margin>=review else 'allow'
                category='none' if action=='allow' else 'indirect_prompt_injection' if stage=='context' else (
                    'output_policy_violation' if stage=='output' else 'direct_prompt_injection')
                decisions.append(Decision(action,category,'no_threat_detected' if action=='allow' else
                    'classifier_attack' if action=='block' else 'classifier_review',risk_score=margin))
            if len(decisions)!=len(texts):
                raise SecurityUnavailable('Security decision incomplete')
            return decisions
        except SecurityUnavailable:
            raise
        except Exception:
            raise SecurityUnavailable('Security analysis unavailable') from None
