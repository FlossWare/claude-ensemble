# Functional Inventory (Draft)

Status: draft for architecture review. This is an inventory and boundary proposal, not an implementation commitment.

## Governing rules

1. Inventory behavior before choosing classes, packages, databases, or processes.
2. Every capability designated as a **service** must expose a language-neutral REST/HTTP API. Internal components and algorithms do not need network endpoints.
3. A service boundary and a deployment/process boundary are different decisions. A service can initially be co-deployed while retaining its own contract.
4. Do not promote an algorithm to a service merely because it has a name. Service designation requires a coherent owner, contract, consumers, state/lifecycle needs, or operational reason. Chunking and tokenization are explicitly designated service candidates because their versioned behavior must be consistent across ingestion, indexing, retrieval, and context budgeting.
5. Consider decorator/composition implementations when defining service contracts.
6. The archived repository is evidence about historical behavior and failure modes, not a specification to preserve.

## Terminology

- **Service**: independently addressable domain/operational responsibility with a REST API and explicit ownership.
- **Capability**: named behavior with defined inputs, outputs, and semantics; may be implemented inside a service.
- **Component**: cohesive internal implementation unit that is not independently addressable.
- **Algorithm/strategy**: replaceable method behind a capability contract, such as BM25 or cosine similarity.
- **Adapter**: translates an external protocol or lifecycle into a CE contract.
- **Orchestration**: coordinates capabilities/services without taking ownership of their domain data.

## Inventory

Designation values are proposals: **Service candidate**, **Capability**, **Component/strategy**, or **Adapter**. They must be confirmed during boundary review.

