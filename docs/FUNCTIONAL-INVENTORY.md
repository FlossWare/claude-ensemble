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
| F-01 | Client-facing gateway | Service candidate | Stable public REST entry point; authentication/policy boundary as required; request validation, routing, time budgets, and error translation. Must not become the owner of Memory, Knowledge, Graph, or learning state. |
| F-02 | Request orchestration | Capability, possibly gateway component | Selects and coordinates retrieval sources/capabilities under a bounded plan; cancellation/deadlines propagate; partial failures are explicit. Decide whether any independent lifecycle justifies a separate service. |
| F-03 | Memory lifecycle | Service candidate | Create, read, update, delete, and retrieve episodic/user/project memory; stable identity, metadata, retention, provenance, access scope, and durable recovery. Define conflict/update semantics. |
| F-04 | Knowledge lifecycle | Service candidate | Own durable knowledge records and source provenance, lifecycle/status, project/source scope, revisions, and deletion. Decide domain ownership explicitly rather than assuming Memory must own Knowledge. |
| F-05 | Graph data and traversal | Service candidate | Own nodes/edges, identity, relationship types, queries, traversal limits, consistency, and provenance. Other services consume its REST contract instead of duplicating graph traversal logic. |
| F-06 | Thompson selection | Service candidate | Own selection arms/context, counts/reward evidence, recommendation/selection operation, update semantics, and persisted state. Distinct from document relevance ranking. |
| F-07 | Learning and outcome capture | Service candidate | Record outcome/evidence, validate feedback, update learner state, explain which evidence/update was applied, and integrate with Thompson through an explicit contract. Avoid circular ownership. |
| F-08 | Source discovery and ingestion orchestration | Service candidate or capability | Enumerate sources, plan ingestion, support dry-run/apply, reconcile changes/deletions, expose progress and failures, and recover interrupted work. Separate service only if lifecycle/scheduling/operational ownership warrants it. |
| F-09 | Indexing lifecycle and searchable representations | **Service (required initial boundary)** | Own document/chunk revisions, stable index identities, metadata needed for retrieval, indexing/update/deletion lifecycle, readiness, pending work, rebuild/backfill, and recovery. Provide a shared contract consumed by retrieval and ranking. Do not hide indexing lifecycle independently inside Memory and Knowledge. |
| F-10 | Chunking | **Service (approved boundary)** | Expose a language-neutral REST API for deterministic chunking. Define document and policy inputs; deterministic boundaries; configurable size/overlap; heading and source-line provenance; stable chunk identity; chunker/policy version; explicit migration/reindex behavior when policy changes. The service owns chunking semantics and version compatibility, not canonical corpus/index state. Draft contract: [docs/contracts/CHUNKING.md](contracts/CHUNKING.md). |
| F-11 | Tokenization and lexical normalization | **Service (approved boundary)** | Expose a language-neutral REST API for consistent index-time and query-time tokenization/normalization. Preserve identifiers, names, error strings, paths, code symbols, and technical phrases. Return tokenizer/normalizer identity and version so indexes and queries cannot silently drift. Keep lexical tokenization distinct from model-specific subword tokenization and context-window token counting; define those as explicit operations/adapters with model identity and count semantics rather than pretending one tokenizer fits all. Draft contract: [docs/contracts/TOKENIZATION.md](contracts/TOKENIZATION.md). |
| F-12 | Lexical retrieval | Capability | Retrieve lexical candidates with evidence and stable identities. Preserve exact identifiers and technical terms. Corpus statistics and index ownership come from the canonical index. BM25 is a strategy, not automatically a service. |
| F-13 | Embedding generation | Capability; service only if justified | Define model identity/version, vector dimensions, normalization, batch behavior, timeout, unavailable-model behavior, and compatibility checks. Independent service only if shared lifecycle, consumers, scaling, or resource isolation justify it. |
| F-14 | Vector persistence and similarity retrieval | Capability; service-boundary review required | Store/query vectors consistently with canonical document/chunk revisions and embedding model identity. Define missing/stale vectors, dimension mismatch, deletion, rebuild, and similarity evidence. Cosine similarity is an algorithm, not automatically a service. |
| F-15 | Intent classification | Capability; service-boundary review required | Explicitly classify at least recall/history, decision, factual lookup, explanation, troubleshooting, relationship exploration, and general query. Provide confidence/evidence or a safe general-query fallback. |
| F-16 | Entity and identifier extraction | Capability | Preserve exact spellings; extract entities, IDs, names, paths, and technical phrases; distinguish uncertain extractions. Feed Graph lookup where useful without silently rewriting identifiers. |
| F-17 | Query planning and expansion | Capability | Use intent/entities to choose relevant sources and bounded query variants; apply source-specific behavior; respect deadline and cost/result budgets; record plan diagnostics without storing raw prompts by default. |
| F-18 | Candidate fusion, ranking, and deduplication | **Service (required initial boundary)** | Accept candidates from enabled retrieval paths, deduplicate by stable identity, order them using explicit ranking policy, use deterministic tie-breaking, and return scores/evidence plus policy version. Do not assume every retrieval strategy exists in the initial implementation. Ranking owns ordering, not corpus/index state or source retrieval. BM25/cosine/normalization remain strategies, not services. |
| F-19 | Optional reranking | Capability/strategy; conditional service | Define input/output and score semantics. Separate service only if model/resource lifecycle, latency, isolation, or independent scaling justifies it. |
| F-20 | Source and project-scope enforcement | Cross-cutting capability owned by relevant domain services | Enforce authorization and scope before results are exposed or consume ranking budget. Missing/invalid scope must never broaden access. Domain owners remain authoritative for their data. |
| F-21 | Prompt-context assembly | Adapter/orchestration capability | Compose bounded Memory, Knowledge, and Graph evidence for the prompt hook; preserve source distinctions/provenance; enforce token/size/time budgets; avoid duplicate content; distinguish “no result” from retrieval failure. |
| F-22 | Claude Code hook integration | Adapter | Invoke retrieval during the normal prompt lifecycle and inject relevant context automatically. No manual lookup instruction or special prefix may be required. Fail-open behavior, time budget, diagnostics, and content formatting must be explicit. |
| F-23 | Provenance and evidence | Shared contract/primitives; domain-owned truth | Carry source IDs, document/chunk revisions, source locations, retrieval path, and ranking policy. Shared formats are acceptable; a separate provenance service is not assumed. |
| F-24 | Configuration and policy | Cross-cutting capability | Validate configuration, identify effective profile/version, define defaults and overrides, and expose safe diagnostics. Avoid hidden per-process policy drift. |
| F-25 | Readiness and recovery | Cross-cutting operational behavior, owned per service | Distinguish process health from readiness of required state/dependencies. Surface pending work and fault state; define restart/recovery and degraded behavior. A successful empty search must not disguise an unavailable index. |
| F-26 | Observability and diagnostics | Cross-cutting capability | Correlation IDs, timings, selected sources/strategies, intent/entities where safe, result counts, failure categories, and policy versions. Do not log raw prompt text or memory/knowledge content by default. |
| F-27 | REST contract and errors | Cross-cutting contract rules | All services expose REST/HTTP contracts. Define request/response schemas, validation, error codes, retryability, idempotency, deadlines, cancellation, pagination/limits, and compatibility. Adapters must not fork domain semantics. |
| F-28 | Security and isolation | Cross-cutting capability | Define caller identity, project/user boundaries, authorization, secret handling, data exposure, and safe failure. Scope filters must be enforced server-side, not trusted solely to the hook. |
| F-29 | Evaluation and acceptance | Cross-cutting capability/process | Maintain labeled scenarios for recall, identifiers, ambiguity, factual lookup, explanations, troubleshooting, graph relationships, empty results, and degraded dependencies. Measure relevance, false positives, latency, resource use, and recovery. |
| F-30 | Deployment and resource policy | Operational concern | Define service lifecycle, dependencies, resource limits, model provisioning, upgrades, and rollback. Deployment topology is not inferred from logical service boundaries. |

