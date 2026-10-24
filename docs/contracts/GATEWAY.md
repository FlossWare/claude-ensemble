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

## Orchestration semantics

### Selection and learning workflows

- `POST /api/v1/selections` accepts `context_id`, versioned selection `policy`, bounded `eligible_arms`, and optional `expected_state_version`. Gateway validates the request and calls `POST /api/v1/thompson/selections` over REST. The response carries `selection_id`, chosen arm, policy/state version, bounded evidence, and request ID.
- `POST /api/v1/outcomes` accepts the stable selection/context/arm identity, outcome, evidence, occurrence timestamp, and policy version. Gateway calls `POST /api/v1/learning/outcomes` over REST and returns the durable Learning operation identity/status. Learning validates and records the outcome, then calls Thompson over REST to apply the idempotent update. Thompson never calls Learning.
- Both workflows use the same deadline, idempotency, local access restrictions, and operation-status rules as other Gateway requests. They do not share service storage or invoke direct methods.

## Orchestration semantics

- Build a bounded plan using Intent Classification and Entity/Identifier Extraction where useful; choose Memory/Knowledge/Graph and lexical/vector retrieval calls based on intent, scope, and request budget. The intent vocabulary is `memory_recall`, `knowledge_lookup`, `relationship_exploration`, `troubleshooting`, `explanation`, `decision_support`, and `general`; unknown/low-confidence intent uses the bounded `general` plan. Query expansion is disabled in v1; exactly one original query is used. Reconsider expansion only with a separately reviewed policy and acceptance evidence.
- Run independent calls concurrently only when the plan, deadline, and failure policy permit. All service calls use REST and propagate correlation, deadline, cancellation, and canonical scope partition.
- Extract up to 32 exact identifiers from Entity/Identifier Extraction and preserve their exact spelling. Gateway supplies these as `exact_identifiers` to Ranking and annotates each candidate's `matched_exact_identifiers` only when the exact identifier appears in its source evidence; this creates the normative exact-match tier in `rrf-v1`.
- Fetch up to 3× the requested final candidate count, capped at 100 per retrieval path. Gateway batch-verifies candidates against their canonical owner before Ranking, with at most 100 identities per verification call. Remove any candidate whose owner reports stale, tombstoned, or not_found. If fewer than the requested count remain, perform at most one refill round within the original deadline and re-verify only the new candidates. Never return an unverified candidate as current. Then invoke Ranking; invoke Reranking only when its reserved budget remains.
- Assemble prompt context with explicit token budget, relevance, recency/authority policy where applicable, provenance, and compression rules. Compression must preserve facts, decisions, constraints, identifiers, and evidence links; it must not silently change meaning.
- Provider prompt-cache optimization is a separate concern from generic response caching. Stable prefixes may be reused only when provider semantics and privacy scope allow it.
- Automatic prompt-time memory injection must work without a manual memory instruction or special prefix. Hook/adapters call Gateway through the public contract and must not bypass service ownership.
- Partial dependency failure is explicit and governed by a documented workflow policy. An unavailable retrieval service is not treated as a successful no-match. For every candidate returned to a client or prompt context, Gateway batches source IDs and `revision_sequence` values by owner and calls Memory/Knowledge revision-verification REST endpoints before presenting candidates as current. A missing/tombstoned source or revision mismatch is filtered. If required verification is unavailable, the candidate is not exposed as current and the response marks freshness degradation; if no safe candidates remain, return an explicit degraded/failed outcome rather than claiming a successful empty search.
- Interactive API default deadline is 5 seconds. The Claude Code prompt hook has a hard 1,500 ms end-to-end deadline. Within the hook budget, Gateway reserves 250 ms for canonical freshness verification, 150 ms for Ranking, 250 ms for optional Reranking, and 100 ms for context assembly/response serialization; all other work must fit in the remaining budget. Intent and entity calls may each consume at most 200 ms and run concurrently. Each lexical/vector retrieval call is capped at 350 ms and the paths run concurrently. Graph traversal is capped at 250 ms. No service may extend the absolute caller deadline. These are acceptance targets, not measured performance claims. If a reserved stage cannot start within its budget, Gateway applies the degradation matrix below. Retries are disabled by default in the prompt-hook path and otherwise limited to one retry when at least 100 ms remains.
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

