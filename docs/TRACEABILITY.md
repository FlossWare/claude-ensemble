# Requirement and Test Traceability

Status: normative review gate. This matrix links the initial required service boundaries to contracts, workflows, isolated suites, and end-to-end acceptance evidence. It is maintained with the contracts, not after implementation.

| Requirement / capability | Owner | Contract / endpoint | Isolated test evidence | Integration / acceptance |
|---|---|---|---|---|
| Public request orchestration, bounded response, prompt-hook fail-open | Gateway | GATEWAY.md, POST /api/v1/requests | Gateway suite with every dependency mocked at REST boundary | AT-PARTIAL-01, AT-HOOK-01, AT-FRESH-01 |
| Canonical memory lifecycle and automatic recall | Memory | MEMORY.md, memories/revisions/verify/reconciliation | Memory suite with Index/Chunking/Tokenization/Embedding/Graph mocked | AT-DEL-01, AT-WRITE-RECALL-01 |
| Sourced knowledge lifecycle and locator provenance | Knowledge | KNOWLEDGE.md, knowledge/sources/verify/reconciliation | Knowledge suite with derived-service dependencies mocked | AT-DEL-01, AT-MAP-01, AT-WRITE-RECALL-01 |
| Source-derived relationships and traversals | Graph | GRAPH.md, projections/deletions/traversals/operations | Graph suite with isolated store; no owner service required | AT-DELETE-GRAPH-01, AT-GRAPH-SUPPORT-01, AT-GRAPH-STALE-PATH-01 |
| Selection state and Thompson sampling | Thompson | THOMPSON.md, selections/updates/state | Thompson suite with isolated state store | AT-LEARNING-01 |
| Feedback validation and durable outcomes | Learning | LEARNING.md, outcomes/operation status | Learning suite with Thompson REST mock | AT-LEARNING-01 |
| Searchable representations, profile registry, generation lifecycle | Index | INDEX.md, profiles/upsert/delete/lookups/generations | Index suite with isolated storage and deterministic clocks | AT-DEL-01, AT-REBUILD-01, AT-REBUILD-02 |
| Deterministic chunks and preview preflight | Chunking | CHUNKING.md, chunk/preview endpoints | Chunking suite with no downstream services | AT-TEXT-01, AT-SIZE-PREFLIGHT-01 |
| Lexical normalization and batch tokenization | Tokenization | TOKENIZATION.md, tokenize/batch endpoints | Tokenization suite with no downstream services | AT-TEXT-01, AT-TOKEN-BATCH-01 |
| Versioned vector generation | Embedding | EMBEDDING.md, embed endpoint | Embedding suite with profile registry mocked | AT-EMBED-01 |
| Intent signal for query plan | Intent Classification | INTENT-CLASSIFICATION.md, classify endpoint | Intent suite with no downstream services | AT-GW-01, AT-HOOK-01 |
| Exact identifiers and Unicode spans | Entity and Identifier Extraction | ENTITY-EXTRACTION.md, extract endpoint | Entity suite with no downstream services | AT-TEXT-01, AT-RANK-01 |
| Lexical candidate retrieval and corpus statistics | Lexical Retrieval | LEXICAL-RETRIEVAL.md, search endpoint | Lexical suite with Index and Tokenization REST mocks | AT-PARTIAL-01, AT-FRESH-01 |
| Vector candidate retrieval | Vector Retrieval | VECTOR-RETRIEVAL.md, search endpoint | Vector suite with Index and Embedding REST mocks | AT-PARTIAL-01, AT-FRESH-01 |
| Candidate fusion, deterministic ordering, exact-ID protection | Ranking | RANKING.md, rank endpoint | Ranking suite with fixed fixtures; no outbound dependencies | AT-RANK-01 |
| Bounded second-stage assessment | Reranking | RERANKING.md, rerank endpoint | Reranking suite with deterministic model adapter double | AT-RERANK-01 |
| Common HTTP behavior, idempotency, deadlines, errors | All services | REST-CONTRACT.md | Schema/header/error fixture checks in every service suite | AT-IDEMP-01, AT-PERF-01, AT-HEALTH-01 |
| Isolated testability with REST mocks | Every logical service | SERVICE-TESTING.md and each service contract | Each of the 16 isolated suites is independently runnable | AT-SVC-ISOLATION-01 |

## Review gate

Every inventory requirement must map to an owner, contract section/endpoint, workflow, and named acceptance test. A named test is not sufficient on its own: acceptance text must define setup, interleaving/failure injection, observable assertions, and expected status. Every service contract must identify outbound REST dependencies and state how those dependencies are mocked in isolation. Notion and Git must agree on owner decisions; this traceability matrix is the Git-side executable-contract index.
