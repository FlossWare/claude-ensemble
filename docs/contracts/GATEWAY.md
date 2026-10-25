# Gateway Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Provide the client-facing CE REST API and orchestrate bounded workflows across logical services. Own request validation, local deployment restrictions where required, scope propagation, request budgets, query planning, service selection, partial-result policy, prompt-context assembly/compression, and final response composition. Query Planning is a Gateway capability, not a separate initial service.

Gateway does not own Memory/Knowledge/Graph/Thompson/Learning/Index domain state. It calls every logical service through REST, even in the single-process deployment. It must not access another service's storage or invoke its implementation directly.

## Endpoints

- POST /api/v1/requests: process a client request and return a bounded response with provenance.
- POST /api/v1/selections: validate and request a Thompson selection through REST.
- POST /api/v1/outcomes: submit outcome evidence to Learning through REST.
- GET /api/v1/gateway/health: process liveness.
- GET /api/v1/gateway/ready: readiness to accept client requests under configured dependency policy.

The public request/response schemas below are normative for the initial contract. Optional `exact_identifiers` is bounded to 32 strings of at most 256 Unicode code points. Generalized authentication is deferred; only local access restrictions required by the single-instance deployment apply.

## Decision selection and outcome workflows

### Selection and learning workflows

- `POST /api/v1/selections` accepts `context_id`, versioned selection `policy`, bounded `eligible_arms`, and optional `expected_state_version`. Gateway validates the request and calls `POST /api/v1/thompson/selections` over REST. The response carries `selection_id`, chosen arm, policy/state version, bounded evidence, and request ID.
- `POST /api/v1/outcomes` accepts the stable selection/context/arm identity, outcome, evidence, occurrence timestamp, and policy version. Gateway calls `POST /api/v1/learning/outcomes` over REST and returns the durable Learning operation identity/status. Learning validates and records the outcome, then calls Thompson over REST to apply the idempotent update. Thompson never calls Learning.
- Both workflows use the same deadline, idempotency, local access restrictions, and operation-status rules as other Gateway requests. They do not share service storage or invoke direct methods.

## Orchestration semantics

