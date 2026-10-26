# Chunking Service Contract (Draft)

Status: contract baseline approved by merged PR #8; the initial runtime implementation is under review in PR #9. The contract remains normative, and passing static validation alone does not establish runtime conformance.

## Responsibility

Produce deterministic, versioned chunks from source content for indexing and retrieval. The service owns chunk-boundary semantics and chunker profiles. It does not own canonical source records, corpus revisions, lexical indexes, embeddings, or vector storage; those belong to their respective owners.

## HTTP API

Base path: `/api/v1`

### `POST /chunking/chunks`

Transform one source document into chunks. The operation is deterministic for the same content, source identity/revision, and effective policy. Every request carries the immutable Index-owned bundle identity `{name, version, digest}` and the exact Chunking component profile/version from that bundle; Chunking never resolves a local default when an index profile is supplied.

Request:

<!-- schema-example: docs/contracts/schemas/chunking.schema.json#/$defs/chunkRequest -->
```json
{
  "index_profile": {"name": "default", "version": "0.1", "digest": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
  "source": {
    "source_id": "knowledge:kn_01J7M6P4V9Q2R8T6W3X5Y0ZABC",
    "revision": "rev-17",
    "revision_sequence": 17,
    "media_type": "text/markdown",
    "content": "# Design\n..."
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

The caller may omit `policy` to use the explicitly configured default profile. The initial runtime default is `markdown-default@0.1` with `max_units=1200`, `overlap_units=120`, and `unit=unicode_code_points`. The response must identify the effective profile and version; defaults must never be implicit in diagnostics. An Index-pinned component profile should normally be supplied explicitly.

Response:

<!-- schema-example: docs/contracts/schemas/chunking.schema.json#/$defs/chunkResponse -->
```json
{
  "index_profile": {"name": "default", "version": "0.1", "digest": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
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

Offsets are zero-based, half-open Unicode code-point offsets into the exact submitted content. Line numbers are one-based and inclusive. If a media type or source format cannot provide a reliable heading path or line mapping, return an empty/omitted optional value rather than fabricated provenance.

## Semantics

- Chunk ordering is deterministic and `ordinal` is contiguous from zero.
- Chunk identity is stable for identical source identity, source revision, effective policy/version, and chunk content/boundaries. It must not depend on process-local state or random IDs.
- Include effective policy identity/version in responses and diagnostics.
- Chunk text must map to the source offsets. Any normalization that changes text must be explicit and must preserve a source mapping.
- Overlap must be deterministic and bounded by policy. The response must not silently exceed the requested maximum unit size except where a documented indivisible unit requires it.
- Heading/source-line provenance is preserved when available.
- A policy/version change must be observable so the Index service can schedule re-chunking and re-indexing. Chunking does not itself mutate the canonical index.
- Repeated identical requests are safe and have no persistent side effects.
- The service must define size limits and reject invalid policies rather than silently substituting values.

## Machine-checkable schemas

The normative chunk and preflight request/response schemas are in [`schemas/chunking.schema.json`](schemas/chunking.schema.json). The preflight schema includes the profile identity and conservative representation-size bound used before canonical commit.

## Errors

Unsupported HTTP methods return `405 method_not_allowed` using the shared CE REST error envelope and request-ID header. Use the shared CE REST error envelope. At minimum distinguish malformed request, unsupported media type, unknown profile/version, invalid policy, content too large, and internal processing failure. Include a stable error code, safe message, retryability, and correlation ID. Client errors are not retryable without changing the request; transient internal failures may be retryable.

## Readiness and diagnostics

Expose `GET /api/v1/chunking/health` and `GET /api/v1/chunking/ready`. Readiness reports whether configured chunking profiles are available. Diagnostics include effective profile/version and duration, but do not log document content by default.

The initial runtime configures `plain-text-default@0.1` and `markdown-default@0.1`; other profile names or versions are rejected as `unsupported_profile` until explicitly configured. If `policy` is omitted, the runtime uses the explicit `markdown-default@0.1` policy of 1200 Unicode code points per chunk and 120 code points of overlap. The plain-text profile does not infer Markdown heading provenance. The Markdown profile recognizes ATX headings only: Setext headings and headings inside fenced code blocks are not interpreted as structural headings in this initial implementation. `options.include_text=false` omits each chunk's `text` field; offsets and identifiers remain available.

The normal chunks endpoint has a 300,000-byte HTTP request-body cap and independently enforces the 262,144-byte UTF-8 source-content cap. Preflight has a 2 MiB request-body cap because the resolved profile bundle accompanies the source. Callers must not treat the larger preflight envelope allowance as permission to submit source content larger than 262,144 UTF-8 bytes. Both endpoints enforce a 30-second absolute request budget by default; a valid `X-CE-Deadline` may shorten that budget. A body-receipt inactivity timeout returns `408 request_timeout`, while expiry of the absolute request deadline returns `504 deadline_exceeded`. A preflight result whose measured UTF-8 chunk text exceeds the response schema's 65,536-byte maximum is rejected as `422 source_too_large` rather than returning an invalid success response. Both normal chunking and preflight enforce the runtime's hard maximum of 256 chunks; preflight rejects sources exceeding that bound rather than allocating an unbounded span list.

## Bounded ingestion preflight

`POST /api/v1/chunking/preflight` accepts source text, the immutable `index_profile` identity, the complete resolved `profile_bundle` returned by Index, and the exact `chunking_profile` from that bundle. It verifies that name/version/digest agree between identity and bundle, then runs the same deterministic chunking algorithm as normal ingestion. The complete bundle supplies the component versions and representation limits; Chunking does not guess defaults and does not call Index, Tokenization, Embedding, or Graph. The response includes `chunk_count`, `max_chunk_text_bytes`, `estimated_representation_bytes_upper_bound`, `max_request_bytes`, `fits_profile`, `chunking_profile`, and `request_id`. `fits_profile` currently checks source byte size, the runtime chunk-count ceiling, the Index profile's chunk-count limit, maximum chunk-text bytes, and conservative serialized representation/request-size bounds. It does not validate metadata size or lexical term/count bounds: metadata and lexical terms are not inputs to this service, and their canonicalization/tokenization rules belong to the owning downstream components, which must enforce those limits before accepting a representation. The `chunking` section of the current Index bundle schema does not pin `overlap_units`, so preflight validates the requested overlap as a legal policy value but cannot compare it to an Index-pinned overlap value. It does not guarantee provider availability or model-side runtime success. Embedding validates actual provider token limits against `embedding.max_input_tokens`; a provider outage or asynchronous model failure is recorded as an ingestion failure/reconciliation state and never publishes a partial representation. The upper bound is `chunk_count * max_chunk_representation_bytes + max_envelope_bytes` from the Index-owned profile. A profile is invalid if `max_chunks * max_chunk_representation_bytes + max_envelope_bytes > max_request_bytes`. Every downstream component must enforce the per-chunk serialized representation cap. If the upper bound exceeds the request cap, Memory/Knowledge reject with `422 source_too_large` before canonical commit.

## Acceptance tests

- Same input and policy produce byte-for-byte equivalent structured output across fresh processes.
- Chunk IDs are stable for identical identity/revision/policy and change appropriately when source revision or chunk boundaries change.
- Offsets, line spans, heading paths, overlap, ordering, and maximum size are verified for plain text, Markdown, Unicode, empty input, and boundary cases.
- Unknown profiles and invalid policies return stable client errors.
- Policy upgrades are visible to Index and trigger a defined re-chunk/re-index path without silently mixing versions.
- Failure and readiness behavior is distinguishable from a valid empty-document result.
- Contract tests run without requiring a particular programming language or deployment topology.