| ID | Responsibility | Initial designation | Required behavior / questions |
|---|---|---|---|
| F-01 | Client-facing gateway | **Service (required initial boundary)** | Stable public REST entry point; request validation, local deployment restrictions where required, routing, time budgets, and error translation. Generalized authentication and distributed identity are deferred. Must not become the owner of Memory, Knowledge, Graph, or learning state. |
| F-02 | Request orchestration and Query Planning | **Gateway capability; not a standalone service initially** | Gateway selects and coordinates retrieval services under a bounded plan, using intent/entities and bounded query variants. Propagate deadlines/cancellation and report partial failures. Any call to another logical service must use its REST contract. Revisit a separate Query Planning service only with evidence of an independent lifecycle or ownership need. |
| F-03 | Memory lifecycle | **Service (required initial boundary)** | Create, read, update, delete, and retrieve episodic/user/project memory; stable identity, metadata, retention, provenance, access scope, and durable recovery. Define conflict/update semantics. |
| F-04 | Knowledge lifecycle | **Service (required initial boundary)** | Own durable knowledge records and source provenance, lifecycle/status, project/source scope, revisions, and deletion. Decide domain ownership explicitly rather than assuming Memory must own Knowledge. |
| F-05 | Graph data and traversal | **Service (required initial boundary)** | Own nodes/edges, identity, relationship types, queries, traversal limits, consistency, and provenance. Other services consume its REST contract instead of duplicating graph traversal logic. |
| F-06 | Thompson selection | **Service (required initial boundary)** | Own selection arms/context, counts/reward evidence, recommendation/selection operation, update semantics, and persisted state. Distinct from document relevance ranking. |
| F-07 | Learning and outcome capture | **Service (required initial boundary)** | Record outcome/evidence, validate feedback, update learner state, explain which evidence/update was applied, and integrate with Thompson through an explicit contract. Avoid circular ownership. |
| F-08 | Source discovery and ingestion orchestration | **Capability owned by Memory/Knowledge initially; no separate service** | Memory and Knowledge initiate ingestion/update/delete for their own authoritative records and call Chunking, Tokenization, Embedding where applicable, and Index through REST. Elaborate source discovery, scheduling, dry-run/apply orchestration, and independent ingestion lifecycle remain out of initial scope unless a concrete required workflow justifies a separate service. Interrupted work and reconciliation state must remain observable and recoverable. |
| F-09 | Indexing lifecycle and searchable representations | **Service (required initial boundary)** | Own document/chunk revisions, stable index identities, metadata needed for retrieval, indexing/update/deletion lifecycle, readiness, pending work, rebuild/backfill, and recovery. Provide a shared contract consumed by Lexical Retrieval and Vector Retrieval. Ranking consumes candidate results from Gateway orchestration and does not call Index directly. Do not hide indexing lifecycle independently inside Memory and Knowledge. |
| F-10 | Chunking | **Service (approved boundary)** | Expose a language-neutral REST API for deterministic chunking. Define document and policy inputs; deterministic boundaries; configurable size/overlap; heading and source-line provenance; stable chunk identity; chunker/policy version; explicit migration/reindex behavior when policy changes. The service owns chunking semantics and version compatibility, not canonical corpus/index state. Draft contract: [docs/contracts/CHUNKING.md](contracts/CHUNKING.md). |
| F-11 | Tokenization and lexical normalization | **Service (approved boundary)** | Expose a language-neutral REST API for consistent index-time and query-time tokenization/normalization. Preserve identifiers, names, error strings, paths, code symbols, and technical phrases. Return tokenizer/normalizer identity and version so indexes and queries cannot silently drift. Keep lexical tokenization distinct from model-specific subword tokenization and context-window token counting; define those as explicit operations/adapters with model identity and count semantics rather than pretending one tokenizer fits all. Draft contract: [docs/contracts/TOKENIZATION.md](contracts/TOKENIZATION.md). |
| F-12 | Lexical retrieval | **Service (required initial boundary)** | Expose REST candidate retrieval using lexical representations and corpus/index statistics owned by Index. Return stable candidate identities, scores/evidence, scope, revisions, and provenance. Preserve exact identifiers and technical terms. BM25 is a replaceable strategy inside this service, not a service itself. |
| F-13 | Embedding generation | **Service (required initial boundary)** | Expose REST vector generation with model identity/version, dimensions, normalization, batching, deadlines, unavailable-model behavior, and compatibility metadata. Keep model/provider implementation behind the contract. |
| F-14 | Vector retrieval | **Service (required initial boundary)** | Expose REST retrieval of vector-similar candidates. Index owns canonical searchable representations and lifecycle; Vector Retrieval owns candidate selection from vector representations, compatibility checks, scope filtering, and retrieval evidence/provenance. Define missing/stale vectors, dimension mismatch, deletion, rebuild, and model compatibility. Cosine similarity is an algorithm, not a service. |
| F-15 | Intent classification | **Service (required initial boundary)** | Expose REST classification for recall/history, decision, factual lookup, explanation, troubleshooting, relationship exploration, and general query. Return confidence/evidence and a safe fallback; do not make unsupported certainty look like fact. |
| F-16 | Entity and identifier extraction | **Service (required initial boundary)** | Expose REST extraction of entities, IDs, names, paths, and technical phrases. Preserve exact spellings, offsets/context where useful, and uncertainty. Support Graph lookup without silently rewriting identifiers. |
| F-17 | Query planning | **Gateway capability; not a separate service initially** | Use intent/entities to choose relevant sources and a bounded plan. Query expansion is disabled in v1; use the original query only. Reintroduce expansion only with a separately reviewed policy, explicit list identity, and acceptance tests. Calls to retrieval/analysis services use REST. Do not add a standalone Query Planning service by default. |
| F-18 | Candidate fusion, ranking, and deduplication | **Service (required initial boundary)** | Fuse candidates from Lexical Retrieval and Vector Retrieval where candidates are available, deduplicate by stable identity, order them using explicit ranking policy, use deterministic tie-breaking, and return scores/evidence plus policy version. Define behavior when either retrieval path fails or returns no candidates. Ranking owns ordering, not corpus/index state or source retrieval. BM25/cosine/normalization remain strategies, not services. |
| F-19 | Reranking | **Service (required initial boundary)** | Expose REST second-stage assessment of a bounded candidate set. Define inputs, output scores/evidence, model/policy version, deadlines, failure/degradation semantics, and compatibility. Keep specific reranking algorithms/models replaceable behind the service contract. |
| F-20 | Source and project-scope partitioning | Cross-cutting capability owned by relevant domain services | Apply scope partition filters before results are exposed or consume ranking budget. Missing/invalid scope must never broaden the selected partition. Scope selects a data partition and does not establish caller identity. Enforce only local access restrictions required by the initial deployment. |
| F-21 | Prompt-context assembly and compression | Gateway orchestration capability | Compose bounded Memory, Knowledge, and Graph evidence for the prompt hook; preserve source distinctions/provenance; enforce token/size/time budgets; avoid duplicate content; distinguish “no result” from retrieval failure. |
| F-22 | Claude Code hook integration | Adapter | Invoke retrieval during the normal prompt lifecycle and inject relevant context automatically. No manual lookup instruction or special prefix may be required. Fail-open behavior, time budget, diagnostics, and content formatting must be explicit. |
| F-23 | Provenance and evidence | Shared contract/primitives; domain-owned truth | Carry source IDs, document/chunk revisions, source locations, retrieval path, and ranking policy. Shared formats are acceptable; a separate provenance service is not assumed. |
| F-24 | Configuration and policy | Cross-cutting capability | Validate configuration, identify effective profile/version, define defaults and overrides, and expose safe diagnostics. Avoid hidden per-process policy drift. |
| F-25 | Readiness and recovery | Cross-cutting operational behavior, owned per service | Distinguish process health from readiness of required state/dependencies. Surface pending work and fault state; define restart/recovery and degraded behavior. A successful empty search must not disguise an unavailable index. |
| F-26 | Observability and diagnostics | Cross-cutting capability | Correlation IDs, timings, selected sources/strategies, intent/entities where safe, result counts, failure categories, and policy versions. Do not log raw prompt text or memory/knowledge content by default. |
| F-27 | REST contract and errors | Cross-cutting contract rules | All services expose REST/HTTP contracts. Define request/response schemas, validation, error codes, retryability, idempotency, deadlines, cancellation, pagination/limits, and compatibility. Adapters must not fork domain semantics. |
| F-28 | Local access and data isolation | Cross-cutting capability | Define user/project/source data partitioning, secret handling, data exposure, and safe failure. Scope filters are partition semantics, not identity. Only local access restrictions genuinely required by the initial deployment are in scope. Generalized authentication and remote/distributed identity mechanisms are deferred. |
| F-29 | Evaluation and acceptance | Cross-cutting capability/process | Maintain labeled scenarios for recall, identifiers, ambiguity, factual lookup, explanations, troubleshooting, graph relationships, empty results, and degraded dependencies. Measure relevance, false positives, latency, resource use, and recovery. |
| F-30 | Deployment and resource policy | Operational concern | Define service lifecycle, dependencies, resource limits, model provisioning, upgrades, and rollback. Deployment topology is not inferred from logical service boundaries. |