- At request start, call `GET /api/v1/index/generations/active` once through REST, then resolve its exact `{name, version}` using `GET /api/v1/index/profiles/{profile_name}/versions/{profile_version}` and require the returned digest to equal the active generation's pinned digest. Pin `index_generation` and the complete immutable `profile_bundle` for the request; do not use the current profile endpoint for an already active generation. Pass the pinned identity/component versions to Lexical Retrieval and Vector Retrieval, which resolve the same pinned bundle through Index when they need component details and pass the identity unchanged to Index. Profile resolution is part of the 100 ms planning budget; failure or digest mismatch produces an explicit degraded/failed result, never a guessed profile. All retrieval is pinned to that generation even if a cutover occurs mid-request. If active-generation resolution fails, do not guess a profile or mix generations; return an explicit degraded/failed response.
- Build a bounded plan using Intent Classification and Entity/Identifier Extraction where useful. V1 uses this normative intent-to-plan table: `memory_recall` → Memory plus lexical/vector retrieval; `knowledge_lookup` → Knowledge plus lexical/vector retrieval; `relationship_exploration` → Graph traversal plus lexical/vector retrieval for explanatory source evidence; `troubleshooting`, `explanation`, and `decision_support` → Memory/Knowledge plus lexical/vector retrieval; `general` or unknown/low-confidence → Memory/Knowledge plus lexical/vector retrieval. For `relationship_exploration` or an explicit bounded relationship request, Gateway passes up to 16 extracted entity surface forms as `entity_mentions` to Graph traversal; Graph resolves them to scoped node IDs using its exact label/alias rule and reports unresolved mentions. Gateway does not invent node IDs from names. Graph is required only for `relationship_exploration` or an explicit bounded relationship request. V1 Gateway requests carry exactly one `scope`; multi-scope public requests are deferred, and Gateway never fans out across or merges scope partitions. The intent vocabulary is `memory_recall`, `knowledge_lookup`, `relationship_exploration`, `troubleshooting`, `explanation`, `decision_support`, and `general`; unknown/low-confidence intent uses the bounded `general` plan. Query expansion is disabled in v1; exactly one original query is used. Reconsider expansion only with a separately reviewed policy and acceptance evidence.
- Run independent calls concurrently only when the plan, deadline, and failure policy permit. After intent/entity planning, start applicable lexical retrieval, vector retrieval, and optional Graph traversal concurrently. The prompt-hook critical path is therefore bounded by planning (≤100 ms), the slowest parallel lexical/vector/Graph branch (≤350 ms), canonical verification (≤250 ms), Ranking (≤150 ms), optional Reranking (≤250 ms), and assembly/serialization (≤100 ms), with a 300 ms safety reserve inside the 1,500 ms hard hook deadline. Every stage is cancelled at its absolute deadline. V1 retrieval does not paginate or refill. If freshness filtering leaves too few candidates, return a partial/degraded result when safe candidates remain, or failed when no safe result remains. All service calls use REST and propagate correlation, deadline, cancellation, and canonical scope partition.
- Extract up to 32 exact identifiers from Entity/Identifier Extraction and preserve their exact spelling. A match requires exact equality between the extracted identifier and either a value in a structured `metadata.identifiers` array or a complete text span after Unicode NFC normalization and Unicode case folding. For text, identifier characters are Unicode letters, combining marks, numbers, underscore, hyphen, and period; the span must be bounded on both sides by start/end of text or a character outside that set. Thus `REV-17` matches `REV-17,` but not `REV-170` or `X-REV-17`. Gateway preserves the original extracted spelling for output and compares normalized forms only. Gateway supplies `exact_identifiers` to Ranking and annotates `matched_exact_identifiers` only on such exact equality. The exact-match tier is a final-output guarantee. Gateway separates exact-match candidates after Ranking, preserves them in Ranking order, and sends only non-exact candidates to the bounded Reranking stage (maximum 20). It then prepends the preserved exact-match candidates to the reranked non-exact candidates. Reranking must preserve identity and evidence for every candidate it receives. Context assembly may not drop a verified exact candidate while a non-exact candidate remains and the context budget can fit the exact candidate.
- Fetch up to 3× the requested final candidate count, capped at 100 per retrieval path. Before verification, merge duplicate identities and cap the aggregate candidate pool at 100 candidates across all paths for the request; before applying the cap, annotate exact-identifier matches using the normative whole-span rule; then order by exact-match tier first, minimum 1-based retrieval rank ascending, `list_id` ascending, and the canonical candidate identity tuple (`source_id` ascending, `revision_sequence` descending, `chunk_id` ascending, `chunker.profile` ascending, `chunker.version` ascending). Keep each candidate's per-list rank/evidence contributions for Ranking. Set `truncated=true` if this cap is reached. The exact-match guarantee begins only at the candidates returned by retrieval and admitted to this bounded aggregate pool; v1 does not guarantee corpus-wide exact-identifier recall. Gateway batch-verifies those candidates against canonical owners before Ranking, with at most 100 identities per owner per batch and at most two batches per owner per request; owner batches run concurrently. Remove stale, tombstoned, not-found, and unverified candidates. V1 does not paginate or refill. If a retrieval path is truncated or canonical verification filters candidates, preserve the available safe candidates and set `truncated=true` and `status=partial` when any required candidates may be missing; if no safe candidates remain because a required dependency failed, return `status=failed`, never successful empty results. This bounded behavior avoids an unbudgeted second retrieval/verification round. Never return an unverified candidate as current. Then invoke Ranking; invoke Reranking only when its reserved budget remains. The Gateway response `score` and `score_semantics` remain the integer fixed-point RRF score from Ranking (`rrf-v1`). Reranking's numeric score is used only to order non-exact candidates internally; Gateway MUST NOT copy it into the integer `score` field.
- Assemble prompt context with explicit token budget, relevance, recency/authority policy where applicable, provenance, and compression rules. Compression must preserve facts, decisions, constraints, identifiers, and evidence links; it must not silently change meaning.
- Provider prompt-cache optimization is a separate concern from generic response caching. Stable prefixes may be reused only when provider semantics and privacy scope allow it.
- Automatic prompt-time memory injection must work without a manual memory instruction or special prefix. Hook/adapters call Gateway through the public contract and must not bypass service ownership.
- Partial dependency failure is governed by the normative degradation matrix below. An unavailable retrieval service is not treated as a successful no-match. For every candidate returned to a client or prompt context, Gateway routes only by the exact `source_id` prefix: `memory:` to Memory and `knowledge:` to Knowledge. It passes the full namespaced `source_id` in the common verification body; it never derives an owner from the suffix or a canonical locator. Gateway batches source IDs and `revision_sequence` values by owner and calls the corresponding revision-verification REST endpoint before presenting candidates as current. A missing/tombstoned source or revision mismatch is filtered. If required verification is unavailable, the candidate is not exposed as current and the response marks freshness degradation; if no safe candidates remain, return an explicit degraded/failed outcome rather than claiming a successful empty search.
- Interactive API default deadline is 5 seconds. The Claude Code prompt hook has a hard 1,500 ms end-to-end deadline. Within the hook budget, Gateway reserves 250 ms for canonical freshness verification, 150 ms for Ranking, 250 ms for optional Reranking, and 100 ms for context assembly/response serialization; all other work must fit in the remaining budget. The applicable lexical, vector, and Graph calls run concurrently after planning. The worst-case planned critical path is 1,200 ms (100 + 350 + 250 + 150 + 250 + 100), leaving a 300 ms safety margin inside the 1,500 ms hard deadline. Intent Classification and Entity/Identifier Extraction each have a 100 ms cap and run concurrently. Each lexical/vector retrieval call is capped at 350 ms and the paths run concurrently. Graph traversal is capped at 250 ms. No service may extend the absolute caller deadline. These are acceptance targets, not measured performance claims. If a reserved stage cannot start within its budget, Gateway applies the degradation matrix below. Retries are disabled by default in the prompt-hook path and otherwise limited to one retry when at least 100 ms remains.
- Preserve request ID, selected plan/policy versions, candidate provenance, source revisions, and model/profile versions in safe response metadata. Do not log raw prompts or sensitive source text by default.

