# Clean-Slate Restart Plan

## Purpose

Redesign Claude Ensemble around an explicit functional model and stable contracts rather than carrying forward historical implementation decisions. The archived repository is reference material only.

## Architecture invariants

These are binding design constraints, not implementation suggestions.

- **Single deployment initially:** one CE application, one REST server, and one process/lifecycle. Logical service boundaries do not imply separate processes, hosts, repositories, or containers.
- **REST-only service communication:** every call from one logical service to another goes through that service's REST contract, even when both are co-located in the same process. Cross-service direct method calls and storage access are prohibited.
- **Federation-ready routing:** callers address stable service contracts, not service locations. Routing may later forward a request to a remote service instance without changing the caller's business logic. Federation infrastructure and configuration may change; the contract must remain compatible.
- **Bounded calls:** service calls define deadlines/timeouts, cancellation behavior, error semantics, retryability, and idempotency where applicable. Retries must be bounded and must not create loops or duplicate side effects.
- **Explicit boundaries:** each service owns its domain semantics and authoritative data. Cross-cutting behavior, components, and algorithms must have named owners but do not automatically become services.
- **Traceable results:** preserve request correlation, source identity/revisions, provenance, and relevant policy/model versions. Do not log raw prompts or sensitive retrieved content by default.
- **Contract-first implementation:** requirements, service ownership, contracts, failure behavior, and acceptance tests must be reviewed before implementation begins. Deviations require explicit architectural review.

## Relationship to FlossWare: concept and lesson transfer

Claude Ensemble and FlossWare are separate projects. CE does not share FlossWare code, repositories, services, or runtime dependencies. FlossWare may seed CE with concepts, and CE may seed FlossWare with validated concepts and lessons learned.

The knowledge-transfer loop is intentionally bidirectional and ongoing:

- **Past:** examine historical implementations, decisions, failures, and successful patterns as evidence. Do not inherit them automatically.
- **Present:** record decisions, trade-offs, experiments, defects, corrections, and acceptance results as the clean-slate CE design develops.
- **Future:** capture operational outcomes, new failure modes, successful patterns, and revisions to assumptions after implementation and use.
- **Transfer:** distill reusable principles, contracts, and lessons for possible use in FlossWare. Validate their applicability in the receiving project; do not copy implementation details or assume a CE-specific decision belongs in FlossWare.
- **Traceability:** where practical, record the source project, context, evidence, limitations, and resulting decision so a lesson does not become an unsupported rule.

This is a concept-and-learning exchange, not a shared implementation or dependency relationship. Both projects remain free to choose different implementations when their requirements differ.

## Required initial logical services

The required logical service boundaries are listed below. They do not imply separate processes or hosts; deployment topology is a separate decision.

- **Gateway**: stable client-facing REST entry point and request coordination.
- **Memory**: capture, update, retrieve, inject relevant context automatically, and explain provenance.
- **Knowledge**: own durable sourced knowledge, revisions, lifecycle, and provenance.
- **Graph**: represent and traverse relationships where graph semantics add value.
- **Thompson**: own the agreed Thompson-sampling functionality and its state/decision contract.
- **Learning**: define what is learned, from which evidence, with what feedback and lifecycle.
- **Index**: own the shared indexing lifecycle and searchable representations, including revisions, updates, deletions, readiness, and recovery. Indexing is a service, not an incidental responsibility hidden inside Memory or Knowledge.
- **Chunking**: provide deterministic, versioned chunk boundaries and source provenance through REST.
- **Tokenization and lexical normalization**: provide consistent, versioned index/query tokenization through REST.
- **Embedding**: generate vectors behind a versioned model-independent contract.
- **Vector Retrieval**: retrieve vector-similar candidates with index/model compatibility, scope, and provenance.
- **Intent Classification**: classify request intent and provide confidence for retrieval planning.
- **Entity and Identifier Extraction**: extract entities and technical identifiers while preserving exact spellings.
- **Query Planning**: select sources and produce bounded query plans, including controlled query expansion.
- **Ranking**: fuse, deduplicate, and order candidates with explainable evidence. It does not own corpus/index state or perform source retrieval.
- **Reranking**: independently assess a bounded candidate set as a second-stage operation.

All listed services, including Embedding, Vector Retrieval, Intent Classification, Entity and Identifier Extraction, Query Planning, Ranking, and Reranking, are required logical boundaries. Their contracts must be specified before implementation. A logical service does not automatically require a separate process or host.

**Required behavior, not extra services:** automatic prompt-time hook integration, bounded context assembly, source/project-scope enforcement, provenance, basic retrieval, configuration, health/readiness, diagnostics, and recovery.

**Required retrieval services:** Embedding, Vector Retrieval, Intent Classification, Entity and Identifier Extraction, Query Planning (including bounded query expansion), Ranking, and Reranking each have an explicit REST contract. They may initially be co-deployed, but their responsibilities must not be hidden inside Index, Gateway, or domain services.

**Conditional capabilities:** elaborate source discovery/ingestion orchestration beyond basic index maintenance, model-specific subword tokenization, and context-window token counting remain conditional. BM25, cosine similarity, score normalization, and index structures remain algorithms/implementation strategies, not separate services by default. Alerting and messaging remain out of initial scope.

## Current working document

- [Functional Inventory (Draft)](FUNCTIONAL-INVENTORY.md): behavior inventory and service/capability/algorithm boundaries. The inventory remains under review overall; service boundaries approved so far are listed in the scope section above.
- [Chunking Service Contract (Draft)](contracts/CHUNKING.md): deterministic chunking, provenance, stable identity, versioning, and reindex behavior.
- [Tokenization Service Contract (Draft)](contracts/TOKENIZATION.md): lexical tokenization/normalization, identifier preservation, offsets, and profile compatibility.

## Design sequence

1. **Functional inventory**: enumerate user-visible and system-level behavior, triggers, inputs, outputs, failure cases, and acceptance evidence.
2. **Boundary classification**: classify every item as a service, component, algorithm, data model, adapter, or operational concern. Chunking and Tokenization are approved services with REST contracts. Do not turn every algorithm into a network service just because it has a name.
3. **Contracts**: specify language-neutral HTTP/REST contracts where a capability needs independent addressability. Define models, errors, lifecycle, deadlines, cancellation, retries, idempotency, and versioning as applicable. Consider decorator/composition implementations when defining each contract.
4. **Ownership**: make explicit who owns persistence, identity, provenance, indexing, retention, recovery, and cross-service consistency.
5. **Acceptance criteria**: define observable tests before implementation, including fresh-process recovery, failure injection, and end-to-end integration where relevant.
6. **Vertical slices**: implement only after the specification is reviewed. Each slice must have contract tests and an end-to-end acceptance path.

## Non-negotiable acceptance requirement: automatic memory

Memory retrieval/injection must work during the normal prompt lifecycle without requiring a manual memory lookup, special prefix, or user reminder. Tests must verify both that relevant stored memories are injected and that the assistant does not falsely claim no memories exist when retrievable memories are available.

## Working rules

- Existing code is evidence, not the design.
- Do not preserve an endpoint, class, schema, or service solely because it exists in the archive.
- Distinguish independently addressable services from internal components and algorithms.
- Prefer clear contracts over language-specific implementation assumptions.
- Do not declare distributed safety based only on an in-process or single-host test.
- Do not begin implementation before the functional inventory, boundaries, contracts, ownership, and acceptance criteria are sufficiently specified and reviewed.

## Historical reference

- Archived repository: [FlossWare-Archives/claude-ensemble-legacy](https://github.com/FlossWare-Archives/claude-ensemble-legacy)
