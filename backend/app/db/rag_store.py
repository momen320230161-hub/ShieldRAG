from uuid import UUID

from app.core.authentication import Principal
from app.db.document_store import DocumentStore


class RagStore:
    def __init__(self, documents: DocumentStore):
        self.documents = documents

    async def begin(self, principal: Principal, document_id: UUID, job_id: UUID,
                     sha256: str, model: str, config_hash: str):
        response = await self.documents._request('POST', '/rest/v1/rpc/shield_begin_index', principal, admin=True,
            json={'p_actor': str(principal.user.id), 'p_id': str(document_id), 'p_job': str(job_id),
                  'p_sha256': sha256, 'p_model': model, 'p_config_hash': config_hash,
                  'p_external_authorized': True})
        return self.documents._row(response)

    async def publish(self, principal: Principal, document_id: UUID, job_id: UUID,
                       sha256: str, chunks: list[dict]):
        response = await self.documents._request('POST', '/rest/v1/rpc/shield_publish_index', principal, admin=True,
            json={'p_actor': str(principal.user.id), 'p_id': str(document_id), 'p_job': str(job_id),
                  'p_verified_sha256': sha256, 'p_chunks': chunks})
        return self.documents._row(response)

    async def fail(self, principal: Principal, document_id: UUID, job_id: UUID | None):
        response = await self.documents._request('POST', '/rest/v1/rpc/shield_fail_index', principal, admin=True,
            json={'p_actor': str(principal.user.id), 'p_id': str(document_id),
                  'p_job': str(job_id) if job_id else None})
        return self.documents._row(response)
