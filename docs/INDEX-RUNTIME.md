# Index Runtime (initial implementation slice)

The Index runtime is a logical service exposed through the shared CE REST server. It owns derived searchable representations and durable source tombstones; it does not own canonical Memory or Knowledge content and does not call other logical services directly.

## Configuration

No built-in Index profile is selected. Provision an immutable bundle and point CE at it:

- `CE_INDEX_PROFILE_BUNDLE_PATH`: required path to the JSON profile bundle.
- `CE_INDEX_DB_PATH`: optional SQLite database path. Default: `~/.FlossWare/index/index.sqlite3`.

The bundle must conform to [the Index profile schema](contracts/schemas/index-profile.schema.json). The SHA-256 digest covers the canonical JSON bundle with `digest` and lifecycle `status` omitted. The current bounded runtime supports one provisioned profile version per database; changing profiles requires the separately reviewed rebuild/registry workflow. Do not put model weights or the SQLite database in Git. Embedding model artifacts remain under the configured model directory, conventionally `~/.FlossWare/models`.

To calculate the bundle digest after editing the bundle's component fields, run this from the repository root:

```bash
python - <<'PY'
import hashlib
import json
from pathlib import Path

path = Path("index-profile.json")
bundle = json.loads(path.read_text(encoding="utf-8"))
bundle.pop("digest", None)
bundle.pop("status", None)
canonical = json.dumps(
    bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
).encode("utf-8")
print(hashlib.sha256(canonical).hexdigest())
PY
```

Place that digest in the bundle's `digest` field. Keep the `status` field present; it is excluded from the digest so lifecycle state cannot change the immutable bundle identity.

## Implemented REST surface

The shared server currently exposes Index health/readiness, pinned profile lookup, active-generation/status lookup, source manifest/status, upsert/operation status, source-wide tombstones, lexical lookup, vector neighbors, and the first generation/fence/checkpoint operations. The initial configured bundle bootstraps the first active generation. The cutover endpoint deliberately fails closed with `503 not_ready` until owner-journal replay, reconciliation evidence, and cutover recovery are implemented and tested.

All mutating POST calls require `Idempotency-Key`. Lexical and vector retrieval must supply the active generation and exact profile identity. Lookup results are bounded to 100 candidates and are filtered against the durable tombstone high-water mark.

## Lifecycle implementation and remaining acceptance work

The runtime retains terminal idempotency bindings for the common 30-day window and returns `409 idempotency_key_expired` for an expired key instead of replaying it as a new mutation. Pending, accepted, and reconciliation-required operations are not expired. Expiry markers remain durable, including for generation creation and lifecycle POSTs. Building generations record structured per-source failures, report their counts/details, and remain ineligible for cutover when failures exist. Active-generation upserts and source tombstones are dual-applied to compatible building generations; an Index-owned journal records each applied change and exposes its position in generation status. Replaying an already dual-applied source revision is idempotent only when its canonical payload matches. Equal active source revisions follow the same rule; conflicting payloads are rejected. New mutations invalidate a previously eligible generation and return it to the building state. Expired idempotency keys return `idempotency_key_expired` even when the attempted retry also changes its payload. HTTP deadline behavior is covered by a real-dispatcher test. Retrieval fan-out forwards the absolute caller deadline to each nested REST call and uses the remaining time as the per-call timeout. The reserved internal worker pool requires a process-local token, so the public marker header alone cannot claim internal capacity. Real-HTTP integration tests exercise both lexical retrieval through Tokenization and Index and vector retrieval through Embedding and Index; the vector wiring test uses a deterministic fake model while the pinned offline CPU job separately verifies actual model inference.

Cutover still deliberately fails closed. Index-side dual-apply journaling is not a substitute for Memory and Knowledge's own durable change journals, replay acknowledgments, stable canonical manifests, and source-write fencing. Those owner services must be implemented and integrated before Index can prove that a target generation is complete or safely switch the active pointer. Recovery after a bad cutover is forward rebuild only; v1 rollback remains unsupported. The generalized multi-version profile registry in [PR #11](https://github.com/FlossWare/claude-ensemble/pull/11) remains deferred until a real consumer requires it.

Keep the PR in draft until the complete test suite passes and remaining contract gaps are either implemented or explicitly assigned to the owner-service integration slice. Static contract validation alone is not runtime acceptance evidence.

## Mandatory second-stage vector reranking

Every non-empty `POST /api/v1/vector-retrieval/search` result passes through the existing reranking endpoint; callers do not opt in. The request uses query text from `query.text`. Callers that supply a precomputed query vector instead must provide `rerank_query` text explicitly. Reranking uses the pinned `default-reranker@0.1` profile and calls `POST /api/v1/reranking/rerank` over internal REST, using `CE_RERANKING_BASE_URL` (default `http://127.0.0.1:8080`).

