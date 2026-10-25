# Embedding Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. No provider, SDK, database, or inference runtime is prescribed.

## Responsibility

Generate embeddings for supplied text under an explicitly named, versioned embedding profile. The service owns profile resolution, input validation, provider/model invocation, vector normalization required by the profile, bounded batching, and per-item result/error semantics.

It does not own source records, chunking, lexical tokenization, index storage, retrieval, ranking, or prompt-context assembly. Callers invoke it through REST. Index stores derived vectors; Memory and Knowledge remain authoritative for source content.

## Endpoints

- POST /api/v1/embeddings: embed one or more text inputs.
- GET /api/v1/embedding/health: liveness.
- GET /api/v1/embedding/ready: ability to accept requests under the configured profile/provider readiness policy.

## Request

~~~json
{
  "profile": "technical-default",
  "profile_version": "0.1",
  "inputs": [
    {"input_id": "chunk-123", "input_type": "document", "text": "Example technical content"}
  ],
  "normalize": "profile-default"
}
~~~

The profile resolves to a pinned provider/model identity, model revision where available, dimensions, input modality, normalization policy, and any required preprocessing. Callers may not silently override model identity or dimensions per request. Query and document embeddings must use compatible profiles. If a provider offers distinct query/document modes, the profile must specify which mode is being requested and compatibility rules.

## Response

~~~json
{
  "profile": "technical-default",
  "profile_version": "0.1",
  "model": {
    "provider": "provider-id",
    "model_id": "model-id",
    "model_version": "model-revision",
    "dimensions": 2,
    "normalization": "l2"
  },
  "results": [
    {
      "input_id": "chunk-123",
      "input_type": "document",
      "status": "complete",
      "vector": [0.01, 0.02],
      "dimensions": 768
    }
  ],
  "request_id": "correlation-id"
}
~~~

Vector values above are illustrative; real responses must have exactly the declared number of finite numeric values. Contract tests must verify length, finiteness, and normalization within a documented tolerance. Do not return a vector with fabricated, truncated, padded, or silently coerced dimensions.

## Semantics

- Each input explicitly declares `input_type` as `document` or `query`; provider-specific query/document modes are resolved from that value under the pinned profile. Incompatible modes are rejected rather than silently embedded as the wrong type.
- Preserve input-to-result identity; result order alone is not a correlation mechanism.
- A batch may report per-item success or failure only if partial success is explicitly represented. Never silently omit failed items.
- Profile/model identity and dimensions are returned with results and recorded by Index alongside each representation.
- The profile defines normalization behavior. The service must not normalize some results and leave others unnormalized under the same profile.
- Embedding requests are bounded and deadline-aware. Retries are bounded and only retry transient provider failures; validation and profile errors are not retried.
- If the caller times out, it must not assume the provider did no work. The embedding endpoint is computationally idempotent by input/profile, but providers may still charge for repeated calls.
- Do not log raw input text, credentials, or provider response bodies by default. Logs use correlation IDs, profile/model identifiers, counts, latency, and safe error codes.
- Provider-specific quotas, data retention, and processing location are configuration/operational constraints. A profile must not route data to a provider that violates the caller's approved policy.
- This service does not persist source text or vectors as authoritative data. Any cache is an explicit bounded optimization with profile/version in the key and must not alter semantics.

## Initial bounds

- Maximum 64 inputs per request and 512 KiB encoded request body.
- Each input must fit the profile's declared provider token/input limit. The service rejects oversized inputs explicitly rather than silently truncating.
- The service returns per-item statuses and safe error codes; no unbounded provider payloads or raw exception strings.
- Deployments document provider-specific rate limits, timeouts, maximum dimensions, and configured profile registry.

## Errors

Use the common REST error envelope. Distinguish invalid input, unknown/incompatible profile, input too large, unsupported policy/profile, provider rate limit, provider unavailable, deadline exceeded, and internal failure. A valid empty input batch is rejected as invalid; a valid input that produces a zero vector or non-finite vector is a provider/profile failure, not a successful embedding.

## Acceptance tests

1. Stable input IDs map results to the correct inputs regardless of provider response order.
2. Result dimensions match the resolved profile exactly; non-finite values are rejected.
3. Profile/version/model identity is explicit; document and query input modes select the configured provider mode and incompatible modes are rejected.
4. Batch limits and per-input provider limits are enforced without silent truncation.
5. Partial batch failures are explicit and retryable only when the error is transient.
6. Deadlines and cancellation are propagated; retry count and total time are bounded.
7. Logs omit raw text and credentials by default.
8. Provider policy/configuration prevents prohibited routing.
9. Health and readiness have distinct liveness/readiness meanings.
10. Contract tests can run against a deterministic fake provider; provider integration tests are separate and clearly labeled.

## Approval gate

This contract is a draft for architecture review. It must be reconciled with the common REST contract, Index profile schema, Tokenization/Chunking outputs, and end-to-end ingestion/retrieval acceptance tests before implementation.
