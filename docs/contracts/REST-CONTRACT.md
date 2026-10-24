# Common REST Contract Rules (Draft)

Status: proposed shared contract for architecture review. These rules apply to every logical CE service, including services co-deployed in the initial single process. They do not prescribe a language, framework, database, or separate deployment.

## Governing rule

Every service-to-service interaction uses HTTP/REST and the receiving service's contract. Direct cross-service implementation calls and direct access to another service's authoritative storage are prohibited, even when the services share a process. Service callers address logical service contracts through the initial local REST dispatcher. Do not add remote routing or federation abstractions in the initial implementation.

## HTTP conventions

- Base path: `/api/v1`. Version the public contract, not implementation/build versions. Compatible additive changes may remain in v1; incompatible schema or semantic changes require a new API major version.
- Use standard HTTP methods and status codes. GET is safe and read-only; PUT is idempotent replacement/upsert where documented; DELETE is idempotent in its externally observable result; POST is used for creation or operations that are not naturally idempotent.
- Use UTF-8 JSON with `Content-Type: application/json` and `Accept: application/json` unless a specific endpoint contract declares otherwise.
- Reject malformed, unsupported, oversized, or semantically invalid requests explicitly. Do not silently broaden scope, substitute a different model/profile, or change requested behavior without reporting the effective choice.
- Bound request size, response size, list sizes, candidate counts, pagination, and processing work. Each endpoint documents its limits.
- Return stable identifiers and explicit effective policy/profile/model versions where those affect semantics.
- Avoid exposing internal stack traces, secrets, raw prompts, or retrieved private content in errors and default logs.

## Common request metadata

Headers are optional only where noted; every request must receive a server-generated correlation ID if none is supplied.

- `X-CE-Request-ID`: caller-supplied correlation identifier, if present. Validate length/characters and propagate it unchanged through the call chain. If absent, generate one. Return it on every response.
- `traceparent`: optional W3C trace context. Validate and propagate when supported; tracing must not be required for correctness.
- `X-CE-Deadline`: absolute deadline in RFC 3339 UTC. The caller sends the overall request deadline; each service computes remaining budget and must not extend it. If absent, apply a documented configured default. Reject malformed deadlines.
- `Idempotency-Key`: required for retryable POST operations that may create or mutate durable state. Scope the key to logical operation and source owner, and retain the key-to-payload/result binding for at least 30 days after terminal completion; never expire a pending/reconciliation-required operation. Reuse with a different request body returns conflict. After the retention window, clients must use the durable operation ID/status contract rather than assume a repeated expired key will replay the prior result. Tombstone high-water marks must outlive idempotency records and any possible delayed retry; source identity reuse is prohibited unless an explicitly newer revision is created.
- The initial deployment is a single local instance. Do not build a generalized identity, authentication, or cross-instance authorization mechanism. Document and enforce only the local access assumptions actually required by the deployment. Scope fields identify data partitions; they do not themselves grant access.

Services must not accept a deadline that permits work beyond the caller's deadline. A downstream call's timeout is bounded by the lesser of the remaining request budget and the service's configured per-call cap.

## Cancellation, timeouts, retries, and side effects

- Every endpoint documents a maximum execution time and whether cancellation is supported. Propagate cancellation when the client disconnects or the deadline expires; stop work where safe. Cancellation is best-effort for already committed durable side effects, which must remain consistent and observable.
- A timed-out request is not proof that the operation did not happen. Mutating operations need idempotency/reconciliation semantics so callers can safely determine or repeat the outcome.
- Retry only when the error is explicitly retryable, the operation is safe/idempotent or carries a valid idempotency key, and enough deadline budget remains.
- Retries are bounded by both attempt count and elapsed deadline. Use backoff with jitter. Never retry validation/authorization errors, never retry indefinitely, and avoid retries at multiple layers that multiply attempts.
- Distinguish a failed dependency from a valid empty result. Partial success must identify which paths succeeded/failed and must not represent failed retrieval as zero matches.
- Do not hide a side effect behind a nominally read-only endpoint.

## Common success and error semantics

Successful responses use the endpoint's documented schema. Empty collections are valid successful results when the operation actually completed.

Errors use this envelope:

```json
{
  "error": {
    "code": "stable_machine_code",
    "message": "Safe, actionable summary",
    "retryable": false,
    "details": {}
  },
  "request_id": "correlation-id"
}
```

- `error.code` is stable and machine-readable; callers must not branch on message text.
- `error.message` is safe for clients and excludes secrets, stack traces, and private content.
- `error.retryable` indicates whether retry may be considered, subject to operation idempotency and remaining deadline.
- `error.details` is optional structured validation or recovery context; it must not expose sensitive data.
- `request_id` matches the response correlation header.
- Every error response includes `X-CE-Request-ID`.

Minimum status conventions:

| HTTP status | Meaning | Typical stable codes |
| --- | --- | --- |
| 400 | Malformed request or invalid parameter | `invalid_request`, `invalid_parameter` |
| 401 | Missing/invalid authentication, if enabled by the deployment | `unauthenticated` |
| 403 | Caller lacks access to the requested scope/resource, where access control applies | `forbidden` |
| 404 | Resource or endpoint does not exist | `not_found` |
| 409 | State/version/idempotency conflict | `conflict`, `idempotency_conflict`, `revision_conflict` |
| 413 | Request exceeds a documented size limit | `request_too_large` |
| 415 | Unsupported media type | `unsupported_media_type` |
| 422 | Valid syntax but unsupported/invalid domain input | `unsupported_profile`, `incompatible_representation` |
| 429 | Caller or service rate limit reached | `rate_limited` |
| 500 | Unexpected internal failure | `internal_error` |
| 502 | Invalid/unusable downstream response | `upstream_failure` |
| 503 | Service/dependency temporarily unavailable or not ready | `service_unavailable`, `dependency_unavailable`, `not_ready` |
| 504 | Deadline exceeded while waiting for work/dependency | `deadline_exceeded` |

Endpoint contracts may refine status use, but must not contradict these meanings without an explicit architecture decision. Do not return 200 with an error-shaped payload.

## Readiness and health

Because the initial deployment has one REST server for all logical services, health routes are service-qualified and must not collide:

- `GET /api/v1/{service}/health`: process/service liveness only. It must not claim that dependencies or data are ready.
- `GET /api/v1/{service}/ready`: whether that logical service can safely fulfill its documented responsibilities. Include a bounded, privacy-safe summary of required dependency/state readiness and degraded conditions.

`{service}` is the stable lowercase service route segment already used by that service's endpoints (for example, `gateway`, `memory`, `entity-extraction`). A shared server must dispatch each route to the named logical service. Contracts must not define competing unqualified `/api/v1/health` or `/api/v1/ready` handlers.

Readiness must distinguish unavailable state/dependencies, pending recovery/index work where relevant, and a valid empty corpus/result. Health and readiness responses must not leak secrets or sensitive content.

## Provenance and result semantics

Where an operation returns sourced or derived evidence, the response must preserve relevant source identity, revision, stable record/chunk identity, source location when available, retrieval path, and policy/model/profile versions that materially affect the result. A service must not fabricate missing provenance. Derived index representations must be traceable to their authoritative source revision.

A result list should make its limit and truncation explicit. Candidate scores are meaningful only with a declared score type/producer and applicable policy/model version. Different retrieval scores must not be treated as directly comparable unless Ranking's contract defines the normalization/fusion semantics.

## Single-process REST dispatch and concurrency

The local dispatcher is one server for multiple logical services. Its execution model is an implementation choice, but it MUST guarantee that nested/concurrent REST calls cannot exhaust all request capacity while handlers wait for work that needs the same exhausted capacity. Implementations may use non-blocking I/O, reentrant scheduling, or isolated capacity pools; no specific language/runtime is mandated. Long-running or multi-stage mutations that cannot reliably finish inside the request deadline return `202 Accepted` with a durable `operation_id` and status endpoint. Do not hold a scarce inbound handler/connection slot while synchronously waiting for downstream work if that can prevent the downstream request from being dispatched. Cancellation stops safe in-flight work, but does not undo committed durable effects.

The concurrency guarantee is tested with mixed concurrent ingestion and retrieval plus fault injection. A stress test must assert no deadlock/starvation and deadline-bounded outcomes; it must not assert that an arbitrary number of operations all succeed inside a single 5-second deadline.

## Canonical scope and identity semantics

