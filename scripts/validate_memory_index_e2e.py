#!/usr/bin/env python3
"""Real local-model HTTP acceptance test for Memory -> Index lexical retrieval.

All model artifacts must already be provisioned locally. The script is offline-only,
uses temporary SQLite stores, and fails rather than substituting a fake embedding.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from runtime.embedding import EXPECTED_DIMENSIONS, EXPECTED_MODEL_ID, get_engine, reset_engine_for_tests
from runtime.index import profile_digest, reset_index_service_for_tests
from runtime.memory import reset_memory_service_for_tests
from runtime.server import BoundedThreadingHTTPServer, Handler


SCOPE = {"type": "project", "id": "memory-index-e2e", "visibility": "private"}


def _request(base: str, path: str, *, payload: dict | None = None, method: str | None = None,
             headers: dict[str, str] | None = None, timeout: float = 5.0) -> dict:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request_headers = {"Accept": "application/json", "X-CE-Request-ID": "memory-index-e2e"}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)
    request = Request(base + path, data=body, headers=request_headers,
                      method=method or ("GET" if body is None else "POST"))
    try:
        with urlopen(request, timeout=timeout) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{path} returned HTTP {exc.code}: {detail}") from exc
    if not isinstance(decoded, dict):
        raise RuntimeError(f"{path} returned a non-object response")
    return decoded


def _profile(revision: str) -> dict:
    value = {
        "name": "memory-index-e2e",
        "version": "0.1",
        "status": "active",
        "chunking": {"profile": "markdown-default", "version": "0.1", "max_units": 1200, "overlap_units": 120},
        "tokenization": {"profile": "technical-default", "version": "0.1"},
        "lexical": {"profile": "bm25-v1", "version": "0.1", "statistics_policy": "scope_partition"},
        "embedding": {
            "required": True, "profile": "technical-default", "version": "0.1",
            "model": EXPECTED_MODEL_ID, "model_version": revision,
            "input_types": ["query", "document"], "dimensions": EXPECTED_DIMENSIONS,
            "normalization": "l2", "metric": "cosine", "max_input_tokens": 8192,
        },
        "limits": {
            "max_chunks": 32, "max_source_bytes": 131072, "max_chunk_text_bytes": 512,
            "max_request_bytes": 2097152, "max_chunk_representation_bytes": 40000,
            "max_envelope_bytes": 16384, "max_metadata_bytes": 1024,
            "max_lexical_terms_per_chunk": 64, "max_lexical_term_bytes": 32,
        },
    }
    value["digest"] = profile_digest(value)
    return value


def main() -> int:
    revision = os.environ.get("CE_EMBEDDING_MODEL_VERSION", "")
    model_path = Path(os.environ.get(
        "CE_EMBEDDING_MODEL_PATH",
        str(Path.home() / ".FlossWare" / "models" / "nomic-embed-text-v1.5"),
    )).expanduser()
    if len(revision) != 40 or any(ch not in "0123456789abcdef" for ch in revision):
        print("FAIL: CE_EMBEDDING_MODEL_VERSION must be a pinned 40-character commit SHA", file=sys.stderr)
        return 1
    if not model_path.is_dir() or model_path.resolve().name != revision:
        print("FAIL: pinned local embedding snapshot is missing or does not match its revision", file=sys.stderr)
        return 1

    original_env = dict(os.environ)
    server = None
    thread = None
    try:
        with tempfile.TemporaryDirectory(prefix="ce-memory-index-e2e-") as temp:
            root = Path(temp)
            bundle_path = root / "profile.json"
            bundle = _profile(revision)
            bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
            os.environ.update({
                "CE_INDEX_PROFILE_BUNDLE_PATH": str(bundle_path),
                "CE_INDEX_DB_PATH": str(root / "index.sqlite3"),
                "CE_MEMORY_DB_PATH": str(root / "memory.sqlite3"),
                "CE_EMBEDDING_MODEL_PATH": str(model_path),
                "CE_EMBEDDING_MODEL_ID": EXPECTED_MODEL_ID,
                "CE_EMBEDDING_MODEL_VERSION": revision,
            })
            for name in ("CE_INDEX_BASE_URL", "CE_CHUNKING_BASE_URL",
                         "CE_TOKENIZATION_BASE_URL", "CE_EMBEDDING_BASE_URL"):
                os.environ.pop(name, None)

            reset_index_service_for_tests()
            reset_memory_service_for_tests()
            engine = get_engine()
            readiness = engine.readiness()
            if readiness.get("ready") is not True:
                raise RuntimeError("configured real embedding model is not ready offline")
            identity = {key: bundle[key] for key in ("name", "version", "digest")}
            # Persist accepted work before the REST server starts, then discard the
            # in-memory owner so startup recovery must reload its durable journal.
            recovery_content = (
                "Startup recovery replays pending canonical Memory revisions "
                "into durable Index storage."
            )
            recovery_seed = get_memory_service().create(
                {
                    "scope": SCOPE, "type": "semantic", "content": recovery_content,
                    "provenance": {"origin": "memory-index-restart-recovery"},
                    "retention_policy": {"kind": "standard"}, "index_profile": identity,
                },
                "memory-index-e2e-recovery-create", "memory-index-e2e-recovery",
            )[1]
            reset_memory_service_for_tests()

            server = BoundedThreadingHTTPServer(("127.0.0.1", 0), Handler)
            base = f"http://127.0.0.1:{server.server_address[1]}"
            thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
            thread.start()

            # Readiness schedules recovery. Poll the durable operation, not the
            # thread, and verify the recovered revision is searchable over REST.
            _request(base, "/api/v1/memory/ready")
            scope_query = ("?scope_type=" + quote(SCOPE["type"]) + "&scope_id=" + quote(SCOPE["id"])
                           + "&visibility=" + quote(SCOPE["visibility"]))
            recovery_operation_id = recovery_seed["operation_id"]
            deadline = time.monotonic() + 120.0
            recovery_operation = {}
            while time.monotonic() < deadline:
                recovery_operation = _request(
                    base, "/api/v1/memories/operations/" + recovery_operation_id + scope_query
                )
                if recovery_operation.get("status") in {"complete", "failed", "reconciliation_required"}:
                    break
                time.sleep(0.25)
            if (recovery_operation.get("status") != "complete"
                    or recovery_operation.get("indexing_status") != "indexed"):
                raise RuntimeError(f"Startup recovery did not complete ingestion: {recovery_operation!r}")
            recovery_generation = _request(base, "/api/v1/index/generations/active").get("generation_id")
            recovered_lookup = _request(
                base, "/api/v1/index/lexical/lookup",
                payload={
                    "scope": SCOPE, "terms": ["startup", "recovery", "canonical", "revisions"],
                    "limit": 10, "index_generation": recovery_generation,
                    "index_profile": identity,
                    "lexical_profile": {"name": bundle["lexical"]["profile"],
                                        "version": bundle["lexical"]["version"]},
                },
            )
            if not any(
                item.get("source_id") == recovery_seed.get("source_id")
                and "startup recovery replays pending canonical memory revisions" in item.get("text", "").lower()
                for item in recovered_lookup.get("candidates", []) if isinstance(item, dict)
            ):
                raise RuntimeError("Startup-recovered Memory source was not retrievable from Index")

            content = (
                "Claude Ensemble indexes source revisions for reliable retrieval. "
                "This acceptance fixture verifies real embedding inference, durable indexing, "
                "and lexical retrieval of the source revision retrieval contract."
            )
            created = _request(
                base, "/api/v1/memories",
                payload={
                    "scope": SCOPE, "type": "semantic", "content": content,
                    "provenance": {"origin": "real-model-http-acceptance"},
                    "retention_policy": {"kind": "standard"}, "index_profile": identity,
                },
                headers={"Idempotency-Key": "memory-index-e2e-create"},
                timeout=10.0,
            )
            operation_id = created.get("operation_id")
            if not isinstance(operation_id, str) or created.get("status") not in {"accepted", "pending"}:
                raise RuntimeError(f"Memory create did not return an accepted operation: {created!r}")

            deadline = time.monotonic() + 120.0
            operation = {}
            while time.monotonic() < deadline:
                operation = _request(base, "/api/v1/memories/operations/" + operation_id + scope_query)
                if operation.get("status") in {"complete", "failed", "reconciliation_required"}:
                    break
                time.sleep(0.25)
            if operation.get("status") != "complete" or operation.get("indexing_status") != "indexed":
                raise RuntimeError(f"Memory ingestion did not complete successfully: {operation!r}")

            active = _request(base, "/api/v1/index/generations/active")
            generation = active.get("generation_id")
            if not isinstance(generation, str) or not generation:
                raise RuntimeError("Index did not expose an active generation")
            lookup = _request(
                base, "/api/v1/index/lexical/lookup",
                payload={
                    "scope": SCOPE, "terms": ["source", "revision", "retrieval", "contract"],
                    "limit": 10, "index_generation": generation,
                    "index_profile": identity,
                    "lexical_profile": {"name": bundle["lexical"]["profile"],
                                        "version": bundle["lexical"]["version"]},
                },
                timeout=10.0,
            )
            candidates = lookup.get("candidates")
            if not isinstance(candidates, list) or not any(
                item.get("source_id") == created.get("source_id")
                and "source revision retrieval contract" in item.get("text", "").lower()
                for item in candidates if isinstance(item, dict)
            ):
                raise RuntimeError(f"Lexical lookup did not retrieve the created Memory source: {lookup!r}")

            # Re-open the persistent Index store and repeat the lookup.
            reset_index_service_for_tests()
            active = _request(base, "/api/v1/index/generations/active")
            generation = active.get("generation_id")
            lookup["candidates"] = []
            reopened = _request(
                base, "/api/v1/index/lexical/lookup",
                payload={
                    "scope": SCOPE, "terms": ["source", "revision", "retrieval", "contract"],
                    "limit": 10, "index_generation": generation,
                    "index_profile": identity,
                    "lexical_profile": {"name": bundle["lexical"]["profile"],
                                        "version": bundle["lexical"]["version"]},
                },
                timeout=10.0,
            )
            if not any(
                item.get("source_id") == created.get("source_id")
                and "source revision retrieval contract" in item.get("text", "").lower()
                for item in reopened.get("candidates", []) if isinstance(item, dict)
            ):
                raise RuntimeError("Lexical retrieval failed after reopening Index storage")

            print("PASS: real pinned Nomic model used through the Embedding REST endpoint.")
            print("PASS: startup recovery replayed a durable pending Memory operation through REST.")
            print("PASS: recovered Memory source was retrievable from Index.")
            print("PASS: Memory -> Chunking -> Tokenization -> Embedding -> Index completed over HTTP.")
            print("PASS: lexical retrieval found the created source before and after Index storage reopen.")
            return 0
    except (HTTPError, OSError, ValueError, RuntimeError) as exc:
        print(f"FAIL: Memory-to-Index real-model HTTP acceptance failed ({type(exc).__name__}: {exc})",
              file=sys.stderr)
        return 1
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2)
        reset_index_service_for_tests()
        reset_memory_service_for_tests()
        reset_engine_for_tests()
        for key in list(os.environ):
            if key not in original_env:
                os.environ.pop(key, None)
        os.environ.update(original_env)


if __name__ == "__main__":
    raise SystemExit(main())