### Public request and response schemas

Request `POST /api/v1/requests`:

~~~json
{
  "request_id": "correlation-id",
  "query": "How are source revisions published?",
  "scope": {"type": "project", "id": "project-id", "visibility": "private"},
  "context_budget": {"unit": "provider_tokens", "model": "configured-target-model", "max": 1200},
  "mode": "prompt_recall"
}
~~~

`query` is required and bounded by the configured request limit. A successful no-match is `status=complete` only if all required retrieval and freshness stages completed; any required dependency failure produces `status=partial` or `status=failed` as specified below. `scope` is required unless this endpoint's deployment profile defines one unambiguous default. Optional `after_operation_id` requests read-your-writes behavior for a previously accepted Memory/Knowledge mutation. Gateway routes the status check by the owner prefix and calls that owner's top-level operation-status endpoint concurrently with intent/entity planning, within the same 100 ms planning budget. If that operation is still indexing, response metadata reports `index_freshness=pending_index` rather than asserting a definitive no-result. If the operation-status call times out or its owner is unavailable, report `index_freshness=unknown`, mark the response degraded, and do not claim a definitive no-match. Candidate freshness values are `verified_current`, `stale`, `tombstoned`, `not_found`, and `unverified`; only `verified_current` candidates may be returned as current. `context_budget` is bounded; the provider adapter must use the named target model's token counting when available and otherwise report that a conservative estimate was used. `mode` is `prompt_recall`, `interactive`, or `lookup`.

Response:

~~~json
{
  "request_id": "correlation-id",
  "status": "complete",
  "context": "Bounded assembled context",
  "candidates": [],
  "degraded": false,
  "degradation_reasons": [],
  "failures": [],
  "plan": {"intent": "general", "variants_used": 1, "policy_version": "v1", "index_generation": "generation-123", "index_profile": {"name": "default", "version": "0.1", "digest": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}},
  "index_freshness": "current",
  "truncated": false
}
~~~

`degraded` and `failures` distinguish a partial workflow from a successful no-match. On a prompt-hook deadline or total dependency failure, the adapter fails open to the original prompt with no injected context, records a safe diagnostic, and must not claim that no memory exists. Interactive callers receive the documented error envelope when no safe result can be produced.

## Degradation matrix and latency budgets

| Dependency/step | Required behavior on failure | Budget |
|---|---|---:|
| Claude Code hook to Gateway | Fail open to the host application; emit bounded diagnostic metadata only | 1,500 ms total |
| Intent Classification | Continue with `general` intent and add `query_understanding_degraded` to `degradation_reasons` | 100 ms |
| Entity/Identifier Extraction | Continue without extracted identifiers; mark degraded | 100 ms |
| Lexical Retrieval | Continue with Vector results if available; otherwise degraded error | 350 ms |
| Vector Retrieval | Continue with Lexical results if available; otherwise degraded error | 350 ms |
| Graph optional | Omit graph-derived evidence and mark partial/degraded | 250 ms |
| Graph required for relationship exploration | Return verified Graph evidence when available; if unavailable, return failed unless verified lexical/vector evidence supports an explicit partial result | 250 ms |
| Embedding | Apply the Vector Retrieval failure rule and record the failed dependency; preserve a surviving lexical result as partial | Within the 350 ms vector-path budget |
| Canonical freshness verification | Fail closed for candidates whose owner cannot be verified; preserve healthy-owner candidates | 250 ms total |
| Ranking | Degraded error; no unranked success response | 150 ms |
| Reranking | Skip and retain Ranking order; mark degraded | 250 ms |
| Optional context compression | Return bounded verified evidence without optional compression; mark partial/degraded | Within the 100 ms assembly budget |
| Required context assembly/token budget | Return failed if provenance, exact identifiers, or the requested budget cannot be preserved | Within the 100 ms assembly budget |

The budgets are ceilings within the 1,500 ms hook deadline, not additive allowances. Gateway uses one absolute deadline, reserves 250 ms for freshness verification, 250 ms for optional Reranking, and 100 ms for assembly/serialization, and stops optional work when the remaining budget reaches those reserves. Lexical and Vector retrieval run in parallel; Intent and Entity/Identifier Extraction may run in parallel. Every dependency call uses the remaining absolute deadline. If mandatory steps cannot complete within the remaining budget, return a degraded error rather than exceed the deadline.

## Errors and fallback

Use the common REST error envelope. Distinguish invalid request, budget/deadline exceeded, dependency unavailable, partial workflow failure, and internal failure. The v1 degradation matrix is normative. In `prompt_recall`, no pagination/refill is permitted; all stages use the single deadline schedule above. `status=complete` requires `degraded=false`, empty `degradation_reasons`, and empty `failures`; `status=partial` or `status=failed` requires `degraded=true`. A request has one scope partition in v1, so there is no per-scope fan-out failure state. Graph evidence is returned separately from ranked text candidates and is not forced into Ranking's chunk-candidate schema. For each Graph path, Gateway verifies every unique support identity within a hard budget of 100 support identities. An edge remains eligible only if at least one support verifies current in the requested scope; a path remains eligible only if every edge has at least one eligible support. If support verification exhausts the budget, affected paths are omitted and the response is partial/degraded. If a Graph owner is unavailable, unverified supports are discarded; a path can remain only through another independently verified current support.

