import math
from uuid import UUID

from fastapi import HTTPException

from app.schemas.rag import AskResult, Citation, Match
from app.services.gemini import reject_credentials

ABSTENTION = 'The answer cannot be determined from the available authorized documents.'
FIELDS = 'id,original_name,visibility,review_status,index_status,sha256,indexed_sha256,embedding_model,external_processing_authorized'


async def authorize_matches(gateway, principal, matches, settings):
    profiles = await gateway.get('/rest/v1/profiles', principal.token,
        {'id': f'eq.{principal.user.id}', 'select': 'id,role', 'limit': '1'})
    if (len(profiles) != 1 or profiles[0].get('id') != str(principal.user.id)
            or profiles[0].get('role') not in ('student', 'admin')):
        raise HTTPException(403, 'Trusted profile required')
    role = profiles[0]['role']
    if not matches:
        return []
    docs = await gateway.get('/rest/v1/documents', principal.token,
        {'id': 'in.(' + ','.join(sorted({str(m.document_id) for m in matches})) + ')', 'select': FIELDS})
    allowed = {d['id']: d for d in docs if d.get('review_status') == 'approved'
        and d.get('index_status') == 'indexed' and d.get('sha256')
        and d.get('sha256') == d.get('indexed_sha256')
        and d.get('embedding_model') == settings.gemini_embedding_model
        and d.get('external_processing_authorized') is True
        and (d.get('visibility') == 'public' or role == 'admin')}
    chunks = await gateway.get('/rest/v1/document_chunks', principal.token,
        {'id': 'in.(' + ','.join(str(m.chunk_id) for m in matches) + ')', 'select': 'id,document_id,content'})
    current = {(c['id'], c['document_id'], c['content']) for c in chunks}
    return [m.model_copy(update={'document_name': allowed[str(m.document_id)]['original_name']})
            for m in matches if str(m.document_id) in allowed
            and (str(m.chunk_id), str(m.document_id), m.content) in current]


async def search(gateway, gemini, principal, question, settings):
    reject_credentials(question.question, settings)
    vectors = await gemini.embed([question.question], 'RETRIEVAL_QUERY')
    rows = await gateway.rpc('match_shield_chunks', principal.token,
        {'query_embedding': vectors[0], 'match_count': question.top_k or settings.rag_default_top_k})
    matches = []
    total = 0
    try:
        for row in rows[:question.top_k or settings.rag_default_top_k]:
            similarity = row['similarity']
            if not isinstance(similarity, (int, float)) or not math.isfinite(similarity):
                raise ValueError('Invalid similarity')
            if similarity < settings.rag_similarity_threshold:
                continue
            text = row['chunk_text']
            if not isinstance(text, str) or not text.strip() or len(text.encode()) > 1800:
                raise ValueError('Invalid chunk')
            if total + len(text) > settings.rag_max_context_chars:
                break
            total += len(text)
            matches.append(Match(chunk_id=UUID(row['chunk_id']), document_id=UUID(row['document_id']),
                document_name='', page=row['page_number'], content=text, similarity=similarity))
    except (KeyError, ValueError, TypeError):
        raise HTTPException(503, 'Invalid retrieval response') from None
    return await authorize_matches(gateway, principal, matches, settings)


async def ask(gateway, gemini, principal, question, settings):
    matches = await search(gateway, gemini, principal, question, settings)
    abstain = AskResult(answer=ABSTENTION, supported=False, citations=[])
    if not matches:
        return abstain
    answer = await gemini.generate(question.question,
        [{'source_id': i, 'text': m.content, 'document_name': m.document_name} for i, m in enumerate(matches)])
    return await validate_answer(gateway,principal,matches,answer,settings)


def valid_evidence(answer,matches):
    return bool(answer.evidence) and all(not isinstance(e.source_id,bool) and 0<=e.source_id<len(matches)
        and bool(e.quote.strip()) and e.quote in matches[e.source_id].content for e in answer.evidence)


async def validate_answer(gateway,principal,matches,answer,settings):
    abstain=AskResult(answer=ABSTENTION,supported=False,citations=[])
    if not answer.supported or not answer.answer.strip() or not answer.evidence:
        return abstain
    citations = []
    for evidence in answer.evidence:
        if (isinstance(evidence.source_id, bool) or evidence.source_id < 0 or evidence.source_id >= len(matches)
                or not evidence.quote.strip() or evidence.quote not in matches[evidence.source_id].content):
            return abstain
        match = matches[evidence.source_id]
        citations.append(Citation(chunk_id=match.chunk_id, document_id=match.document_id,
            document_name=match.document_name, page=match.page, quote=evidence.quote))
    # Permission changes or replacement indexes during generation invalidate the answer.
    current = await authorize_matches(gateway, principal, matches, settings)
    if {m.chunk_id for m in current} != {m.chunk_id for m in matches}:
        return abstain
    reject_credentials(answer.answer, settings)
    return AskResult(answer=answer.answer, supported=True, citations=citations)
