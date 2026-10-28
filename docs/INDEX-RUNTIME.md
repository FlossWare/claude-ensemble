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

## ChromaDB vector-store implementation

Index uses persistent local ChromaDB for vector storage and similarity search. SQLite remains authoritative for lexical/BM25 retrieval, source manifests and revisions, idempotency, generation lifecycle, scope, and tombstones. ChromaDB is an internal implementation detail; the REST endpoint and schema remain unchanged. The SQLite vector backend remains available explicitly with `CE_INDEX_VECTOR_BACKEND=sqlite`; the default backend is `chromadb`. `CE_INDEX_CHROMA_PATH` selects the persistent Chroma directory and otherwise defaults to a sibling directory next to the Index SQLite database.

Collections are isolated by profile digest, generation, and metric. Vector records use deterministic IDs derived from generation/source/revision sequence/chunk identity. If a collection is empty when first used, Index seeds it from existing SQLite vector representations so a switch from the previous SQLite backend does not silently lose retrieval results. Queries constrain scope in Chroma and validate every returned candidate against current SQLite representation and tombstone state before returning it. The Index service owns one persistent Chroma client per process and reuses it across collections.

Vector mutations are synchronous. Index updates SQLite canonical state and synchronizes the affected source's vectors before returning success. If ChromaDB cannot be initialized or a vector write/query/delete fails, Index returns an error rather than reporting success or silently falling back to SQLite. There is no durable outbox, replay worker, reconciliation framework, or distributed transaction simulation. Restart persistence is provided by ChromaDB's on-disk store; ordinary idempotent retries use the existing Index operation binding and deterministic vector IDs.

The adapter maps cosine, inner-product, and Euclidean metrics explicitly. Retrieval preserves the existing REST contract and mandatory second-stage reranking. Acceptance requires the complete test suite plus real persistent-Chroma coverage for writes, updates, deletes, scope isolation, persistence across process/client restart, stale-revision/tombstone filtering, and retrieval through the mandatory reranker. SonarCloud is not a merge gate for this work.
