# Graph Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Own graph nodes, edges, relationship types, identity, provenance, mutation lifecycle, and bounded traversal. Graph is authoritative for relationship data only; it does not own canonical Memory/Knowledge source content or perform lexical/vector retrieval.

## Endpoints

- POST /api/v1/graph/nodes: create or upsert a node under explicit idempotency semantics.
- GET /api/v1/graph/nodes/{node_id}: direct node lookup.
- POST /api/v1/graph/edges: create or upsert an edge.
- DELETE /api/v1/graph/edges/{edge_id}: remove/tombstone an edge.
- POST /api/v1/graph/traversals: bounded traversal/query.
- POST /api/v1/graph/source-projections: idempotently upsert graph facts derived from one canonical source revision.
- POST /api/v1/graph/source-deletions: tombstone graph facts derived from a source identity/revision.
- GET /api/v1/graph/operations/{operation_id}: query projection/deletion status.
- GET /api/v1/graph/sources/manifest: bounded source revision/tombstone manifest for reconciliation.
- GET /api/v1/graph/health and GET /api/v1/graph/ready.

Node/edge schemas and identity rules below are normative for the initial contract. Memory and Knowledge are the source-projection writers for relationships derived from their canonical records; they call Graph through REST after extraction/validation. Graph does not call either owner.

## Source projection schemas

`POST /api/v1/graph/source-projections` request fields: `operation_id`, `source_id`, opaque `source_revision`, monotonic `revision_sequence`, canonical `scope`, and bounded arrays of nodes/edges. Each edge has stable `edge_id`, `source_node_id`, `target_node_id`, `relationship_type`, directionality, and provenance. Response returns `operation_id`, accepted source revision/sequence, status, and `request_id`.

`POST /api/v1/graph/source-deletions` request fields: `operation_id`, `source_id`, tombstone `revision_sequence`, scope, and `delete_scope=source`. V1 supports source-wide tombstones only; revision-specific deletion is unsupported. The tombstone sequence must exceed prior source revisions. Response reports durable tombstone status. Stale projections at or below the tombstone sequence are rejected.

## Semantics

- A graph fact is identified by its normalized relationship identity plus a set of source supports. Each support is `(source_id, source_revision, revision_sequence, scope)`; two sources asserting the same relationship create two supports, not one untraceable fact.
- Deleting or superseding one source removes only that source's support. The relationship remains queryable while at least one current support remains. A traversal result must include support provenance for each edge.
- A returned path is eligible only when every edge in the path has at least one non-tombstoned support in the requested scope. If a path has no current support for any edge, omit the path. If a path contains multiple supports for an edge, include only current support evidence; never let one stale support make a path current when no current support remains. Graph never calls Memory/Knowledge to verify freshness; owner-issued projections and tombstones plus revision high-water marks govern its derived state. Gateway canonical verification remains the final response freshness gate.
- Source projection and deletion operations are idempotent and status-queryable through `GET /api/v1/graph/operations/{operation_id}`. Graph retains durable source revision/tombstone watermarks and exposes a paginated `GET /api/v1/graph/sources/manifest` for owner/operator reconciliation. V1 recovery rebuild is owner-led: Memory and Knowledge replay their durable source projection journals; Graph reports its own manifest/watermarks and does not call back into owners. Memory and Knowledge replay their own graph projections and tombstones; Graph never calls back into them.

- Node and edge identity are stable and explicitly scoped. Edge type, directionality, source/target identity, provenance, validity/lifecycle, and timestamps are represented explicitly. Every source-derived graph fact carries `source_id`, `source_revision`, and `revision_sequence`.
- Mutations are idempotent; same idempotency key with different payload returns `409 idempotency_conflict`. For a given `source_id`, a projection with a lower `revision_sequence` than the highest accepted source sequence is rejected as `409 revision_conflict`; an equal sequence is idempotent only for the same source revision and canonical projection payload, otherwise it returns `409 revision_conflict`. A source-wide tombstone advances the source high-water mark and rejects all later-arriving projections at or below it.
- Traversal requests specify start nodes, allowed edge types/directions, maximum depth, maximum visited nodes, maximum returned paths/results, and deadline. No unbounded graph walks.
- Results include provenance and enough revision/status metadata to distinguish current relationships from stale references to source records. Source-projection writes are idempotent by operation ID and source revision. Source deletion tombstones all facts derived from that source; delayed projections at or below the source tombstone sequence are rejected. Tombstone high-water marks survive cleanup and rebuild.
- Graph does not implicitly fetch Memory/Knowledge content. Callers use those services' REST contracts when canonical source data is needed.
- Scope partition filters are applied server-side on reads, writes, and traversals. Only local access restrictions required by the deployment apply; scope selects a data partition and does not establish caller identity.
- Traversal ordering and tie-breaking are deterministic for fixed graph state and policy when applicable. Cycles and duplicate paths are handled explicitly.
- Do not log sensitive node/edge properties by default. Propagate correlation, deadlines, cancellation, and bounded retry semantics.

## Machine-checkable schemas

The normative Graph request/response JSON Schema is in [`schemas/graph.schema.json`](schemas/graph.schema.json). It defines projection, deletion, traversal, and operation response shapes, including bounds and status enums.

## Endpoint status codes

- Node/edge/traversal successful reads or synchronous operations: `200`.
- Accepted source projection/deletion: `202` with `operation_id`; query status through the operation endpoint (`200`). `GET /api/v1/graph/ready` returns not-ready while recovery replay checkpoints are incomplete. A delete operation is `complete` only when every support for that source is retrieval-ineligible; physical cleanup may finish asynchronously.
- Invalid schema/parameter: `400 invalid_request`.
- Missing node/edge/operation: `404 not_found`.
- Idempotency conflict, stale sequence, or unsupported revision transition: `409 idempotency_conflict` or `409 revision_conflict`.
- If the encoded HTTP request body exceeds the common REST body limit, return `413 request_too_large`. If a validly encoded source projection exceeds its documented source/profile limits, return `422 source_too_large`.
- Deadline: `504 deadline_exceeded`; Graph/dependency unavailable: `503 service_unavailable` or `503 dependency_unavailable`.

## Errors

Use the common error envelope. Distinguish invalid node/edge, missing endpoint node, required local access restriction failure, idempotency/version conflict, traversal limit exceeded, deadline exceeded, and unavailable/internal failure.

## Acceptance tests

1. Node/edge identity, directionality, and relationship types are explicit.
2. Idempotent mutation and concurrent conflict behavior are tested.
3. Traversal depth/node/result/time limits are enforced.
4. Cycles and duplicate paths cannot cause unbounded work.
5. Scope partition filters are enforced server-side.
6. Results preserve provenance and expose stale source references.
7. Graph does not access Memory/Knowledge storage or invoke implementations directly.
8. Errors distinguish invalid query from valid empty traversal.
9. Restart/recovery preserves committed graph state.

## Approval gate

Review with Memory/Knowledge provenance links, Gateway orchestration, scope model, graph identity schema, and end-to-end workflows before implementation.
