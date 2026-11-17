import logging

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from app.schemas.rag import GeneratedAnswer
from app.schemas.security import SecureResult, SecuritySummary
from app.security.classifier import SecurityUnavailable
from app.security.decisions import Decision
from app.security.rules import inspect_rules
from app.services.gemini import UnsafeGeneratedAnswer
from app.services.rag import ABSTENTION, search, valid_evidence, validate_answer

logger=logging.getLogger(__name__)


def denied(decision):
    return SecureResult(decision=decision.decision,status='blocked',security=SecuritySummary(
        threat_detected=True,risk_level='medium' if decision.decision=='review' else 'high',
        threat_category=decision.threat_category,reason_code='security_review' if decision.decision=='review'
        else 'unsafe_context' if decision.threat_category=='indirect_prompt_injection'
        else 'unsafe_output' if decision.threat_category=='output_policy_violation' else 'unsafe_input'))


def unavailable():
    return SecureResult(decision='review',status='unavailable',security=SecuritySummary(
        threat_detected=False,risk_level='unknown',threat_category='undetermined',reason_code='security_unavailable'))


async def secure_ask(gateway,gemini,agent,audit,principal,question,settings):
    async def analyze(texts,stage):
        # Never run CPU inference on the event loop. Bounded concurrency is shared per app.
        async with agent.request_limit:
            return await run_in_threadpool(agent.analyze,texts,stage)

    async def block(decision,stage,document_id=None):
        await audit.record(principal,stage,decision.decision,decision.reason_code,document_id)
        return denied(decision)

    error_reason='classifier_error'
    try:
        decision=(await analyze([question.question],'input'))[0]
        if decision.decision!='allow':
            return await block(decision,'input')
        error_reason='provider_unavailable'
        matches=await search(gateway,gemini,principal,question,settings)
        if matches:
            error_reason='classifier_error'
            # The classifier was trained on prose, not UUID-heavy filenames.
            # Check untrusted names with rules separately; never prepend metadata
            # to the ML feature input and silently shift its input distribution.
            decisions=await analyze([m.content for m in matches],'context')
            # Analyze every authorized chunk, then block the entire request on any non-allow.
            violations=[(match,inspect_rules(match.document_name,'context',settings) or result)
                        for match,result in zip(matches,decisions)]
            violations=[pair for pair in violations if pair[1].decision!='allow']
            if violations:
                # A later confirmed block must outrank an earlier ambiguous review.
                match,result=max(violations,key=lambda pair:pair[1].decision=='block')
                return await block(result,'context',match.document_id)
            error_reason='provider_unavailable'
            raw=await gemini.generate(question.question,[{'source_id':i,'text':m.content,
                'document_name':m.document_name} for i,m in enumerate(matches)],extractive=True)
            if not isinstance(raw,GeneratedAnswer):
                raise SecurityUnavailable('Unexpected answer schema')
            error_reason='classifier_error'
            span=raw.answer.strip()
            if raw.supported and (not span or not valid_evidence(raw,matches)
                    or not any(span in evidence.quote for evidence in raw.evidence)):
                return await block(Decision('block','output_policy_violation','invalid_source_support'),'output')
            # Analyze the answer once. Quotes are checked independently by rules
            # and must be exact substrings of previously screened source chunks.
            for evidence in raw.evidence:
                if violation := inspect_rules(evidence.quote,'output',settings):
                    return await block(violation,'output')
            if span:
                output=(await analyze([span],'output'))[0]
                if output.decision!='allow':
                    return await block(output,'output')
            error_reason='provider_unavailable'
            result=await validate_answer(gateway,principal,matches,raw.model_copy(update={'answer':span}),settings)
        else:
            result=None
        # Require an audit acknowledgement before releasing any secure response.
        error_reason='provider_unavailable'
        await audit.record(principal,'output','allow','no_threat_detected')
        supported=result is not None and result.supported
        return SecureResult(decision='allow',status='answered' if supported else 'insufficient_evidence',
            answer=result.answer if supported else ABSTENTION,supported=supported,
            citations=result.citations if supported else [],security=SecuritySummary(threat_detected=False,
                risk_level='low',threat_category='none',reason_code='no_threat_detected' if supported else 'insufficient_evidence'))
    except UnsafeGeneratedAnswer:
        try:
            return await block(Decision('block','output_policy_violation','protected_credential'),'output')
        except HTTPException:
            return unavailable()
    except HTTPException as error:
        if error.status_code in (401,403):
            raise
        # No upstream exception text or payload is logged/returned.
        try:
            await audit.record(principal,'error','block',error_reason)
        except HTTPException:
            pass
        return unavailable()
    except Exception:
        try:
            await audit.record(principal,'error','block',error_reason)
        except HTTPException:
            pass
        logger.warning('Secure RAG denied after internal failure; user_id=%s',principal.user.id)
        return unavailable()
