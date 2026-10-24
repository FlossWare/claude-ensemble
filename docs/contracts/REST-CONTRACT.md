# Common REST Contract Rules (Draft)

Status: proposed shared contract for architecture review. These rules apply to every logical CE service, including services co-deployed in the initial single process. They do not prescribe a language, framework, database, or separate deployment.

## Governing rule

Every service-to-service interaction uses HTTP/REST and the receiving service's contract. Direct cross-service implementation calls and direct access to another service's authoritative storage are prohibited, even when the services share a process. Service callers use stable service identities/contracts rather than hard-coded physical locations so routing can later forward requests to remote instances without changing caller business logic.

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
- `Idempotency-Key`: required for retryable POST operations that may create or mutate durable state. Scope the key to caller/operation, define retention, and return the original effective result for a repeated key with the same request. Reuse with a different request body returns a conflict.
- Caller identity and authorization context must be carried by the deployment's authenticated request mechanism. Never trust a user/project scope supplied in the body without server-side authorization. Exact authentication headers/transport are deployment decisions and must be standardized before external exposure.

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
| 401 | Missing/invalid authentication | `unauthenticated` |
| 403 | Caller lacks access to the requested scope/resource | `forbidden` |
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

Each service exposes:

- `GET /api/v1/health`: process/liveness health only. It must not claim that dependencies or data are ready.
- `GET /api/v1/ready`: whether the service can safely fulfill its documented responsibilities. Include a bounded, privacy-safe summary of required dependency/state readiness and degraded conditions.

Readiness must distinguish unavailable state/dependencies, pending recovery/index work where relevant, and a valid empty corpus/result. Health and readiness responses must not leak secrets or sensitive content.

## Provenance and result semantics

Where an operation returns sourced or derived evidence, the response must preserve relevant source identity, revision, stable record/chunk identity, source location when available, retrieval path, and policy/model/profile versions that materially affect the result. A service must not fabricate missing provenance. Derived index representations must be traceable to their authoritative source revision.

A result list should make its limit and truncation explicit. Candidate scores are meaningful only with a declared score type/producer and applicable policy/model version. Different retrieval scores must not be treated as directly comparable unless Ranking's contract defines the normalization/fusion semantics.

## Security, privacy, and scope

- Enforce authorization and user/project/source scope at the owning service. Gateway filtering is not a substitute for domain enforcement.
- Missing or invalid scope must fail safely and must never broaden access.
- Do not log raw prompts, Memory/Knowledge content, embedding input text, secrets, or full candidate payloads by default. Log correlation ID, endpoint, duration, outcome category, effective policy/model versions, bounded counts, and safe diagnostics.
- Diagnostics and errors must not disclose whether an unauthorized caller's private resource exists when that distinction would leak information.

## Composition and decorators

When a service contract is designed, consider whether useful implementations can be composed/decorated without changing the contract (for example, caching, metrics, tracing, or resilience wrappers). This is a design consideration, not a mandate to build decorators. Decorators must preserve contract semantics, deadlines, cancellation, provenance, authorization, and idempotency; they must not create unbounded retries or bypass service boundaries.

## Federation readiness

- Callers target a logical service contract through configurable routing, not embedded host/port assumptions.
- The initial local router may resolve every service to the same REST server. A later router may forward selected service calls to remote instances.
- Remote forwarding must preserve request ID, trace context, deadline, caller identity/scope, idempotency key, and error semantics.
- Federation changes routing/configuration and operational controls; it must not require caller business-logic changes while the service contract remains compatible.
- Do not claim multi-host safety from single-process tests. Federation requires additional network failure, authentication, concurrency, and recovery acceptance tests.

## Contract acceptance checklist

For every service endpoint, specify and test:

1. Method, path, request/response schema, content type, size limits, and API version.
2. Authentication/authorization and user/project/source scope.
3. Owned data and side effects, including revision/conflict semantics.
4. Stable error codes/statuses, retryability, idempotency, and partial-failure semantics.
5. Deadline budget, timeout, cancellation, retry policy, and downstream call limits.
6. Correlation/provenance and privacy-safe diagnostics.
7. Health/readiness behavior and degraded dependency semantics.
8. Compatibility/version behavior and effective model/profile/policy identity.
9. Contract tests independent of implementation language, plus integration and failure-injection tests.
10. A decorator/composition review and a documented reason if no meaningful composition point exists.

No implementation begins solely because this shared draft exists. The service inventory, responsibility matrix, endpoint contracts, and acceptance criteria must be reviewed together first.
