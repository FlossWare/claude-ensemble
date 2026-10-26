# Service Testing Standard

Status: required engineering standard for Claude Ensemble service implementations.

## Purpose

Every logical service is independently testable and must demonstrate contract correctness, expected behavior, safe failure, and compatibility with its callers before its implementation is considered complete. Tests are deliverables, not post-implementation cleanup.

## Required test layers

Each service implementation must include the applicable layers below. The service PR must identify any layer marked not applicable and explain why.

1. **Unit tests**: deterministic business logic, validation, boundary values, empty/maximum inputs, ordering, identity, and error paths. These tests should be fast and isolated.
2. **Contract tests**: validate representative valid and invalid requests, successful responses, and error responses against the normative JSON Schemas and endpoint metadata. Test unknown fields and missing required fields where schemas prohibit them.
3. **HTTP/API tests**: exercise the actual local HTTP boundary for routes, methods, status codes, media types, correlation IDs, serialization, malformed payloads, body limits, and safe errors.
4. **Integration tests**: verify real interactions between service boundaries and the relevant dependent services or adapters. Keep the logical REST contract even when services share one process.
5. **Persistence tests** (where applicable): use the real test storage engine for transactions, uniqueness, ordering, idempotency, consistency, and reopen/restart behavior. An in-memory fake alone is insufficient evidence for durable guarantees.
6. **Failure/recovery tests** (where applicable): inject timeouts, unavailable dependencies, interrupted writes, process termination, retries, replay, and recovery. Verify that a timeout is not incorrectly treated as proof that a mutation did not happen.
7. **Concurrency tests** (where applicable): exercise simultaneous reads/writes and mixed workflows, assert bounded completion and consistency, and detect deadlock/starvation without assuming every operation succeeds under an unrealistic deadline. Before a dispatcher is used for nested service-to-service REST calls, add saturation tests for nested-call starvation and any required control lane; a worker-count cap alone does not prove reentrant dispatch is safe.
8. **Security and resource-boundary tests**: validate input constraints, scope/ownership checks, resource limits, safe diagnostics, and that failures never broaden access or leak private content.
9. **Regression tests**: every fixed defect that could recur gets a focused regression test.

## Mocking policy

Mocks are optional and must serve a clear isolation purpose; there is no quota for mocks.

- Prefer real pure-function inputs for algorithm tests.
- Use mocks, fakes, or stubs to isolate an external provider, clock, random source, network failure, or expensive/non-deterministic dependency when the test specifically concerns the service's behavior around that dependency.
- Use a real local HTTP server for HTTP behavior when practical; do not mock the HTTP stack in tests intended to validate routes, headers, serialization, or status codes.
- Use the actual test database/storage engine for persistence guarantees. Test doubles may supplement these tests, not replace them.
- Add fault injection at a controllable seam to verify timeout, retry, cancellation, partial failure, and recovery behavior.
- Avoid mocks that reproduce the implementation's assumptions so closely that the test can pass while the real contract is broken.

## Contract and boundary requirements

- Validate successful and error payloads against the canonical schema, including required fields and additionalProperties restrictions.
- Assert stable machine-readable error codes and status mappings; do not assert only message text.
- Assert request_id in the response body matches X-CE-Request-ID.
- Verify request IDs, deadlines, and retryability follow the shared REST contract.
- Test invalid media types, malformed UTF-8/JSON, missing fields, wrong types, unsupported values, and unknown fields.
- Test just-below, exactly-at, and just-above important limits, including encoded byte size versus character count.
- Verify empty results are distinguished from errors and that each endpoint follows its schema's empty-result semantics.
- Verify deterministic outputs across fresh processes for deterministic services.

## CI and completion gate

The service PR must include:

- a test matrix describing applicable layers and the relevant test modules;
- automated schema validation and the full repository test suite;
- integration and failure-injection coverage appropriate to the service's responsibilities;
- evidence that CI ran against the PR's current head commit and passed;
- documented coverage gaps, with follow-up issues only when the gap is genuinely outside the increment's scope.

A service is not complete merely because tests were authored or a workflow passed on a different commit. A failing or unverified gate blocks merge unless an explicit owner decision documents the exception.

## Chunking-specific minimums

Chunking tests must cover media-type-specific heading provenance (`text/plain`, `text/markdown`, missing and other media types), Unicode and exact source offsets, line spans and heading context, bundle-pinned overlap and maximum chunk size, deterministic output and stable IDs, policy/version changes, invalid and unknown profiles, empty/boundary/oversized input, option type validation, response/request/error schema conformance, HTTP errors and correlation IDs, and preflight bounds. Tests must prove that a policy inconsistent with the digest-verified Index bundle is rejected. Because Chunking has no persistent side effects, database recovery tests do not apply; process-boundary determinism does.
