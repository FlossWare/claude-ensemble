# Tokenization Service Contract (Draft)

Status: proposed contract for architecture review. No implementation or tokenizer library is prescribed.

## Responsibility

Provide consistent, versioned lexical tokenization and normalization for index-time and query-time use. Preserve technical identifiers and source spans so lexical retrieval can explain exact matches. This service does not own corpus/index state or rank retrieval results.

Model-specific subword tokenization and context-window token counting are deliberately separate concerns. They may later use separate adapters or services because their token IDs, vocabularies, and counting semantics are model-specific; they must not be conflated with lexical terms.

## HTTP API

Base path: `/api/v1`

### `POST /tokenization/lexical`

Tokenize and normalize one text input using an explicit profile. Requests carry the pinned Index profile identity and component tokenizer profile/version. Tokenization resolves that immutable bundle through Index's versioned profile REST endpoint, verifies the digest and component identity, and never silently falls back to a local or current profile.

### `POST /tokenization/lexical/batch`

Apply the same profile and options to 1–64 inputs, with a maximum 512 KiB encoded request body. Each input has a unique `input_id` and `text`; each result carries that `input_id` and either tokens or a stable per-item error. Results must not be correlated by array order alone. Batch and single-item calls have equivalent per-item semantics.

Request:

<!-- schema-example: docs/contracts/schemas/tokenization.schema.json#/$defs/request -->
```json
{
  "index_profile": {"name": "default", "version": "0.1", "digest": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
  "text": "Fix FooBarException in src/FooBar.java",
  "profile": "technical-default",
  "profile_version": "0.1",
  "options": {
    "preserve_identifiers": true,
    "include_offsets": true,
    "include_normalized_terms": true
  }
}
```

For indexing workflows, callers supply the immutable Index-owned bundle identity `{name, version, digest}` and exact Tokenization component profile/version from that bundle. A default is not selected independently by Tokenization. The response echoes the effective profile/version and bundle digest.

Response:

<!-- schema-example: docs/contracts/schemas/tokenization.schema.json#/$defs/response -->
```json
{
  "profile": "technical-default",
  "version": "0.1",
  "normalization_version": "0.1",
  "index_profile": {"name": "default", "version": "0.1", "digest": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
  "tokens": [
    {
      "term": "fix",
      "surface": "Fix",
      "start_offset": 0,
      "end_offset": 3,
      "kind": "word"
    },
    {
      "term": "foobarException",
      "surface": "FooBarException",
      "start_offset": 4,
      "end_offset": 19,
      "kind": "identifier"
    }
  ]
}
```

Offsets are zero-based, half-open Unicode code-point offsets into the exact submitted text. The sample is illustrative, not a mandate to lowercase or split identifiers in this exact way; profile behavior is the contract.

## Semantics

- Index-time and query-time callers use compatible profile/version combinations. The service exposes identity/version so incompatible indexes can be detected rather than silently queried.
- Preserve original surface text and offsets when requested. Normalized terms are additional representations, not replacements for source evidence.
- Profiles define Unicode handling, case behavior, punctuation, path handling, code identifiers, error strings, and language-specific behavior explicitly.
- Preserve exact identifier/name/error/path/code-symbol forms when configured. Optional subterms may be emitted alongside the exact form; do not replace the exact form with lossy splitting.
- Token order is deterministic. Repeated identical requests with the same profile/version/options return equivalent results.
- Empty input returns an empty token list, not an error.
- This endpoint is lexical tokenization, not an embedding tokenizer and not a model context-length oracle.
- Profile/version changes that affect terms must be visible to Index so it can reindex or reject incompatible query behavior.
- No request content is logged by default.

## Machine-checkable schemas

The normative request/response schemas for single and batch lexical tokenization are in [`schemas/tokenization.schema.json`](schemas/tokenization.schema.json). The batch request is limited to 1–64 inputs and 512 KiB encoded body; each result is keyed by `input_id`, never array position.

## Errors

Use the shared CE REST error envelope. At minimum distinguish malformed request, unknown profile/version, unsupported language/profile, text too large, and internal processing failure. Include a stable error code, safe message, retryability, and correlation ID.

## Readiness and diagnostics

Expose `GET /api/v1/tokenization/health` and `GET /api/v1/tokenization/ready`. Readiness reports whether configured profiles are available. Diagnostics include profile/version and duration, but not submitted text or emitted terms by default.

## Acceptance tests

- Identical input/profile/version/options yields deterministic output across fresh processes.
- Unicode offsets and surface spans are correct.
- Tests cover case, punctuation, accents, Unicode normalization, paths, filenames, code symbols, mixedCase identifiers, acronyms, error messages, numbers, empty input, and large inputs.
- Exact technical identifiers remain searchable even when optional normalized subterms are emitted.
- Index-time/query-time profile compatibility is explicit and mismatches are observable.
- Unknown profiles and invalid requests return stable client errors.
- Tests prove this service does not silently pretend to provide model-specific token IDs or context-window counts.
- Contract tests run without requiring a particular programming language or deployment topology.
