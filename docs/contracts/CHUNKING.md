# Chunking Service Contract (Draft)

Status: proposed contract for architecture review. No implementation or storage technology is prescribed.

## Responsibility

Produce deterministic, versioned chunks from source content for indexing and retrieval. The service owns chunk-boundary semantics and chunker profiles. It does not own canonical source records, corpus revisions, lexical indexes, embeddings, or vector storage; those belong to their respective owners.

## HTTP API

Base path: `/api/v1`

### `POST /chunking/chunks`

Transform one source document into chunks. The operation is deterministic for the same content, source identity/revision, and effective policy.

Request:

```json
{
  "source": {
    "source_id": "knowledge:kn_01J7M6P4V9Q2R8T6W3X5Y0ZABC",
    "revision": "rev-17",
    "revision_sequence": 17,
    "media_type": "text/markdown",
    "content": "# Design\n..."
  },
  "policy": {
    "profile": "markdown-default",
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

The caller may omit `policy` to use the explicitly configured default profile. The response must identify the effective profile and version; defaults must never be implicit in diagnostics.

Response:

```json
{
  "source_id": "knowledge:kn_01J7M6P4V9Q2R8T6W3X5Y0ZABC",
  "source_revision": "rev-17",
  "revision_sequence": 17,
  "chunker": {
    "profile": "markdown-default",
    "version": "0.1"
  },
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
  ]
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

## Errors

Use the shared CE REST error envelope. At minimum distinguish malformed request, unsupported media type, unknown profile/version, invalid policy, content too large, and internal processing failure. Include a stable error code, safe message, retryability, and correlation ID. Client errors are not retryable without changing the request; transient internal failures may be retryable.

## Readiness and diagnostics

Expose `GET /api/v1/chunking/health` and `GET /api/v1/chunking/ready`. Readiness reports whether configured chunking profiles are available. Diagnostics include effective profile/version and duration, but do not log document content by default.

## Acceptance tests

- Same input and policy produce byte-for-byte equivalent structured output across fresh processes.
- Chunk IDs are stable for identical identity/revision/policy and change appropriately when source revision or chunk boundaries change.
- Offsets, line spans, heading paths, overlap, ordering, and maximum size are verified for plain text, Markdown, Unicode, empty input, and boundary cases.
- Unknown profiles and invalid policies return stable client errors.
- Policy upgrades are visible to Index and trigger a defined re-chunk/re-index path without silently mixing versions.
- Failure and readiness behavior is distinguishable from a valid empty-document result.
- Contract tests run without requiring a particular programming language or deployment topology.
