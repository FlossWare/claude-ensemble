# Service Isolation and Contract Testing

Status: normative testing requirement for every FlossWare Claude Ensemble logical service.

## Required test layers

Every logical service MUST be testable in isolation. A service test MUST NOT require another real CE service to be running. When behavior depends on another service, use a mock HTTP/REST endpoint implementing that dependency's published contract. Mock the network boundary, not the service's own core behavior.

1. **Pure unit tests:** exercise deterministic algorithms, validation, mapping, identity, limits, and state transitions without network or persistent infrastructure.
2. **Service contract tests:** start only the service under test with an isolated test store and mock REST dependencies. Send HTTP requests through its own REST router; validate requests/responses against normative JSON Schemas and assert status/error envelopes, headers, deadlines, cancellation, idempotency, and limits.
3. **Dependency-failure tests:** make each mocked dependency return success, valid empty, malformed response, 4xx, 5xx, timeout, connection reset, and delayed response. Assert bounded retries and truthful degraded/failed status.
4. **Dispatcher integration tests:** separately run the real single-process REST dispatcher with multiple real service routers to test routing, nested-call starvation, cancellation, and deadline propagation. These do not replace isolated tests.
5. **End-to-end acceptance tests:** exercise only explicitly named vertical slices after isolated suites pass.

## Mock rules

- Mock outbound dependencies at HTTP/REST boundaries using the dependency's real contract schema and representative fixtures. Do not mock a service's own handler, core algorithm, or state machine in its service contract tests.
- Every mock records method, path, headers, body, request ID, deadline, and call count. Tests assert exact call shape and bounded retry count.
- Provide deterministic controls for clock, timers, response gates, crash points, and injected failures. Do not use wall-clock sleeps as the sole proof of a race or deadline.
- Unknown/unmocked outbound destinations fail the test immediately. No test may silently reach a developer's running service or external network.
- Validate mock fixtures against the same schema used by the consumer. Consumer contract changes update provider fixtures and acceptance cases in the same change.
- Keep service-owned persistence isolated per test (ephemeral database, temporary namespace, or deterministic in-memory adapter as appropriate). Never share another service's storage or fixtures as a substitute for REST calls.
- Assert there are no direct cross-service method calls and no cross-service storage access. A same-process deployment does not weaken this rule.
- Test doubles may simplify infrastructure, but must preserve the dependency's observable HTTP contract, failure modes, idempotency, and timing behavior relevant to the scenario.

## Required isolated suite per service

| Service | Mocked outbound REST dependencies | Minimum isolated assertions |
|---|---|---|
| Gateway | Every downstream service it invokes | Planning, deadlines, degradation matrix, freshness verification, one bounded refill, prompt-hook fail-open, safe metadata |
| Memory | Index, Chunking, Tokenization, Embedding, Graph | Canonical revision/tombstone state, preflight rejection, 202 async lifecycle, idempotency, journal replay, sequence recovery |
| Knowledge | Index, Chunking, Tokenization, Embedding, Graph | Canonical source/revision/provenance, source identity, preflight rejection, 202 async lifecycle, idempotency, journal replay |
| Graph | None for query/deletion; callers are inbound | Multi-source supports, source tombstones, stale retry rejection, bounded traversal, operation status, restart recovery |
| Thompson | None | Eligible-arm constraints, state versions, policy semantics, duplicate event handling, conflict/recovery |
| Learning | Thompson | Evidence validation, durable operation status, one-way update, idempotent retry, rejected event has no effect |
| Index | None for normal operations; owners push reconciliation | Profile registry, atomic per-source publication, index-wide tombstone checks, dual-apply to building generations, seal/cutover, abandon |
| Chunking | None | Deterministic chunk boundaries/IDs, profile versioning, preview matches actual chunk count/encoded size, Unicode offsets |
| Tokenization | None | Batch item mapping, normalization/profile compatibility, exact identifier preservation, Unicode offsets, per-item errors |
| Embedding | Index profile registry/profile fixture | Query/document mode, dimensions, finite values, normalization, model/profile mismatch, batch mapping |
| Lexical Retrieval | Index, Tokenization | Profile mismatch, scoped statistics, deterministic scoring/ranks, empty vs unavailable, bounded candidates |
| Vector Retrieval | Index, Embedding | Input type/model/dimension/metric compatibility, bounded neighbors, rank assignment, empty vs unavailable |
| Intent Classification | None | Label vocabulary, confidence/fallback, bounded results, timeout/error mapping |
| Entity and Identifier Extraction | None | Exact spelling, typed identifiers, Unicode code-point spans, uncertainty, malformed/overlong input |
| Ranking | None | Fixed-point RRF, list identity, per-list deduplication, exact-ID tier, stable tie-breaking, bounds |
| Reranking | None | Candidate identity preserved, bounded input/output, deterministic model adapter double, timeout behavior, no invented provenance |

## Testability gate

A service is not implementation-ready until its contract names request/response schemas; status/error codes; dependencies; timeout/deadline; idempotency/retry semantics where applicable; state ownership; and isolated test scenarios. A missing dependency must be mockable using a published contract, not inferred from implementation internals.

Passing isolated mocks alone does not prove the whole system works. The first vertical slice also requires real-dispatcher integration and end-to-end acceptance tests.
