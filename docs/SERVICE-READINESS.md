# CE Service Readiness Audit

Audit date: 2026-10-28
Audited baseline: `main` at the time of review.
Purpose: distinguish implemented algorithms, reachable REST services, durable domain services, and contract-level acceptance. A module or endpoint alone is not evidence that a service is complete.

## Readiness definitions

- **Implemented slice**: code and tests exist for a bounded subset of the contract.
- **Partial / not contract-complete**: some endpoints and behavior exist, but required lifecycle, durability, recovery, or acceptance is missing.
- **Not implemented**: no runtime module and no corresponding REST route were found on the audited baseline.
- **Blocked / fail-closed**: the implementation intentionally refuses a safety-critical operation rather than pretending the workflow is complete.

## Service matrix

| Service / capability | Baseline evidence | Readiness | Dependency / next acceptance |
|---|---|---|---|
| REST dispatcher and bounded worker pool | `runtime/server.py`; dispatcher saturation tests | Implemented slice | Keep internal REST capacity isolation; add service-specific readiness and full workflow acceptance. |
| Chunking | `runtime/chunking.py`, `tests/test_chunking_runtime.py` | Implemented slice | Verify the approved contract and deterministic/provenance behavior in full ingestion tests. |
| Tokenization | `runtime/tokenization.py`, `tests/test_tokenization_runtime.py` | Implemented slice | Verify pinned profile compatibility across ingestion and query paths. |
| Embedding | `runtime/embedding.py`, real-model CI validation | Implemented slice | Keep pinned local model validation and explicit readiness; validate document/query vectors through actual REST workflows. |
| Intent classification and entity extraction | Runtime modules and individual tests | Implemented slice | Gateway planning does not yet consume them because Gateway request orchestration is absent. |
| Ranking and reranking | Runtime modules and individual tests | Implemented slice | Validate identity/provenance preservation and fallback behavior through the Gateway workflow. |
| Lexical and vector retrieval | `runtime/retrieval.py`, REST routes, unit tests | Implemented slice | Algorithms exist, but there is no public Gateway request path that plans, fans out, fuses, freshness-checks, and assembles context end to end. |
| Index | `runtime/index.py`, extensive persistence, manifest, generation and fence tests | Partial / deliberately fail-closed | Generation cutover is explicitly disabled until owner-journal replay and reconciliation are integrated. Do not weaken this gate. |
| Memory | `runtime/memory.py`, HTTP and restart tests; Memory-to-Index ingestion slice | Partial | Canonical CRUD and a Memory-to-Index path exist. Graph projection/deletion and owner-journal reconciliation are not wired; delete status can remain pending graph. Readiness/recovery claims need to reflect this. |
| Knowledge | Contract and schema exist; no `runtime/knowledge.py` or Knowledge routes found | Not implemented | Required owner for sourced knowledge, with canonical revisions, ingestion journal, Index lifecycle, Graph projection, deletion, and restore reconciliation. |
| Graph | `runtime/graph.py`, Graph REST routes, SQLite owner/event journals, traversal and replay tests | Implemented slice (partial / not contract-complete) | Source projections, tombstones, bounded traversal, and local replay watermarks exist. Memory/Knowledge owner journals and end-to-end recovery are not wired. Until Knowledge is implemented, operators must checkpoint `knowledge` at sequence 0 for overall Graph readiness; remove this bootstrap step only when readiness semantics explicitly support an absent owner. |
| Thompson | Contract and schema exist; no runtime module or routes found | Not implemented | Persisted selection and reward semantics; implement before Learning. |
| Learning | Contract and schema exist; no runtime module or routes found | Not implemented | Durable feedback/outcome processing that calls Thompson through REST; depends on Thompson. |
| Gateway / request lifecycle / RAG | Contract exists; no `POST /api/v1/requests` route or Gateway runtime found | Not implemented | Depends on real Memory/Knowledge, Index and retrieval contracts, plus Graph for relationship retrieval. Must be an orchestrator, not a domain-state owner. |
| Durable execution history | Issue #22 remains open; no complete Gateway request journal found | Not implemented | Must record bounded request/execution status and enable safe retry/reconciliation before client adapters are considered complete. |
| MCP and client hooks | No MCP adapter found | Not implemented | Downstream of a stable Gateway API and defined request lifecycle. |
| Source-ingestion adapters | PR #31 adds a draft implementation on its branch, not `main` | Review in progress | Keep draft until the domain owner lifecycle and end-to-end acceptance path are real. |
| Installer and release acceptance | Issues #23 and #25 remain open | Not release-ready | Finish only after required services, durable workflows, and real-model checks pass. |

## Dependency order

1. **Complete the owner/data plane before building Gateway orchestration.** Memory and Index have a useful initial slice, but their integration is incomplete. Knowledge is absent, and Graph is a dependency of both owners' specified write/delete/recovery workflows.
2. **Implement Graph as a real durable service**, with source-supported node/edge facts, idempotent projections and tombstones, contiguous per-owner projection watermarks, bounded traversal, and restart tests. Memory/Knowledge must call it through REST; Graph must not call source owners.
3. **Implement Knowledge** using the owner lifecycle and recovery patterns proven by Memory, without copying Memory's domain model blindly. It must own source identity, revisions, provenance, deletion, and its own durable downstream-operation journal.
4. **Close Memory and Index integration gaps**: owner projection journals, Graph operations, owner reconciliation/fences, restore barriers, and explicit readiness. Preserve Index's fail-closed generation cutover.
5. **Implement Thompson, then Learning**, with durable idempotency, concurrency and restart acceptance.
6. **Build Gateway request orchestration** once the required owners and retrieval contracts are usable. Begin with a narrow end-to-end RAG path, then add Graph, optional reranking, bounded context assembly, and freshness verification. Every logical service call remains REST even in one process.
7. **Add durable Gateway execution history**, then MCP/hooks as thin adapters over Gateway. Finish installer and release acceptance last.

## Release gates

- Every required service has a REST contract, reachable routes, schema/error conformance, durable state where required, and restart/replay tests.
- Cross-service calls use REST, not direct calls into another service's implementation or storage.
- Memory and Knowledge writes/deletes expose durable operation identities and truthful downstream status.
- No candidate is returned as current without canonical freshness verification; dependency failure must degrade or fail closed rather than become a false no-match.
- Index generation cutover remains disabled until owner journals, sealed reconciliation checkpoints, write fencing, and recovery reconciliation are implemented and tested end to end.
- Gateway request acceptance proves a real request through planning, parallel retrieval, fusion/reranking policy, canonical freshness verification, bounded context assembly, provenance, deadline handling, and partial-failure behavior.
- MCP/hooks are not release substitutes for missing Gateway behavior.
- SonarCloud/SonarQube is explicitly outside this workstream until the user asks to revisit it.

## Immediate implementation target

The first Graph runtime slice is now in this branch, but it is not yet fully accepted: owner projection journals and restart replay are still missing. The next code milestone is **wire Memory's durable Graph projection/deletion journal, then implement Knowledge's matching owner lifecycle and recovery**. The current Memory implementation creates canonical records and publishes Index representations, but does not yet submit source-supported Graph projections/deletions or reconcile Graph recovery. Implementing Gateway first would only hide this missing dependency behind orchestration code.
