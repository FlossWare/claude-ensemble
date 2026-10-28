# Graph library evaluation

Status: decision for the initial CE Graph runtime slice.

## Decision

Use **NetworkX 3.5** for the in-memory graph representation and standard graph traversal/path algorithms. Keep the existing SQLite-backed source-support and owner-reconciliation model. Do not build a general-purpose graph engine inside CE.

## Contract fit

The Graph REST contract requires directed and undirected relationship traversal, scope isolation, deterministic bounded path results, source-specific relationship supports, and durable owner-led replay. NetworkX supplies graph data structures and established traversal/path algorithms, but it does not own any of those CE domain guarantees.

The runtime constructs the NetworkX graph only after filtering SQLite rows by the exact canonical scope and applying the contract's relationship-direction rules. CE continues to enforce:

- source-supported nodes and relationships, tombstones, revision watermarks, and idempotency;
- scope filtering before graph construction;
- stable support/provenance payloads and deterministic edge choice;
- maximum depth, visited-node count, path count, and materialized-edge bounds;
- SQLite persistence, owner journal replay, checkpoints, and readiness;
- the public REST contract and error behavior.

The in-memory graph is a query structure, not canonical storage. It is rebuilt from bounded, scoped persisted rows for each traversal. This avoids a second mutable state representation that could diverge from SQLite after a restart or failed projection.

## Candidates

| Library | Assessment |
|---|---|
| NetworkX | Selected. Pure Python, mature, broad graph traversal support, BSD-3-Clause license, and a low-friction fit for the current bounded CE workloads. |
| rustworkx | Not selected for the initial slice. Worth benchmarking only if representative CE workloads show NetworkX is too slow; adds a compiled dependency and different graph/index semantics. |
| igraph | Not selected. Strong analysis capabilities, but broader than the current service needs and introduces additional API/licensing review without demonstrated benefit. |

## Trade-offs and safeguards

NetworkX is not a graph database and does not provide persistence or distributed transactions. That is acceptable: SQLite remains the durable store and CE's owner-journal protocol remains authoritative. NetworkX's path enumeration can grow rapidly, so the runtime bounds the scoped graph, traversal depth, and total emitted paths. These limits are part of the CE contract and must not be delegated to library defaults.

## Validation required

The Graph runtime tests must pass through the service boundary for directionality, scope isolation, deterministic paths, depth/node/path limits, source support preservation, tombstones, and restart/reconciliation behavior. CI is the validation source; the library selection alone does not make the Graph service accepted.
