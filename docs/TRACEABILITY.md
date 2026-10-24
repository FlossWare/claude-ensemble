# Functional Traceability Matrix

Status: proposed architecture acceptance artifact. Rows map the functional inventory to an owner, contract/workflow, and acceptance coverage. An acceptance specification is not an executed test.

| Inventory ID | Owner / capability | Contract or workflow | Acceptance coverage |
|---|---|---|---|
| F-01 | Gateway | `contracts/GATEWAY.md`, `contracts/REST-CONTRACT.md` | AT-GW-01, AT-MAP-01, AT-FRESH-01, AT-PARTIAL-01, AT-VERIFY-01, AT-PERF-01 |
| F-02 | Gateway query planning | `contracts/GATEWAY.md` | AT-GW-01, AT-RRF-02 |
| F-03 | Memory | `contracts/MEMORY.md` | AT-DEL-01, AT-CONC-01, AT-IDEMP-01, AT-RECOVERY-01 |
| F-04 | Knowledge | `contracts/KNOWLEDGE.md` | AT-DEL-01, AT-CONC-01, AT-ID-01, AT-MAP-01, AT-RECOVERY-01 |
| F-05 | Graph | `contracts/GRAPH.md` | AT-DELETE-GRAPH-01, AT-RECOVERY-01 |
| F-06 | Thompson | `contracts/THOMPSON.md` | AT-SCHEMA-01, AT-IDEMP-01 |
| F-07 | Learning | `contracts/LEARNING.md` | AT-SCHEMA-01, AT-IDEMP-01 |
| F-08 | Memory and Knowledge ingestion orchestration | `contracts/MEMORY.md`, `contracts/KNOWLEDGE.md` | AT-REST-ASYNC-01, AT-RECOVERY-01 |
| F-09 | Index | `contracts/INDEX.md` | AT-DEL-01, AT-REBUILD-01, AT-REBUILD-02, AT-CUTOVER-SEAL-01, AT-GEN-02, AT-GEN-03, AT-PROFILE-01 |
| F-10 | Chunking | `contracts/CHUNKING.md` | AT-TEXT-01, AT-REBUILD-01, AT-PROFILE-01 |
| F-11 | Tokenization | `contracts/TOKENIZATION.md` | AT-TEXT-01, AT-TOKEN-BATCH-01, AT-PROFILE-01 |
| F-12 | Lexical Retrieval | `contracts/LEXICAL-RETRIEVAL.md` | AT-RANK-01, AT-VERIFY-01, AT-SCHEMA-01 |
| F-13 | Embedding | `contracts/EMBEDDING.md` | AT-EMBED-01, AT-PROFILE-01 |
| F-14 | Vector Retrieval | `contracts/VECTOR-RETRIEVAL.md` | AT-RANK-01, AT-VERIFY-01, AT-PROFILE-01 |
| F-15 | Intent Classification | `contracts/INTENT-CLASSIFICATION.md` | AT-GW-01 |
| F-16 | Entity and Identifier Extraction | `contracts/ENTITY-EXTRACTION.md` | AT-TEXT-01, AT-RRF-02 |
| F-17 | Gateway query planning | `contracts/GATEWAY.md` | AT-GW-01, AT-RRF-02 |
| F-18 | Ranking | `contracts/RANKING.md` | AT-RANK-01, AT-RRF-02 |
| F-19 | Reranking | `contracts/RERANKING.md` | AT-PERF-01, AT-SCHEMA-01 |
| F-20 | Scope partitioning and local access restrictions | `contracts/REST-CONTRACT.md`, owner contracts | AT-VERIFY-01, AT-ID-01, AT-MAP-01 |
| F-21 | Gateway prompt-context assembly/compression | `contracts/GATEWAY.md` | AT-PERF-01, AT-GW-01 |
| F-22 | Claude Code hook adapter | Gateway integration workflow | AT-PERF-01; hook integration test required before implementation approval |
| F-23 | Shared provenance/evidence | Common REST rules and all candidate/source contracts | AT-SCHEMA-01, AT-VERIFY-01, AT-MAP-01, AT-FRESH-01, AT-RRF-02 |
| F-24 | Configuration and profile policy | `contracts/INDEX.md`, `contracts/EMBEDDING.md`, `contracts/REST-CONTRACT.md` | AT-PROFILE-01 |
| F-25 | Health, readiness, and recovery | All service contracts, `docs/RESTART.md` | AT-HEALTH-01, AT-RECOVERY-01 |
| F-26 | Diagnostics/observability | Common REST metadata and per-service status responses | AT-PERF-01, AT-RECOVERY-01 |
| F-27 | REST contract and errors | `contracts/REST-CONTRACT.md` | AT-HEALTH-01, AT-SCHEMA-01, AT-REST-ASYNC-01 |
| F-28 | Local access and data isolation | Common REST rules and source-owner contracts | AT-VERIFY-01, AT-ID-01 |
| F-29 | Evaluation and acceptance | `docs/ARCHITECTURE-REVIEW-ACCEPTANCE.md` | All AT-* scenarios; domain relevance evaluation remains a pre-release gate |
| F-30 | Deployment/resource policy | `docs/RESTART.md`, common REST bounds | AT-PERF-01, AT-RECOVERY-01 |

## Known acceptance gaps

- The listed AT-* items are specifications, not executed tests.
- Hook injection with a real Claude Code lifecycle still requires an executable integration test.
- Notion/Git alignment is a manual release gate until a reliable export/diff is available.
- Latency budgets are normative targets and remain unverified until measured under the specified dispatcher/load test.