- **Intent Classification / Entity Extraction unavailable or timed out:** use `general` intent and the original query; mark `query_understanding_degraded`.
- **Lexical Retrieval unavailable:** continue with Vector Retrieval if it succeeds; add `lexical_degraded` to `degradation_reasons` and include `{service: lexical-retrieval, code: dependency_unavailable, retryable: true}` in `failures`. A successful empty lexical result is not a failure.
- **Vector Retrieval unavailable:** continue with Lexical Retrieval if it succeeds; add `vector_degraded` to `degradation_reasons` and include `{service: vector-retrieval, code: dependency_unavailable, retryable: true}` in `failures`.
- **Both retrieval paths unavailable:** return `status=failed`, `degraded=true`, and failures for both services; never a successful empty result. If exactly one retrieval path succeeds, rank its candidates normally and return `status=partial`, `degraded=true`, with the surviving path's candidates.
- **Canonical verification unavailable for a candidate's owner:** fail closed for candidates from that owner, add `freshness_verification_degraded` to `degradation_reasons`; if no verified candidates remain, return a degraded dependency failure rather than an empty-success response. Candidates from owners that remain available may still be returned.
- **Ranking unavailable or invalid response:** return `status=failed` with a Ranking failure entry. No implicit unsorted candidate fallback in v1. Ranking only orders supplied candidates; canonical freshness verification belongs exclusively to Gateway.
- **Reranking unavailable or timed out:** return the valid Ranking order with `status=partial`, `degraded=true`, `reranking_degraded` in `degradation_reasons`, and a Reranking failure entry.
- **Graph unavailable:** when relationship traversal is required, return `status=failed` unless independently verified lexical/vector evidence can be returned as a partial result with a Graph failure entry; never fabricate graph evidence. When Graph is optional, omit graph evidence and mark the response partial/degraded.
- **Embedding unavailable:** if Vector Retrieval cannot produce a query vector because Embedding is unavailable, apply the same vector-path failure rule and record `embedding` as the failed dependency and add `embedding_degraded` to `degradation_reasons`; a surviving lexical path may be returned as partial. If the profile requires vectors and no lexical path succeeds, return failed.
- **Assembly/token-budget failure:** return `status=failed` with `context_assembly_failed`; never return a context that exceeds the requested budget or silently drops required provenance.
- **Deadline exhausted before reserved verification/assembly:** fail closed and return a deadline/dependency failure, not stale or partially verified content.

All successful responses carry `degraded` and a bounded list of `degradation_reasons`. Response `index_freshness` is `current`, `pending_index`, or `unknown`; when `after_operation_id` is supplied, Gateway checks that operation's status before treating absence as definitive. An empty candidate list while the hinted operation is pending is a partial/degraded result, not a successful definitive no-match.

## Machine-checkable schemas

The normative Gateway request/response JSON Schema is in [`schemas/gateway.schema.json`](schemas/gateway.schema.json). It defines public request and response shapes, selection/outcome requests, candidate freshness states, degradation metadata, and bounds. `status=complete` means all required stages succeeded; `partial` means safe output exists with one or more explicitly reported optional/degraded stages; `failed` means no safe result can be produced.

## Acceptance tests

1. Client request traverses service REST contracts only; no direct cross-service calls/storage access.
2. Scope partition filters and required local access restrictions are propagated and enforced by target services.
3. Deadlines/cancellation propagate; retries and total attempts are bounded.
4. Intent/entity outputs influence planning but never broaden scope partition filters or local access restrictions.
5. Ranking/Reranking use bounded candidates and explicit failure/fallback behavior.
6. Context assembly respects token budget and preserves required provenance/identifiers/constraints.
7. Automatic prompt-time memory injection works without manual prompt tricks.
8. Provider prompt caching is distinct from response caching and obeys privacy/profile rules.
9. Partial failure differs from valid no-match and is visible to callers.
10. Logs avoid raw prompts/sensitive content by default.
11. Health and readiness semantics are distinct.

## Approval gate

Review with every service contract, hook/client adapters, prompt-context requirements, security/scope policy, and end-to-end acceptance workflows before implementation.