`query` is required and bounded by the configured request limit. `scope` is required unless this endpoint's deployment profile defines one unambiguous default. Optional `after_operation_id` requests read-your-writes behavior for a previously accepted Memory/Knowledge mutation. Gateway routes the status check by the owner prefix and calls that owner's top-level operation-status endpoint. If that operation is still indexing, response metadata reports `index_freshness=pending_index` rather than asserting a definitive no-result. Candidate freshness values are `verified_current`, `stale`, `tombstoned`, `not_found`, and `unverified`; only `verified_current` candidates may be returned as current. `context_budget` is bounded; the provider adapter must use the named target model's token counting when available and otherwise report that a conservative estimate was used. `mode` is `prompt_recall`, `interactive`, or `lookup`.

Response:

~~~json
{
  "request_id": "correlation-id",
  "context": "Bounded assembled context",
  "candidates": [],
  "degraded": false,
  "failures": [],
  "plan": {"intent": "general", "variants_used": 1, "policy_version": "0.1"},
  "freshness": "verified",
  "truncated": false
}
~~~

`degraded` and `failures` distinguish a partial workflow from a successful no-match. On a prompt-hook deadline or total dependency failure, the adapter fails open to the original prompt with no injected context, records a safe diagnostic, and must not claim that no memory exists. Interactive callers receive the documented error envelope when no safe result can be produced.

## Errors and fallback

Use the common REST error envelope. Distinguish invalid request, budget/deadline exceeded, dependency unavailable, partial workflow failure, and internal failure. The v1 degradation matrix is normative:

- **Intent Classification / Entity Extraction unavailable or timed out:** use `general` intent and the original query; mark `query_understanding_degraded`.
- **Lexical Retrieval unavailable:** continue with Vector Retrieval if it succeeds; mark `lexical_degraded`. A successful empty lexical result is not a failure.
- **Vector Retrieval unavailable:** continue with Lexical Retrieval if it succeeds; mark `vector_degraded`.
- **Both retrieval paths unavailable:** return a dependency failure, never a successful empty result.
- **Canonical verification unavailable for a candidate's owner:** fail closed for candidates from that owner, mark `freshness_verification_degraded`; if no verified candidates remain, return a degraded dependency failure rather than an empty-success response. Candidates from owners that remain available may still be returned.
- **Ranking unavailable or invalid response:** return a dependency failure. No implicit unsorted candidate fallback in v1.
- **Reranking unavailable or timed out:** return the valid Ranking order with `reranking_degraded` metadata.
- **Graph unavailable:** omit graph-derived candidates only when the plan does not require relationship traversal; otherwise return a dependency failure.
- **Deadline exhausted before reserved verification/assembly:** fail closed and return a deadline/dependency failure, not stale or partially verified content.

All successful responses carry `degraded` and a bounded list of `degradation_reasons`. Response `index_freshness` is `current`, `pending_index`, or `unknown`; when `after_operation_id` is supplied, Gateway checks that operation's status before treating absence as definitive. An empty candidate list while the hinted operation is pending is a partial/degraded result, not a successful definitive no-match.

## Machine-checkable schemas

The normative Gateway request/response JSON Schema is in [`schemas/gateway.schema.json`](schemas/gateway.schema.json). It defines candidate freshness states, degradation metadata, and bounds. Prose above defines orchestration behavior.

## Machine-checkable schemas

The normative Gateway request/response JSON Schema is in [`schemas/gateway.schema.json`](schemas/gateway.schema.json). It defines the public request, candidate freshness enum, degradation metadata, and response bounds.

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