## Scope tiers for the restart

The inventory distinguishes required CE functionality from implementation choices. The services listed below are required logical boundaries; deployment topology remains a separate decision. This list is authoritative for the current draft and overrides any older conditional wording elsewhere in this file.

### Required initial logical services

- **Gateway**: stable REST entry point and bounded request coordination.
- **Memory**: memory lifecycle and retrieval, including automatic prompt-time recall.
- **Knowledge**: sourced knowledge lifecycle and provenance.
- **Graph**: relationship storage and traversal where graph semantics are needed by CE.
- **Thompson**: selection and persisted selection state.
- **Learning**: outcome/feedback capture and learning state.
- **Index**: shared indexing lifecycle and searchable representations, including updates, deletions, revisions, readiness, and recovery. Indexing is a service, not an incidental implementation detail hidden inside Memory or Knowledge.
- **Chunking**: deterministic, versioned chunking through REST.
- **Tokenization and lexical normalization**: consistent, versioned index/query tokenization through REST.
- **Embedding**: generate vectors with explicit model identity/version, dimensions, normalization, batching, and failure semantics.
- **Lexical Retrieval**: retrieve lexical candidates using Index-owned corpus statistics and indexed representations; BM25 remains an internal strategy.
- **Vector Retrieval**: retrieve candidates by vector similarity while respecting index revisions, model compatibility, scope, and provenance.
- **Intent Classification**: classify request intent with confidence and evidence for retrieval planning.
- **Entity and Identifier Extraction**: identify entities, exact identifiers, paths, names, and technical phrases while preserving spelling and uncertainty.
- **Ranking**: shared candidate fusion, ordering, and deduplication with explainable evidence. It does not own corpus/index state or perform source retrieval.
- **Reranking**: independently assess a bounded candidate set as a second-stage operation.

These 16 entries are logical service boundaries, not a mandate for separate processes. Each service has a REST contract, a clear owner, consumers, failure/readiness semantics, and acceptance tests. Co-deployment is allowed.

**Required Gateway capabilities (not additional services):** Query Planning selects retrieval sources and constructs bounded query plans, including controlled query expansion. Prompt-context assembly/compression and provider prompt-cache optimization also belong to Gateway orchestration/provider adaptation.

### Required behavior, not additional services

- Prompt-time hook integration and bounded context assembly.
- Source/project-scope enforcement and provenance.
- Request validation, configuration, health/readiness, diagnostics, and recovery.
- A basic retrieval path that can find and rank useful candidates from the initial corpus.
- Acceptance tests proving normal prompt-time memory injection works without a special prefix or user reminder.

These are capabilities, adapters, or cross-cutting rules owned by the relevant services. They do not automatically become standalone services.

### Conditional capabilities

