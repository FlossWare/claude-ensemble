# Chunking Service Contract (Draft)

Status: contract baseline approved by merged PR #8; the initial runtime implementation is under review in PR #9. The contract remains normative, and passing static validation alone does not establish runtime conformance.

## Responsibility

Produce deterministic, versioned chunks from source content for indexing and retrieval. The service owns chunk-boundary semantics and exposes one canonical chunker version. It does not own canonical source records, corpus revisions, lexical indexes, embeddings, or vector storage; those belong to their respective owners.

## HTTP API

Base path: `/api/v1`

### `POST /chunking/chunks`

Transform one source document into chunks. The operation is deterministic for the same content, source identity/revision, and effective policy. Every request carries the immutable Index-owned bundle identity `{name, version, digest}` and the complete `profile_bundle`; Chunking verifies the bundle digest and identity, then verifies that the effective Chunking profile, version, maximum size, and overlap match the bundle.

Request:

<!-- schema-example: docs/contracts/schemas/chunking.schema.json#/$defs/chunkRequest -->
```json
{
  "index_profile": {"name": "default", "version": "0.1", "digest": "16f97decdb831addaf3656c31387704cf795c0b869d93326817baa2b4a5f4074"},
  "source": {
    "source_id": "knowledge:kn_01J7M6P4V9Q2R8T6W3X5Y0ZABC",
    "revision": "rev-17",
    "revision_sequence": 17,
    "media_type": "text/markdown",
    "content": "# Design\n..."
  },
  "profile_bundle": {
    "name": "default",
    "version": "0.1",
    "status": "active",
    "chunking": {
      "profile": "markdown-default",
      "version": "0.1",
      "max_units": 1200,
      "overlap_units": 120
    },
    "tokenization": {"profile": "technical-default", "version": "0.1"},
    "lexical": {"profile": "default", "version": "0.1", "statistics_policy": "scope_partition"},
    "embedding": {
      "required": false,
      "profile": "default",
      "version": "0.1",
      "model": "none",
      "model_version": "none",
      "input_types": ["document"],
      "dimensions": 1,
      "normalization": "none",
      "metric": "cosine",
      "max_input_tokens": 1000
    },
    "limits": {
      "max_chunks": 1,
      "max_source_bytes": 262144,
      "max_chunk_text_bytes": 65536,
      "max_request_bytes": 1048576,
      "max_chunk_representation_bytes": 900000,
      "max_envelope_bytes": 65536,
      "max_metadata_bytes": 8192,
      "max_lexical_terms_per_chunk": 512,
      "max_lexical_term_bytes": 128
    },
    "digest": "16f97decdb831addaf3656c31387704cf795c0b869d93326817baa2b4a5f4074"
  },
  "policy": {
    "profile": "markdown-default",
    "profile_version": "0.1",
    "max_units": 1200,
    "overlap_units": 120,
    "unit": "unicode_code_points"
  },
  "options": {
    "include_text": true,
    "include_line_spans": true
  }
}
```

Both `/chunks` and `/preflight` validate the complete bundle structure, digest, and identity. The `chunking` component in the Index bundle pins `profile`, `version`, `max_units`, and `overlap_units`; these behavior-changing parameters are digest-covered. The caller may omit `policy` on `/chunks`, in which case the service derives it from the validated bundle rather than from a process-local default. An explicit policy must exactly match the bundle or the request fails with `409 profile_mismatch`. Preflight's `chunking_profile` must likewise match all four pinned values.

Response:

<!-- schema-example: docs/contracts/schemas/chunking.schema.json#/$defs/chunkResponse -->
```json
{
  "index_profile": {"name": "default", "version": "0.1", "digest": "16f97decdb831addaf3656c31387704cf795c0b869d93326817baa2b4a5f4074"},
  "source_id": "knowledge:kn_01J7M6P4V9Q2R8T6W3X5Y0ZABC",
  "source_revision": "rev-17",
  "revision_sequence": 17,
  "chunker": {
    "profile": "markdown-default",
    "version": "0.1"
  },
  "chunking_profile": {"profile": "markdown-default", "version": "0.1"},
  "chunks": [
    {
      "chunk_id": "opaque-stable-id",
      "ordinal": 0,
      "text": "# Design",
      "start_offset": 0,
      "end_offset": 8,
      "start_line": 1,
      "end_line": 1,
      "heading_path": ["Design"],
      "metadata": {}
    }
  ],
  "request_id": "correlation-id"
}
```

Offsets are zero-based, half-open Unicode code-point offsets into the exact submitted content. Line numbers are one-based and inclusive. Heading paths are derived only when `source.media_type` is exactly `text/markdown`; `text/plain`, a missing media type, and other media types produce an empty `heading_path`. The runtime still reports source offsets and line spans for those inputs because those are calculated directly from the submitted text.

## Semantics

- Chunk ordering is deterministic and `ordinal` is contiguous from zero.
- Chunk identity is stable for identical source identity, source revision, effective policy/version, and chunk content/boundaries. It must not depend on process-local state or random IDs.
- Include effective policy identity/version in responses and diagnostics.
- Chunk text must map to the source offsets. Any normalization that changes text must be explicit and must preserve a source mapping.
- Overlap must be deterministic and bounded by policy. The response must not silently exceed the requested maximum unit size except where a documented indivisible unit requires it.
- Heading/source-line provenance is preserved when available.
- Only `markdown-default@0.1` is supported. Any different profile or version requires an explicit contract, schema, runtime, and test change.
- Repeated identical requests are safe and have no persistent side effects.
- The service must define size limits and reject invalid policies rather than silently substituting values.

## Machine-checkable schemas

