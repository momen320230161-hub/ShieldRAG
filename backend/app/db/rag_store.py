from uuid import UUID

from fastapi import HTTPException

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

    async def fail(self, principal: Principal, document_id: UUID, job_id: UUID):
        response = await self.documents._request('POST', '/rest/v1/rpc/shield_fail_index', principal, admin=True,
            json={'p_actor': str(principal.user.id), 'p_id': str(document_id),
                  'p_job': str(job_id)})
        return self.documents._row(response)

    async def record_integrity_failure(self, principal: Principal, document: dict,
                                       event_id: UUID, failure: str, observed_sha256: str | None):
        # Called by the existing shielded/idempotent integrity-audit helper.
        # Audit + invalidation of this exact completed revision commit together.
        response = await self.documents._request('POST', '/rest/v1/rpc/shield_invalidate_index',
            principal, admin=True, json={
                'p_actor': str(principal.user.id), 'p_document_id': document['id'],
                'p_revision': document['index_revision_id'], 'p_event_id': str(event_id),
                'p_failure': failure, 'p_expected_sha256': document['sha256'],
                'p_storage_path': document['storage_path'], 'p_observed_sha256': observed_sha256})
        try:
            confirmed = response.json()
        except ValueError:
            raise HTTPException(503, 'Integrity audit acknowledgement is invalid') from None
        if confirmed != str(event_id):
            raise HTTPException(503, 'Integrity audit acknowledgement is invalid')