- Source discovery and elaborate ingestion orchestration beyond the minimum needed to populate and maintain the index.
- Model-specific subword tokenization and context-window token counting, which are distinct from the existing lexical Tokenization service.
- Additional retrieval strategies or advanced ranking algorithms not required by the agreed retrieval flows.

A conditional capability is not silently in scope just because it could be useful; but the services listed above are explicitly part of the intended CE capability set.

### Not separate services by default

BM25, cosine similarity, score normalization, and individual index structures are algorithms or implementation strategies, not services by themselves. Exact-identifier matching is a Ranking contract guarantee and does not require a separate service. Query expansion is deferred in v1. Observability, configuration, security, and provenance are cross-cutting responsibilities, not standalone services by default.

Ranking and Reranking are distinct services: Ranking performs shared candidate fusion/order/deduplication; Reranking applies a separately specified second-stage candidate assessment. Index owns indexing lifecycle and searchable representations; Lexical Retrieval and Vector Retrieval own their respective candidate retrieval paths; Embedding owns vector generation. Query Planning remains inside Gateway orchestration.

Alerting and messaging are outside the initial scope unless a concrete required workflow demonstrates otherwise. Avoid building a generalized enterprise-search pipeline before CE's required user flows demand one.

## Required end-to-end flows

### A. Prompt-time conversational recall

1. The normal Claude Code prompt lifecycle invokes the hook automatically.
2. The adapter sends a bounded request to CE without requiring user syntax or a manual reminder.
3. Query understanding identifies likely intent and preserves entities/identifiers.
4. Planning queries appropriate Memory, Knowledge, and Graph sources within deadline and result budgets.
5. Retrieval returns candidates with stable identity and provenance.
6. Ranking/fusion deduplicates and protects exact matches.
7. Context assembly respects budget and emits source-aware evidence.
8. Diagnostics distinguish no relevant result from service/index failure.
9. Tests prove that previously stored relevant memories are injected and the assistant does not falsely claim memory is absent.

### B. Ingestion to retrieval

1. Accept content and apply source/scope policy; elaborate discovery orchestration is conditional.
2. Extract source revision and normalize content deterministically.
3. Chunk with the versioned Chunking service and stable IDs/provenance.
4. Update the Index service consistently, including revisions and deletions.
5. Record pending work, component versions, and readiness.
6. Recover interrupted operations and reconcile stale/deleted chunks.
7. Retrieve candidates through Lexical Retrieval and Vector Retrieval as appropriate to the query and available representations.
8. Send the combined candidate set to Ranking, then the bounded top set to Reranking where configured, and return ordered results with provenance. A failed retrieval path must be distinguishable from a successful empty result.

### C. Learning and selection

1. Record outcome evidence with identity and provenance.
2. Validate and persist evidence idempotently.
3. Update learning/Thompson state through explicit contracts.
4. Return selection/recommendation with policy/state version and traceable evidence.
5. Test duplicate feedback, interrupted updates, restart recovery, and concurrent updates.

## Acceptance requirements before implementation

- Each inventory row has an agreed designation, owner, contract or explicit reason no separate contract is needed, dependencies, failure behavior, and acceptance tests.
- Every service has a REST API contract, even if co-deployed with other services.
- Capability/algorithm boundaries are not confused with deployment boundaries.
- The initial retrieval path has explicit acceptance tests for useful recall, identifier preservation, deduplication, provenance, empty results, and graceful degradation across lexical and vector retrieval. Embedding, Intent Classification, Entity and Identifier Extraction, Ranking, and Reranking are required logical services; Query Planning remains Gateway orchestration.
- Automatic prompt-time recall is tested through the installed Claude Code hook with real conversational recall.
- Indexing/retrieval acceptance covers deterministic chunking, revision changes, deletion, fresh-process recovery, failure injection, stale/pending index state, embedding model/dimension incompatibility, and graceful degradation when either retrieval path is unavailable.
- Resource/latency acceptance reflects shipped service limits and concurrent Memory/Knowledge work, not just unit tests.
- No implementation starts until the inventory and boundary decisions are reviewed.


## Additional required prompt-budget capabilities

- **Prompt compression** is a required capability owned by Gateway's prompt-context assembly/orchestration. It reduces tokens while preserving facts, decisions, constraints, exact identifiers, and provenance. It must not silently alter meaning. It is not a generic data-compression service.
- **Provider prompt-cache optimization** is a required Gateway/provider-adapter capability. Keep stable prompt prefixes separate from dynamic context where the provider supports caching. Treat caching as a cost/latency optimization, never as the source of truth or a correctness dependency.
- Acceptance tests must compare compressed context with its source evidence for preservation of key facts/identifiers and must verify that cache use/failure does not change response semantics.