## Scope tiers for the restart

The inventory deliberately separates the small initial architecture from optional techniques. A named capability is not a commitment to implement it in the first release.

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
- **Ranking**: shared candidate ordering, fusion, and deduplication through REST. Ranking does not own corpus data or perform source retrieval.

These are logical service boundaries, not a mandate for ten separate processes. Each service must have a REST contract, a clear owner, consumers, failure/readiness semantics, and a concrete reason to exist. Co-deployment is allowed.

### Required behavior, not additional services

- Prompt-time hook integration and bounded context assembly.
- Source/project-scope enforcement and provenance.
- Request validation, configuration, health/readiness, diagnostics, and recovery.
- A basic retrieval path that can find and rank useful candidates from the initial corpus.
- Acceptance tests proving normal prompt-time memory injection works without a special prefix or user reminder.

These are capabilities, adapters, or cross-cutting rules owned by the relevant services. They do not automatically become standalone services.

### Required capabilities with explicit service boundaries

The following are part of CE's intended functionality and must be represented as logical services with language-neutral REST contracts. The initial deployment may co-locate them, but they must not be silently absorbed into Index, Ranking, Gateway, or a domain service.

- **Embedding**: generate vectors with explicit model identity/version, dimensions, normalization, batching, and failure semantics.
- **Vector Retrieval**: retrieve candidates by vector similarity while respecting index revisions, model compatibility, scope, and provenance. It consumes vectors and indexed content; it does not own embedding-model behavior.
- **Intent Classification**: classify request intent with confidence and evidence sufficient to guide retrieval.
- **Entity and Identifier Extraction**: identify entities, exact identifiers, paths, names, and technical phrases while preserving source spelling and uncertainty.
- **Query Planning**: select retrieval sources and construct bounded query plans from the request, intent, and extracted entities. Query expansion is a capability of this service, with explicit limits and traceability.
- **Reranking**: apply a second-stage ranking operation to a bounded candidate set when required by the ranking policy. It has a distinct contract and can initially use a simple implementation.

