# Graph Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Own graph nodes, edges, relationship types, identity, provenance, mutation lifecycle, and bounded traversal. Graph is authoritative for relationship data only; it does not own canonical Memory/Knowledge source content or perform lexical/vector retrieval. Source identifiers follow the shared namespaced opaque-ID grammar in `REST-CONTRACT.md`.

## Endpoints

- Direct node/edge CRUD endpoints are deferred from v1; source-derived graph facts are written only through the canonical source-projection workflow.
- POST /api/v1/graph/traversals: bounded traversal/query.
- POST /api/v1/graph/source-projections: idempotently upsert graph facts derived from one canonical source revision.
- POST /api/v1/graph/source-deletions: tombstone graph facts derived from a source identity/revision.
- GET /api/v1/graph/operations/{operation_id}: query projection/deletion status.
- GET /api/v1/graph/sources/manifest: bounded source revision/tombstone manifest for reconciliation.
- POST /api/v1/graph/reconciliation/checkpoints: owner-pushed checkpoint declaring the sealed graph-projection journal sequence after replay.
- GET /api/v1/graph/health and GET /api/v1/graph/ready.

Node/edge identity and support schemas below are normative. Memory and Knowledge are the source-projection writers for relationships derived from canonical records; they call Graph through REST after extraction/validation. Graph does not call either owner. V1 exposes source projection/deletion, bounded traversal, operation status, manifest, owner reconciliation checkpoints, and health/readiness only; standalone node/edge CRUD is deferred.

## Source projection schemas

`POST /api/v1/graph/source-projections` request fields: `operation_id`, `source_id`, opaque `source_revision`, monotonic `revision_sequence`, owner-local monotonic `owner_projection_sequence`, canonical `scope`, and bounded arrays of nodes/edges. Each node may carry up to 32 normalized `aliases` in addition to `label`. Each edge has stable `edge_id`, `source_node_id`, `target_node_id`, `relationship_type`, directionality, and provenance. Response returns `operation_id`, accepted source revision/sequence, status, and `request_id`.

`POST /api/v1/graph/source-deletions` request fields: `operation_id`, `source_id`, tombstone `revision_sequence`, owner-local monotonic `owner_projection_sequence`, scope, and `delete_scope=source`. V1 supports source-wide tombstones only; revision-specific deletion is unsupported. The tombstone sequence must exceed prior source revisions. Response reports durable tombstone status. Stale projections at or below the tombstone sequence are rejected.

## Semantics

- V1 normalized relationship identity is `(scope.type, scope.id, scope.visibility, source_node_id, target_node_id, relationship_type, directed)`. For `directed=true`, preserve source/target order. For `directed=false`, sort the two endpoint IDs by Unicode code-point order and use the smaller as `source_node_id` and larger as `target_node_id` before forming the tuple. Normalize `relationship_type` to Unicode NFC without case-folding; its case remains significant. The canonical traversal `edge_id` is `rel:` plus lowercase hexadecimal SHA-256 of RFC 8785 canonical JSON for that normalized tuple. The `edge_id` supplied by each owner is source-local and appears as `source_edge_id` on that support; it is not part of cross-source fact identity. Two sources asserting the same tuple create one relationship fact with separate source supports, even if their source-local edge IDs differ. Edge properties are support-specific evidence and do not alter relationship identity in v1. Each support is `(source_id, source_revision, revision_sequence, source_edge_id, scope)`; two sources asserting the same relationship create two supports, not one untraceable fact.
- Node and edge facts are source-supported projections. Every projected node label, node type, alias, and node property is stored with the same source identity, source revision, revision sequence, and scope as its projection. An attribute/alias is eligible only while its own support is current. If multiple sources support a node, removing or superseding one source removes only that source's node-attribute and edge supports; it does not remove another source's support. Conflicting labels/types are exposed as supported alternatives in deterministic order rather than resolved by last-writer-wins. Entity mention resolution matches only current supported labels/aliases in the requested scope. A node is traversable only while at least one current source support remains. A traversal result must include each edge's stable identity and bounded `supports` array. A stale or unverified support is excluded individually; a path remains eligible only if every edge retains at least one independently verified current support. Stale support is never used as evidence that a path is current. Graph recovery is owner-led: Memory and Knowledge replay their own durable graph-projection journals through the existing Graph projection/deletion REST endpoints. Each Graph event carries an owner-local monotonic `owner_projection_sequence`; Graph records idempotent sequence/payload identity and advances only a contiguous terminal watermark for each owner. After replaying through its sealed journal sequence, the owner calls `POST /api/v1/graph/reconciliation/checkpoints` with `owner` and `sealed_projection_sequence`. Graph reports `ready=true` only when its contiguous terminal watermark reaches the declared sequence for both owners. A gap or lower watermark returns `409 graph_replay_incomplete` and Graph remains not-ready. The manifest exposes per-owner terminal watermarks and readiness. Graph never calls back into source owners. Each support carries `source_id`, `source_revision`, `revision_sequence`, scope, and provenance.
- A returned path is eligible only when every edge in the path has at least one non-tombstoned support in the requested scope. `POST /api/v1/graph/traversals` returns `{scope, resolved_start_node_ids, unresolved_entity_mentions, paths:[{path_id,node_ids,edges:[{edge_id,source_node_id,target_node_id,relationship_type,directed,supports}]}],truncated,request_id}`. V1 does not support pagination or `next_page_token`; requests containing a page token are invalid. Each edge's `supports` list is bounded to 100, and the whole traversal response is bounded to 10 paths in Gateway v1 (Graph's service-level hard maximum is 10). Each support includes the owner's original `source_edge_id`. Gateway verifies unique support identities against canonical owners before returning Graph evidence. It retains an edge only when at least one support verifies current in the requested scope, and retains a path only when every edge remains eligible. An owner outage makes that support unverified; other independently verified supports may keep the edge eligible. If no edge support remains verified, omit the edge/path and mark the response degraded. If any edge in a path has no current support, omit the path. If a path contains multiple supports for an edge, include only current support evidence; never let one stale support make a path current when no current support remains. Graph never calls Memory/Knowledge to verify freshness; owner-issued projections and tombstones plus revision high-water marks govern its derived state. Gateway canonical verification remains the final response freshness gate.
- Source projection and deletion operations are idempotent and status-queryable through `GET /api/v1/graph/operations/{operation_id}`. Reusing an owner projection sequence with a different operation/payload returns `409 revision_conflict`; retries of the same operation and sequence return the original result. Graph retains durable source revision/tombstone watermarks and exposes a paginated `GET /api/v1/graph/sources/manifest` for owner/operator reconciliation. V1 recovery rebuild is owner-led: Memory and Knowledge replay their durable source projection journals; Graph reports its own manifest/watermarks and does not call back into owners. Memory and Knowledge replay their own graph projections and tombstones; Graph never calls back into them.

