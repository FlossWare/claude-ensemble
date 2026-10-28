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

The runtime retains terminal idempotency bindings for the common 30-day window and returns `409 idempotency_key_expired` for an expired key instead of replaying it as a new mutation. Pending, accepted, and reconciliation-required operations are not expired. Expiry markers remain durable, including for generation creation and lifecycle POSTs. Building generations record structured per-source failures, report their counts/details, and remain ineligible for cutover when failures exist. Active-generation upserts and source tombstones are dual-applied to compatible building generations; an Index-owned journal records each applied change and exposes its position in generation status. Replaying an already dual-applied source revision is idempotent only when its canonical payload matches. New active changes invalidate a previously eligible generation and return it to the building state. HTTP deadline behavior is covered by a real-dispatcher test.

Cutover still deliberately fails closed. Index-side dual-apply journaling is not a substitute for Memory and Knowledge's own durable change journals, replay acknowledgments, stable canonical manifests, and source-write fencing. Those owner services must be implemented and integrated before Index can prove that a target generation is complete or safely switch the active pointer. Recovery after a bad cutover is forward rebuild only; v1 rollback remains unsupported. The generalized multi-version profile registry in [PR #11](https://github.com/FlossWare/claude-ensemble/pull/11) remains deferred until a real consumer requires it.

Keep the PR in draft until the complete test suite passes and remaining contract gaps are either implemented or explicitly assigned to the owner-service integration slice. Static contract validation alone is not runtime acceptance evidence.
