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
- GET /api/v1/graph/health and GET /api/v1/graph/ready.

Exact node/edge schema and identity rules must be finalized before implementation.

## Semantics

- Node and edge identity are stable and explicitly scoped. Edge type, directionality, source/target identity, provenance, validity/lifecycle, and timestamps are represented explicitly.
- Mutations are idempotent; same idempotency key with different payload conflicts. Concurrent updates have a documented version/conflict rule.
- Traversal requests specify start nodes, allowed edge types/directions, maximum depth, maximum visited nodes, maximum returned paths/results, and deadline. No unbounded graph walks.
- Results include provenance and enough revision/status metadata to distinguish current relationships from stale references to source records.
- Graph does not implicitly fetch Memory/Knowledge content. Callers use those services' REST contracts when canonical source data is needed.
- Scope authorization is enforced server-side on reads, writes, and traversals. Caller-supplied filters cannot expand authorization.
- Traversal ordering and tie-breaking are deterministic for fixed graph state and policy when applicable. Cycles and duplicate paths are handled explicitly.
- Do not log sensitive node/edge properties by default. Propagate correlation, deadlines, cancellation, and bounded retry semantics.

## Errors

Use the common error envelope. Distinguish invalid node/edge, missing endpoint node, authorization failure, idempotency/version conflict, traversal limit exceeded, deadline exceeded, and unavailable/internal failure.

## Acceptance tests

1. Node/edge identity, directionality, and relationship types are explicit.
2. Idempotent mutation and concurrent conflict behavior are tested.
3. Traversal depth/node/result/time limits are enforced.
4. Cycles and duplicate paths cannot cause unbounded work.
5. Scope authorization is enforced server-side.
6. Results preserve provenance and expose stale source references.
7. Graph does not access Memory/Knowledge storage or invoke implementations directly.
8. Errors distinguish invalid query from valid empty traversal.
9. Restart/recovery preserves committed graph state.
10. Single-process tests do not claim federation safety.

## Approval gate

Review with Memory/Knowledge provenance links, Gateway orchestration, scope model, graph identity schema, and end-to-end workflows before implementation.