- Node and edge identity are stable and explicitly scoped. Edge type, directionality, source/target identity, provenance, validity/lifecycle, and timestamps are represented explicitly. Every source-derived graph fact carries `source_id`, `source_revision`, and `revision_sequence`.
- Mutations are idempotent; same idempotency key with different payload returns `409 idempotency_conflict`. For a given `source_id`, a projection with a lower `revision_sequence` than the highest accepted source sequence is rejected as `409 revision_conflict`; an equal sequence is idempotent only for the same source revision and canonical projection payload, otherwise it returns `409 revision_conflict`. A source-wide tombstone advances the source high-water mark and rejects all later-arriving projections at or below it.
- Traversal requests specify either `start_node_ids` or `entity_mentions` (exactly one), optional `relationship_types`, `direction` (`outgoing`, `incoming`, or `both`; default `both`), maximum depth (default 3), maximum visited nodes (default 500), maximum returned paths (default 10), and deadline. When `entity_mentions` is supplied, Graph resolves each mention against `label` and `aliases` in the requested scope using Unicode NFC normalization and case folding with exact whole-string equality; substring matches are not accepted. Each mention resolves to at most 4 node IDs, ordered by `node_id` ascending; unmatched mentions are returned in `unresolved_entity_mentions`. The response always includes `resolved_start_node_ids`. Gateway v1 caps relationship traversal at depth 3 and 10 paths, and verifies at most 100 unique support identities per request; paths exceeding those limits are omitted and `truncated=true` rather than bypassing freshness verification. No unbounded graph walks.
- Results include provenance and enough revision/status metadata to distinguish current relationships from stale references to source records. Source-projection writes are idempotent by operation ID and source revision. Source deletion tombstones all facts derived from that source; delayed projections at or below the source tombstone sequence are rejected. Tombstone high-water marks survive cleanup and rebuild.
- Graph does not implicitly fetch Memory/Knowledge content. Callers use those services' REST contracts when canonical source data is needed.
- Scope partition filters are applied server-side on reads, writes, and traversals. Only local access restrictions required by the deployment apply; scope selects a data partition and does not establish caller identity.
- Traversal is deterministic: breadth-first by increasing path depth; start nodes sort by normalized label then `node_id`; neighbors sort by the next visited `node_id`, then canonical `edge_id`; paths within a depth sort by the lexicographic `node_ids` sequence and then the canonical edge-tuple sequence `(source_node_id, target_node_id, relationship_type, directed, edge_id)`. For outgoing directed traversal the next node is `target_node_id`; for incoming directed traversal it is `source_node_id`; for undirected traversal it is the endpoint other than the current node. Supports within an edge sort by `source_id` ascending, `revision_sequence` descending, then `source_edge_id` ascending. Ordering is computed after stale/unverified supports are filtered and must not depend on insertion order. Do not revisit a node already present in the current path. Emit each `node_ids` sequence once; duplicate paths are removed before applying the path limit. Cycles terminate through the per-path visited-node set. V1 defaults when omitted: `max_depth=3`, `max_visited_nodes=500`, `max_paths=10`; all limits are hard-capped by those same values.
- Do not log sensitive node/edge properties by default. Propagate correlation, deadlines, cancellation, and bounded retry semantics.

## Machine-checkable schemas

The normative Graph request/response JSON Schema is in [`schemas/graph.schema.json`](schemas/graph.schema.json). Its `x-endpoints` map binds every endpoint to request/response definitions, success status, error envelope, and permitted error statuses. It defines projection/deletion sequence identity, traversal/support/path results, reconciliation checkpoints, and operation status.

## Endpoint status codes

- Node/edge/traversal successful reads or synchronous operations: `200`.
- Accepted source projection/deletion: `202` with `operation_id`; query status through the operation endpoint (`200`).
- Owner reconciliation checkpoint: `200` when the sealed sequence is fully applied; `409 graph_replay_incomplete` when a sequence gap remains. `GET /api/v1/graph/ready` returns not-ready while recovery replay checkpoints are incomplete. A delete operation is `complete` only when every support for that source is retrieval-ineligible; physical cleanup may finish asynchronously.
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
