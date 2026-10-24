# Graph Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Own graph nodes, edges, relationship types, identity, provenance, mutation lifecycle, and bounded traversal. Graph is authoritative for relationship data only; it does not own canonical Memory/Knowledge source content or perform lexical/vector retrieval.

## Endpoints

- GET /api/v1/graph/operations/{operation_id}: durable projection/traversal operation status, including retry/reconciliation state.
- POST /api/v1/graph/reconciliation: accept an owner-led, bounded page of source projection events/tombstones for recovery.

Projection/traversal success returns `200 OK`; accepted asynchronous projection returns `202 Accepted`; invalid schema returns `400`; source/version conflict returns `409`; oversized payload returns `413`; missing operation returns `404`; unavailable/deadline errors use the common envelope.

- POST /api/v1/graph/nodes: create or upsert a node under explicit idempotency semantics.
- GET /api/v1/graph/nodes/{node_id}: direct node lookup.
- POST /api/v1/graph/edges: create or upsert an edge.
- DELETE /api/v1/graph/edges/{edge_id}: remove/tombstone an edge.
- POST /api/v1/graph/traversals: bounded traversal/query.
- POST /api/v1/graph/source-projections: idempotently upsert graph facts derived from one canonical source revision.
- POST /api/v1/graph/source-deletions: tombstone graph facts derived from a source identity/revision.
- GET /api/v1/graph/health and GET /api/v1/graph/ready.

Node/edge schemas and identity rules below are normative for the initial contract. Memory and Knowledge are the source-projection writers for relationships derived from their canonical records; they call Graph through REST after extraction/validation. Graph does not call either owner.

## Source projection schemas

The normative machine-checkable schema is [`schemas/graph.schema.json`](schemas/graph.schema.json). `source_id` uses the common opaque owner-prefixed grammar. All source-derived facts carry a set of supports, each `(source_id, revision_sequence, source_revision)`; identical relationships supported by multiple sources are one logical relationship with multiple independent supports. Deleting one source removes only that source's support; the relationship remains while any current support remains.

`POST /api/v1/graph/source-projections` request fields: `operation_id`, `source_id`, opaque `source_revision`, monotonic `revision_sequence`, canonical `scope`, and bounded arrays of nodes/edges. Each edge has stable `edge_id`, `source_node_id`, `target_node_id`, `relationship_type`, directionality, and provenance. Response returns `operation_id`, accepted source revision/sequence, status, and `request_id`.

`POST /api/v1/graph/source-deletions` request fields: `operation_id`, `source_id`, tombstone `revision_sequence`, scope, and delete scope (`source` or `revision`). The tombstone sequence must exceed prior source revisions. Response reports durable tombstone status. Stale projections at or below the tombstone sequence are rejected.

## Semantics

- Node and edge identity are stable and explicitly scoped. Edge type, directionality, source/target identity, provenance, validity/lifecycle, and timestamps are represented explicitly. Every source-derived graph fact carries `source_id`, `source_revision`, and `revision_sequence`.
- Mutations are idempotent; same idempotency key with different payload conflicts. Concurrent updates have a documented version/conflict rule.
- Traversal requests specify start nodes, allowed edge types/directions, maximum depth, maximum visited nodes, maximum returned paths/results, and deadline. No unbounded graph walks.
- Results include provenance and enough revision/status metadata to distinguish current relationships from stale references to source records. Source-projection writes are idempotent by operation ID and source revision. Source deletion tombstones all facts derived from that source; delayed projections at or below the source tombstone sequence are rejected. Tombstone high-water marks survive cleanup and rebuild.
- Graph does not implicitly fetch Memory/Knowledge content. Callers use those services' REST contracts when canonical source data is needed.
- Scope partition filtering is enforced on reads, writes, and traversals. Scope is not an authorization model.
- Traversal ordering and tie-breaking are deterministic for fixed graph state and policy when applicable. Cycles and duplicate paths are handled explicitly.
- Do not log sensitive node/edge properties by default. Propagate correlation, deadlines, cancellation, and bounded retry semantics.

## Errors

Use the common error envelope. Distinguish invalid node/edge, missing endpoint node, invalid scope partition or required local access restriction failure, idempotency/version conflict, traversal limit exceeded, deadline exceeded, and unavailable/internal failure.

## Acceptance tests

1. Node/edge identity, directionality, and relationship types are explicit.
2. Two sources support the same relationship; deleting one source removes only that support and preserves the relationship while the other support is current.
3. A path with any stale/tombstoned support is not returned as current; Gateway verifies each source support before exposing the path.
2. Idempotent mutation and concurrent conflict behavior are tested.
3. Traversal depth/node/result/time limits are enforced.
4. Cycles and duplicate paths cannot cause unbounded work.
5. Scope authorization is enforced server-side.
6. Results preserve provenance and expose stale source references.
7. Graph does not access Memory/Knowledge storage or invoke implementations directly.
8. Errors distinguish invalid query from valid empty traversal.
9. Restart/recovery preserves committed graph state.
10. Single-process tests do not claim federation safety.

## Isolated testing

Graph MUST be testable alone with its persistence adapter isolated and with owner calls mocked at REST boundaries; Graph does not call owners for traversal or deletion. Test projection idempotency, multiple supports, source-specific tombstone, stale retry, partial-path staleness, status recovery, traversal bounds, and schema/error behavior without Memory/Knowledge running.

## Approval gate

Review with Memory/Knowledge provenance links, Gateway orchestration, scope model, graph identity schema, and end-to-end workflows before implementation.
