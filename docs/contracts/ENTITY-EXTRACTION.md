# Entity and Identifier Extraction Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Extract exact entities, technical identifiers, paths, names, version strings, symbols, and other query anchors from supplied text. Preserve the original span and normalized form, distinguish exact identifiers from inferred entities, and represent uncertainty. This service supplies features to Gateway query planning; it does not search, authorize, resolve access, or mutate records.

## Endpoints

- POST /api/v1/entity-extraction/extract
- GET /api/v1/entity-extraction/health
- GET /api/v1/entity-extraction/ready

## Request

<!-- schema-example: docs/contracts/schemas/entity-extraction.schema.json#/$defs/request -->
~~~json
{
  "request_id": "correlation-id",
  "text": "Review docs/contracts/INDEX.md and issue #1",
  "profile": {"name": "technical-default", "version": "0.1"}
}
~~~

## Response

<!-- schema-example: docs/contracts/schemas/entity-extraction.schema.json#/$defs/response -->
~~~json
{
  "request_id": "correlation-id",
  "profile": {"name": "technical-default", "version": "0.1"},
  "entities": [
    {"kind": "file_path", "text": "docs/contracts/INDEX.md", "normalized": "docs/contracts/INDEX.md", "start_offset": 7, "end_offset": 30, "confidence": 1.0, "exact": true},
    {"kind": "issue_identifier", "text": "#1", "normalized": "1", "start_offset": 41, "end_offset": 43, "confidence": 1.0, "exact": true}
  ]
}
~~~

Span offsets are zero-based, half-open Unicode code-point offsets into the exact submitted Unicode text. UTF-8 byte offsets are not permitted. `start_offset` is inclusive and `end_offset` is exclusive. Offsets refer to the original `text` field, not a normalized representation.

## Semantics

- Preserve exact surface text and span. Normalization never overwrites the original value.
- Distinguish exact syntactic extraction from inferred/linked entity interpretation. Confidence and uncertainty are explicit; do not fabricate identifiers or silently repair paths/names.
- Preserve punctuation and case where meaningful for paths, symbols, IDs, versions, and technical terms. Normalization rules are versioned by profile.
- The service does not resolve identifiers against repositories, Graph, Memory, Knowledge, or external systems. Resolution/search remains an explicitly orchestrated downstream action.
- Bound input length, entity count, execution time, and provider calls. Propagate request correlation, deadline, and cancellation.
- Avoid logging raw input text by default.

## Machine-checkable schemas

The normative request/response schema is [`schemas/entity-extraction.schema.json`](schemas/entity-extraction.schema.json). Entity spans use zero-based, half-open Unicode code-point offsets and the field names `start_offset` and `end_offset`.

## Errors

Use the common error envelope. Distinguish invalid input/profile, unsupported text size, deadline exceeded, provider unavailable, and internal failure. No entities found is a valid response.

## Acceptance tests

1. Exact file paths, URLs, issue/PR IDs, version strings, symbols, and technical names preserve source spans and surface form.
2. Unicode code-point offsets align exactly with Chunking and Tokenization for emoji, combining characters, and non-Latin scripts.
3. Exact extraction is distinguishable from inferred entities.
4. No-match differs from service failure.
5. No lookup, access-control, or mutation side effects occur.
6. Limits/deadlines/cancellation and privacy-safe logging are enforced.
7. Profiles and normalization versions are explicit.

## Approval gate

Review with Gateway query planning, Intent Classification, Tokenization, and retrieval workflow acceptance tests before implementation.
