import base64

from runtime.gateway import GatewayService


def _candidate(source_id="knowledge:src-1", revision="rev-1", sequence=1, text="CE-42 is a useful source chunk"):
    return {
        "source_id": source_id,
        "source_revision": revision,
        "revision_sequence": sequence,
        "chunk_id": "chunk-1",
        "chunker": {"profile": "markdown-default", "version": "0.1"},
        "retrieval_rank": 1,
        "score_semantics": "bm25-v1",
        "text": text,
        "matched_exact_identifiers": [],
        "provenance": {"origin": "fixture"},
        "score": 1.2,
    }


def test_gateway_rag_request_runs_rest_plan_retrieval_freshness_and_ranking(monkeypatch):
    monkeypatch.setenv("CE_GATEWAY_WRITE_PROFILE_NAME", "default")
    index_profile = {"name": "default", "version": "0.1", "digest": "a" * 64}
    bundle = {
        **index_profile,
        "lexical": {"profile": "technical-default", "version": "0.1"},
        "embedding": {"profile": "default-embedding", "version": "0.1"},
    }
    candidate = _candidate()
    calls = []

    def transport(method, path, payload, request_id, headers, timeout):
        calls.append((method, path, payload))
        if method == "GET" and path == "/api/v1/index/generations/active":
            return 200, {"generation_id": "gen-1", "index_profile": index_profile}
        if method == "GET" and path == "/api/v1/index/profiles/default/versions/0.1":
            return 200, {"name": "default", "version": "0.1", "digest": "a" * 64, "bundle": bundle}
        if path == "/api/v1/intent-classification/classify":
            return 200, {"results": [{"intent": "knowledge_lookup"}]}
        if path == "/api/v1/entity-extraction/extract":
            return 200, {"entities": [{"kind": "technical_identifier", "text": "CE-42", "exact": True}]}
        if path == "/api/v1/lexical-retrieval/search":
            return 200, {"candidates": [candidate], "truncated": False}
        if path == "/api/v1/vector-retrieval/search":
            return 200, {"metric": "cosine", "candidates": [], "truncated": False}
        if path == "/api/v1/knowledge/sources/verify-revisions":
            return 200, {"results": [{"source_id": "knowledge:src-1", "requested_revision_sequence": 1, "status": "current"}]}
        if path == "/api/v1/ranking/rank":
            return 200, {"candidates": [{
                "source_id": "knowledge:src-1", "source_revision": "rev-1", "revision_sequence": 1,
                "chunk_id": "chunk-1", "chunker": candidate["chunker"], "rank": 1, "score": 100,
                "score_semantics": "rrf-v1", "evidence": [{"retrieval_path": "lexical", "retrieval_rank": 1}],
                "provenance": {"origin": "fixture"}, "text": candidate["text"],
                "matched_exact_identifiers": ["CE-42"],
            }]}
        raise AssertionError(f"unexpected REST call: {method} {path}")

    service = GatewayService(transport=transport)
    result = service.search({
        "request_id": "req-1", "query": "find CE-42", "scope": {"type": "project", "id": "p1", "visibility": "private"},
        "mode": "lookup", "context_budget": {"unit": "provider_tokens", "model": "test-model", "max": 100},
    }, "req-1")
    assert result["status"] == "complete"
    assert result["plan"]["intent"] == "knowledge_lookup"
    assert result["candidates"][0]["freshness"] == "verified_current"
    assert result["candidates"][0]["matched_exact_identifiers"] == ["CE-42"]
    assert "token_budget_estimated" not in result["degradation_reasons"]
    assert "knowledge:src-1@1" in result["context"]
    assert any(path == "/api/v1/ranking/rank" for _, path, _ in calls)


def test_gateway_filters_stale_candidates_before_ranking(monkeypatch):
    monkeypatch.setenv("CE_GATEWAY_WRITE_PROFILE_NAME", "default")
    index_profile = {"name": "default", "version": "0.1", "digest": "a" * 64}
    bundle = {**index_profile, "lexical": {"profile": "technical-default", "version": "0.1"},
              "embedding": {"profile": "default-embedding", "version": "0.1"}}
    candidate = _candidate()
    calls = []

    def transport(method, path, payload, request_id, headers, timeout):
        calls.append(path)
        if path == "/api/v1/index/generations/active":
            return 200, {"generation_id": "gen-1", "index_profile": index_profile}
        if path == "/api/v1/index/profiles/default/versions/0.1":
            return 200, {"bundle": bundle, **index_profile}
        if path == "/api/v1/intent-classification/classify":
            return 200, {"results": [{"intent": "general"}]}
        if path == "/api/v1/entity-extraction/extract":
            return 200, {"entities": []}
        if path == "/api/v1/lexical-retrieval/search":
            return 200, {"candidates": [candidate], "truncated": False}
        if path == "/api/v1/vector-retrieval/search":
            return 200, {"metric": "cosine", "candidates": [], "truncated": False}
        if path == "/api/v1/knowledge/sources/verify-revisions":
            return 200, {"results": [{"source_id": "knowledge:src-1", "requested_revision_sequence": 1, "status": "stale"}]}
        if path == "/api/v1/ranking/rank":
            assert payload["lists"][0]["candidates"] == []
            return 200, {"candidates": []}
        raise AssertionError(f"unexpected REST call: {method} {path}")

    result = GatewayService(transport=transport).search({
        "query": "find source", "scope": {"type": "project", "id": "p1", "visibility": "private"},
        "mode": "lookup", "context_budget": {"unit": "provider_tokens", "model": "test-model", "max": 100},
    }, "req-2")
    assert result["candidates"] == []
    assert "stale_candidates_filtered" in result["degradation_reasons"]
    assert "/api/v1/ranking/rank" in calls


def test_gateway_health_route_is_reachable():
    from runtime.server import BoundedThreadingHTTPServer, Handler
    import json
    import threading
    from urllib.request import urlopen

    server = BoundedThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/api/v1/gateway/health", timeout=2) as response:
            assert response.status == 200
            assert json.loads(response.read())["service"] == "gateway"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)



def test_gateway_request_route_dispatches_to_service(monkeypatch):
    import json
    import threading
    from urllib.request import Request, urlopen

    from runtime.gateway import GatewayService
    from runtime.server import BoundedThreadingHTTPServer, Handler

    def fake_search(self, body, request_id):
        assert body == {"query": "test query"}
        return {"request_id": request_id, "status": "complete", "candidates": [], "degraded": False}

    monkeypatch.setattr(GatewayService, "search", fake_search)
    server = BoundedThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/v1/requests",
            data=json.dumps({"query": "test query"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=2) as response:
            payload = json.loads(response.read())
            assert response.status == 200
            assert payload["status"] == "complete"
            assert payload["request_id"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
