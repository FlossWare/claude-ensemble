# Knowledge Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Own durable sourced knowledge records, source identity/revisions, lifecycle/status, provenance, scope, and direct canonical lookup. Knowledge distinguishes sourced claims/material from episodic memory; exact taxonomy and overlap rules with Memory must be finalized before implementation.

Knowledge owns canonical records; Index owns derived searchable representations. Knowledge initiates ingestion/update/delete and calls Chunking, Tokenization, Embedding when required, and Index through REST only.

## Endpoints

- POST /api/v1/knowledge/sources
- GET /api/v1/knowledge/sources/{source_id}
- POST /api/v1/knowledge/sources/{source_id}/revisions
- DELETE /api/v1/knowledge/sources/{source_id}
- GET /api/v1/knowledge/sources/{source_id}/operations/{operation_id}
- GET /api/v1/health and GET /api/v1/ready

## Contract rules

- Every source has stable identity, owner/scope, source kind, canonical locator where applicable, revision, provenance, lifecycle status, and retention/deletion policy.
- Revisions are immutable snapshots with explicit source version and capture time. The current revision is unambiguous; updates do not silently mutate historical evidence.
- Preserve provenance to original source, source revision, and extraction/normalization profile. Distinguish source facts from derived interpretations.
- Mutations are idempotent; same key with a different payload conflicts. Authorization is enforced server-side for all operations.
- Delete makes a source ineligible under the defined guarantee before physical cleanup; stale indexing work cannot resurrect it.
- Ingestion durably records source revision and operation identity, then calls Chunking, Tokenization, Embedding as required, and Index via REST. Track stage status and support retry/reconciliation after restart. Canonical source revision remains authoritative if indexing fails.
- Source persistence and Index publication are not one distributed transaction.
- Knowledge provides canonical lookup. Generic lexical/vector candidate search belongs to retrieval services over Index and is orchestrated by Gateway; Knowledge must not duplicate generic corpus search.

## Errors and acceptance tests

Use the common error envelope. Distinguish invalid source, unauthorized scope, revision/idempotency conflict, retention/deletion restriction, dependency unavailable, indexing pending/failed, deadline exceeded, and internal failure. Test immutable revisions, provenance, authorization, deletion/stale-write prevention, REST-only dependencies, partial failure/reconciliation, canonical availability during Index outage, no duplicate retrieval logic, bounded retries, privacy, and restart recovery.

## Approval gate

Review with Memory, Index, Chunking, Tokenization, Embedding, Gateway, source/provenance policy, and end-to-end ingestion/retrieval workflows before implementation.