The reranker evaluates at most the top 20 vector candidates. If a request asks for more than 20 results and Index returned more than 20 candidates, this stage returns the reranked top 20 and sets `truncated=true`; it does not silently hide that cap. The returned candidate order follows reranker rank. Each candidate retains its vector distance and original `retrieval_rank` for audit/diagnostics; downstream consumers that need the final ranking must use `rerank_rank` (or the returned order), not treat the original vector rank as the final rank. Responses include `rerank_score`, `rerank_rank`, and `reranking_profile`. If the reranking dependency is not configured or fails, vector retrieval fails rather than silently returning an un-reranked list. Empty candidate lists do not invoke the reranker. This stage does not change canonical Memory/Knowledge data or Index persistence.

## Proposed ChromaDB vector-store adapter (design only)

This section records the design gate for issue [#40](https://github.com/FlossWare/claude-ensemble/issues/40). It is not a claim that ChromaDB is implemented or enabled.

### Ownership and boundary

- Keep `POST /api/v1/index/vector-neighbors` and its request/response schema unchanged. The REST dispatcher and `IndexService` remain the owners of validation, generation/profile identity, scope policy, source revision ordering, tombstones, and operation status.
- Introduce a narrow internal vector-store interface for upsert, bounded nearest-neighbor query, delete-by-source/generation, and reconciliation. ChromaDB is one adapter; the current SQLite-backed vector search remains an explicit backend for deterministic tests and a controlled fallback.
- Keep SQLite authoritative for lexical/BM25 data, source manifests, idempotency bindings, generation lifecycle, tombstone high-water marks, owner checkpoints, and durable write intents. ChromaDB must not become a second authority for source lifecycle.
- Do not add a separately deployed Chroma service or change the public Index API for this integration.

### Collection and metadata isolation

Use a deterministic collection identity derived from the validated Index profile identity and generation identity. Do not place multiple generations in one unpartitioned collection. Persist the stable candidate identity in Chroma metadata: source ID, source revision, revision sequence, chunk ID, chunker identity, scope fields, embedding model/version/dimensions, and the profile/generation identity required to reject incompatible candidates. Store document text only as needed for the existing response contract; SQLite remains authoritative for candidate metadata and lifecycle state.

Every query must constrain generation/profile and scope in the Chroma query itself, then validate returned IDs and metadata against SQLite. Reject malformed or incompatible metadata. Before returning candidates, discard any candidate whose revision is not the current indexed source revision or whose source is at or below its tombstone high-water mark. The existing deterministic tie-break rule must be applied after candidate validation.

### Metric and result semantics

Map the Index contract's supported metrics explicitly to Chroma distance spaces and test the conversion from Chroma's returned distance to the existing Index response semantics. Do not assume that similarly named distances have identical direction or scale. Keep the current bounded result limit and stable tie-breaking. Preserve candidate identity, original vector distance/similarity fields, retrieval rank, scope, source revision, and provenance so the downstream mandatory reranker requires no special Chroma logic.

### Durable writes and recovery

SQLite and ChromaDB cannot participate in one shared transaction. Therefore, do not mark an operation complete merely because one side committed.

1. In one SQLite transaction, validate idempotency/revision/tombstone constraints and persist the canonical Index operation state plus a durable vector-store intent.
2. Apply the intent to ChromaDB using a deterministic ID derived from generation, source revision, and chunk identity, making retries idempotent.
3. Acknowledge the intent in SQLite only after the Chroma operation succeeds and the resulting collection/record state is validated.
4. On startup/readiness, replay pending intents in deterministic order. Health may be live while readiness remains false or degraded if required replay has not converged.
5. For deletes and generation cleanup, persist the intent before touching ChromaDB. SQLite tombstones remain authoritative even if physical deletion is delayed.
6. If ChromaDB is unavailable, leave the operation pending/retryable and return the contract-defined pending/error state. Never claim vector indexing is complete when the durable intent has not been acknowledged.
7. Provide an explicit reconciliation path that compares expected SQLite-owned vector identities with collection contents, records discrepancies, and repairs only when the owning generation is safe to modify.

The first implementation must document crash points and prove retry behavior for a crash after SQLite intent commit, after Chroma mutation, and before SQLite acknowledgement. Generation cutover remains fail-closed; this work does not relax owner-journal, fencing, or reconciliation requirements.

### Rollout and acceptance gate

Keep backend selection explicit through configuration; do not silently switch existing deployments from SQLite vectors to ChromaDB. Start with local persistent Chroma storage and a temporary directory in tests. Do not introduce network access, model downloads, or implicit fallback on startup. The adapter is eligible for default consideration only after tests prove contract parity, scope/generation isolation, revision/tombstone filtering, metric parity, bounded deterministic results, restart recovery, and unchanged mandatory reranking behavior.