The normative chunk and preflight request/response schemas are in [`schemas/chunking.schema.json`](schemas/chunking.schema.json). The preflight schema includes the profile identity and conservative representation-size bound used before canonical commit.

## Errors

Unsupported HTTP methods return `405 method_not_allowed` using the shared CE REST error envelope and request-ID header. Arbitrary unrecognized verbs are routed through that same handler rather than the standard library's uncorrelated `501`. `HEAD` returns `405` with the same error metadata and request-ID headers but no body, as required by HTTP semantics; its `Content-Length` describes the suppressed error representation. Other errors use the same envelope. At minimum distinguish malformed request, unsupported media type, unknown profile/version, invalid policy, content too large, and internal processing failure. Include a stable error code, safe message, retryability, and correlation ID. Client errors are not retryable without changing the request; transient internal failures may be retryable.

## Readiness and diagnostics

Expose `GET /api/v1/chunking/health` and `GET /api/v1/chunking/ready`. Readiness reports whether the canonical `markdown-default@0.1` implementation is available. Diagnostics include effective profile/version and duration, but do not log document content by default.

The runtime supports only `markdown-default@0.1`. Other profile names and versions are rejected as `unsupported_profile`; adding another profile requires a concrete use case and a contract change. If `policy` is omitted, the runtime uses the policy pinned in the supplied Index bundle; it does not substitute local defaults. The canonical profile recognizes ATX headings only: Setext headings and headings inside fenced code blocks are not interpreted as structural headings in this initial implementation. `options.include_text=false` omits each chunk's `text` field; offsets and identifiers remain available.

The local runtime uses a bounded threaded HTTP server with at most 32 active request handlers and a listen backlog of 64; when handler capacity is exhausted, excess connections receive a correlated `503 service_unavailable` error instead of spawning unbounded threads. This is a local guardrail, not a substitute for deployment-level admission control. `X-CE-Deadline` must use an RFC 3339 UTC timestamp ending in `Z`; non-standard JSON constants (`NaN`, `Infinity`, and `-Infinity`) and duplicate object keys are rejected. The normal chunks endpoint has a 300,000-byte HTTP request-body cap and independently enforces the 262,144-byte UTF-8 source-content cap. Preflight has a 2 MiB request-body cap because the resolved profile bundle accompanies the source. Callers must not treat the larger preflight envelope allowance as permission to submit source content larger than 262,144 UTF-8 bytes. Both endpoints enforce a 30-second absolute request budget by default; a valid `X-CE-Deadline` may shorten that budget. A body-receipt inactivity timeout returns `408 request_timeout`, while expiry of the absolute request deadline returns `504 deadline_exceeded`. A preflight result whose measured UTF-8 chunk text exceeds the response schema's 65,536-byte maximum is rejected as `422 source_too_large` rather than returning an invalid success response. Both normal chunking and preflight enforce the runtime's hard maximum of 256 chunks; preflight rejects sources exceeding that bound rather than allocating an unbounded span list.

## Bounded ingestion preflight

`POST /api/v1/chunking/preflight` accepts source text, the immutable `index_profile` identity, the complete resolved `profile_bundle` returned by Index, and the exact `chunking_profile` from that bundle. It verifies that name/version/digest agree between identity and bundle, then runs the same deterministic chunking algorithm as normal ingestion. The complete bundle supplies the component versions and representation limits; Chunking does not guess defaults and does not call Index, Tokenization, Embedding, or Graph. The response includes `chunk_count`, `max_chunk_text_bytes`, `estimated_representation_bytes_upper_bound`, `max_request_bytes`, `fits_profile`, `chunking_profile`, and `request_id`. `fits_profile` currently checks source byte size, the runtime chunk-count ceiling, the Index profile's chunk-count limit, maximum chunk-text bytes, and conservative serialized representation/request-size bounds. It does not validate metadata size or lexical term/count bounds: metadata and lexical terms are not inputs to this service, and their canonicalization/tokenization rules belong to the owning downstream components, which must enforce those limits before accepting a representation. The Index bundle pins both `max_units` and `overlap_units`, and preflight rejects either value if it differs from the digest-covered bundle. It does not guarantee provider availability or model-side runtime success. Embedding validates actual provider token limits against `embedding.max_input_tokens`; a provider outage or asynchronous model failure is recorded as an ingestion failure/reconciliation state and never publishes a partial representation. The upper bound is `chunk_count * max_chunk_representation_bytes + max_envelope_bytes` from the Index-owned profile. The current profile digest canonicalization is intentionally limited to the present schema's JSON primitive values. Any change that introduces additional JSON value types or any second-language implementation must add independent RFC 8785 conformance vectors and cross-implementation digest tests before release; the fixed golden vector is a regression check, not a complete conformance suite. A profile is invalid if `max_chunks * max_chunk_representation_bytes + max_envelope_bytes > max_request_bytes`. Every downstream component must enforce the per-chunk serialized representation cap. If the upper bound exceeds the request cap, Memory/Knowledge reject with `422 source_too_large` before canonical commit.

## Acceptance tests

- Same input and policy produce byte-for-byte equivalent structured output across fresh processes.
- Chunk IDs are stable for identical identity/revision/policy and change appropriately when source revision or chunk boundaries change.
- Offsets, line spans, heading paths, overlap, ordering, and maximum size are verified for ordinary text, Markdown headings, Unicode, empty input, and boundary cases.
- Non-canonical profile names/versions and invalid policies return stable client errors.
- Only the canonical `markdown-default@0.1` profile is accepted; unsupported profile/version requests are rejected.
- Failure and readiness behavior is distinguishable from a valid empty-document result.
- Contract tests run without requiring a particular programming language or deployment topology.