These are logical service boundaries, not a requirement for separate deployment units. Each must define inputs, outputs, ownership, REST behavior, failure semantics, and acceptance tests. Keep model choice and algorithms replaceable behind the contracts.

### Conditional capabilities

- Source discovery and elaborate ingestion orchestration beyond the minimum needed to populate and maintain the index.
- Model-specific subword tokenization and context-window token counting, which are distinct from the existing lexical Tokenization service.
- Additional retrieval strategies or advanced ranking algorithms not required by the agreed retrieval flows.

A conditional capability is not silently in scope just because it could be useful; but the services listed above are explicitly part of the intended CE capability set.

### Not separate services by default

BM25, cosine similarity, score normalization, and individual index structures are algorithms or implementation strategies, not services by themselves. Exact-identifier lookup and deduplication may be operations owned by Vector Retrieval, lexical retrieval, or Ranking according to their contract; they do not automatically require separate services. Observability, configuration, security, and provenance are cross-cutting responsibilities, not standalone services by default.

Ranking and Reranking are distinct services: Ranking performs the shared candidate fusion/order/deduplication operation; Reranking applies a separately specified second-stage candidate assessment. Index owns indexing lifecycle and searchable representations; Vector Retrieval owns vector-based candidate retrieval; Embedding owns vector generation.

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
7. Retrieve candidates using the initially selected retrieval strategy.
8. Send candidates to Ranking and return ordered results with provenance. Vector retrieval is conditional, not an assumed requirement.

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
- The initial retrieval path has explicit acceptance tests for useful recall, identifier preservation, deduplication, provenance, empty results, and graceful degradation. Do not require embeddings, intent classification, or query expansion without an approved use case.
- Automatic prompt-time recall is tested through the installed Claude Code hook with real conversational recall.
- Indexing acceptance covers deterministic chunking, revision changes, deletion, fresh-process recovery, failure injection, and stale/pending index state. Embedding incompatibility is tested only if embeddings are included.
- Resource/latency acceptance reflects shipped service limits and concurrent Memory/Knowledge work, not just unit tests.
- No implementation starts until the inventory and boundary decisions are reviewed.