Use the same scope object across service contracts:

~~~json
{
  "scope": {
    "type": "project",
    "id": "stable-scope-id",
    "visibility": "private"
  }
}
~~~

- Allowed scope types are user, project, shared, and global. A service may support a narrower subset and must reject unsupported types explicitly. Scope is a partition/filtering semantic, not proof of identity or authorization.
- Do not accept caller-supplied owner/principal fields as trusted identity. Any local access restrictions required by the initial deployment are enforced at the owning service.
- Visibility is a data classification/filter, not an authorization grant. It does not replace any local access restrictions the deployment actually requires.
- Missing scope is allowed only for endpoints whose contract explicitly defines an unambiguous default. No service may silently fall back to a broader scope.
- Source identity is a stable, namespaced source ID. A source revision has both an opaque revision ID and a monotonically increasing per-source revision sequence. Never compare opaque revision strings lexicographically to decide which revision is newer.
- A chunk ID is stable within a source revision and chunker profile/version. Candidate identity is the tuple (source ID, revision sequence, chunk ID, chunker profile/version); services must not deduplicate distinct source revisions as though they were the same evidence.
- Index publication and deletion checks use the revision sequence plus tombstone state to reject stale writes. Revision sequence allocation is owned by the authoritative source service, Memory or Knowledge.

## Default operational bounds

Unless a service contract explicitly overrides these defaults, request bodies are limited to 1 MiB, collection/candidate responses to 100 items per call, and synchronous request execution to a 5-second default deadline. Long-running work must use an operation ID and expose status rather than silently extending the request deadline. Service-specific documented limits override these defaults for the relevant endpoint; all overrides must remain bounded and be reflected in acceptance tests. A caller's explicit deadline may be shorter than the configured default and must never be extended by a downstream service.

## Local access assumptions, privacy, and scope

- Enforce only the local access restrictions genuinely required by the initial single-instance deployment, at the owning service. No generalized authentication, distributed identity, or authorization framework is assumed. Gateway filtering is not a substitute for owner-enforced local restrictions where those are required.
- Missing or invalid scope must fail safely and must never broaden the data partition.
- Do not log raw prompts, Memory/Knowledge content, embedding input text, secrets, or full candidate payloads by default. Log correlation ID, endpoint, duration, outcome category, effective policy/model versions, bounded counts, and safe diagnostics.
- Diagnostics and errors must not disclose whether an unauthorized caller's private resource exists when that distinction would leak information.

## Composition and decorators

When a service contract is designed, consider whether useful implementations can be composed/decorated without changing the contract (for example, caching, metrics, tracing, or resilience wrappers). This is a design consideration, not a mandate to build decorators. Decorators must preserve contract semantics, deadlines, cancellation, provenance, authorization, and idempotency; they must not create unbounded retries or bypass service boundaries.

## Deferred concerns

Federation, remote routing, distributed identity, cross-instance authentication, and federation-specific authorization are explicitly out of scope. Do not design for them or treat them as implementation blockers now. Revisit them only if federation becomes a concrete requirement.

## Contract acceptance checklist

## Contract acceptance checklist

For every service endpoint, specify and test:

1. Method, path, request/response schema, content type, size limits, and API version.
2. Scope semantics and any local access restrictions actually required by the initial deployment; no generalized authentication framework is assumed.
3. Owned data and side effects, including revision/conflict semantics.
4. Stable error codes/statuses, retryability, idempotency, and partial-failure semantics.
5. Deadline budget, timeout, cancellation, retry policy, and downstream call limits.
6. Correlation/provenance and privacy-safe diagnostics.
7. Health/readiness behavior and degraded dependency semantics.
8. Compatibility/version behavior and effective model/profile/policy identity.
9. Contract tests independent of implementation language, plus integration and failure-injection tests.
10. A decorator/composition review and a documented reason if no meaningful composition point exists.

No implementation begins solely because this shared draft exists. The service inventory, responsibility matrix, endpoint contracts, and acceptance criteria must be reviewed together first.


Default cancellation rule: synchronous endpoints honor disconnect/deadline cancellation on a best-effort basis. Cancellation does not roll back a durable mutation that has already committed; the result remains queryable by operation identity. Long-running work reports status through an operation ID rather than extending the request deadline.
