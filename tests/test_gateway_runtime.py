import base64
from datetime import datetime, timezone

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
    propagated_deadlines = []

    def transport(method, path, payload, request_id, headers, timeout):
        calls.append((method, path, payload))
        propagated_deadlines.append((headers.get("X-CE-Deadline"), timeout))
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
    }, "req-1", headers={"X-CE-Deadline": "2099-01-01T00:00:00Z"})
    assert result["status"] == "complete"
    assert propagated_deadlines
    request_deadline = datetime(2099, 1, 1, tzinfo=timezone.utc)
    parsed_deadlines = [
        datetime.fromisoformat(deadline.replace("Z", "+00:00"))
        for deadline, _ in propagated_deadlines
    ]
    assert all(deadline <= request_deadline for deadline in parsed_deadlines)
    assert any(deadline < request_deadline for deadline in parsed_deadlines)
    assert all(0 < timeout <= 30.0 for _, timeout in propagated_deadlines)
    assert result["plan"]["intent"] == "knowledge_lookup"
    assert result["context_budget"]["model"] == "test-model"
    assert result["context_budget"]["counting_method"] == "conservative_utf8_byte_upper_bound"
    assert result["context_budget"]["is_estimate"] is True
    assert result["context_budget"]["fallback_reason"] == "no_configured_tokenizer"
    assert result["candidates"][0]["freshness"] == "verified_current"
    assert result["candidates"][0]["matched_exact_identifiers"] == ["CE-42"]
    assert "token_budget_estimated" not in result["degradation_reasons"]
    assert "knowledge:src-1@1" in result["context"]
    assert result["context_budget"]["used"] == len(result["context"].encode("utf-8"))
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
    assert result["index_freshness"] == "unknown"
    assert "stale_candidates_filtered" in result["degradation_reasons"]
    assert "/api/v1/ranking/rank" in calls



def test_gateway_after_operation_id_waits_until_indexing_is_complete():
    service = GatewayService()
    calls = []
    states = iter(["pending_index", "pending_index", "indexed"])

    def call(method, path, payload=None, request_id="req-barrier", headers=None, timeout=30.0):
        calls.append((method, path, timeout))
        return 200, {"status": "accepted", "indexing_status": next(states)}

    service._wait_for_operation(
        "knowledge:op:abc123",
        {"type": "project", "id": "p1", "visibility": "private"},
        "req-barrier",
        call,
        None,
    )
    assert len(calls) == 3
    assert all(method == "GET" for method, _, _ in calls)
    assert all(path == "/api/v1/knowledge/operations/knowledge:op:abc123" for _, path, _ in calls)
    assert all(0 < timeout <= 1.0 for _, _, timeout in calls)


def test_gateway_after_operation_id_rejects_unknown_owner():
    import pytest
    from runtime.gateway import GatewayError

    with pytest.raises(GatewayError) as error:
        GatewayService()._wait_for_operation(
            "other:op:abc123",
            {"type": "project", "id": "p1", "visibility": "private"},
            "req-barrier",
            lambda *args, **kwargs: (200, {"indexing_status": "indexed"}),
            None,
        )
    assert error.value.code == "invalid_request"



def test_gateway_chunks_freshness_verification_at_owner_contract_limit():
    calls = []

    def transport(method, path, payload, request_id, headers, timeout):
        assert method == "POST"
        assert path == "/api/v1/memories/verify-revisions"
        items = payload["items"]
        assert 1 <= len(items) <= 100
        calls.append(len(items))
        return 200, {
            "results": [
                {
                    "source_id": item["source_id"],
                    "requested_revision_sequence": item["revision_sequence"],
                    "status": "current",
                }
                for item in items
            ]
        }

    candidates = [
        {"source_id": f"memory:src-{index:03d}", "revision_sequence": 1}
        for index in range(150)
    ]
    reasons = []
    failures = []
    fresh = GatewayService(transport=transport)._fresh_candidates(
        candidates, "req-chunked-freshness", reasons, failures
    )

    assert calls == [100, 50]
    assert len(fresh) == 150
    assert reasons == []
    assert failures == []


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



def test_gateway_request_route_runs_rag_orchestration_over_http(monkeypatch):
    import json
    import threading
    from urllib.request import Request, urlopen

    from runtime.gateway import GatewayService
    from runtime.server import BoundedThreadingHTTPServer, Handler

    monkeypatch.setenv("CE_GATEWAY_WRITE_PROFILE_NAME", "default")
    identity = {"name": "default", "version": "0.1", "digest": "a" * 64}
    bundle = {
        **identity,
        "lexical": {"profile": "technical-default", "version": "0.1"},
        "embedding": {"profile": "default-embedding", "version": "0.1"},
    }
    candidate = {
        "source_id": "knowledge:src-1",
        "source_revision": "rev-1",
        "revision_sequence": 1,
        "chunk_id": "chunk-1",
        "chunker": {"profile": "markdown-default", "version": "0.1"},
        "retrieval_rank": 1,
        "score_semantics": "bm25-v1",
        "text": "CE-42 is a useful source chunk",
        "matched_exact_identifiers": [],
        "provenance": {"origin": "fixture"},
        "score": 1.2,
    }

    def fake_rest(self, method, path, payload=None, request_id="gateway", headers=None, timeout=30.0):
        if method == "GET" and path == "/api/v1/index/generations/active":
            return 200, {"generation_id": "gen-1", "index_profile": identity}
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

    monkeypatch.setattr(GatewayService, "_call", fake_rest)
    server = BoundedThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = {
            "request_id": "req-route",
            "query": "find CE-42",
            "scope": {"type": "project", "id": "p1", "visibility": "private"},
            "mode": "lookup",
            "context_budget": {"unit": "provider_tokens", "model": "test-model", "max": 100},
        }
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/v1/requests",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=2) as response:
            payload = json.loads(response.read())
            assert response.status == 200
            assert payload["status"] == "complete"
            assert payload["request_id"] == "req-route"
            assert payload["candidates"][0]["freshness"] == "verified_current"
            assert "knowledge:src-1@1" in payload["context"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)



def test_gateway_rag_acceptance_uses_real_http_services_without_transport_mocking(monkeypatch, tmp_path):
    """Exercise Gateway, retrieval, freshness, and ranking through the actual HTTP handlers."""
    import json
    import threading
    from urllib.request import Request, urlopen

    import runtime.index as index_module
    import runtime.knowledge as knowledge_module
    from runtime.index import IndexService, profile_digest
    from runtime.knowledge import KnowledgeService
    from runtime.server import BoundedThreadingHTTPServer, Handler

    monkeypatch.setenv("CE_INDEX_VECTOR_BACKEND", "sqlite")
    monkeypatch.setenv("CE_GATEWAY_WRITE_PROFILE_NAME", "default")

    bundle = {
        "name": "default",
        "version": "0.1",
        "status": "active",
        "chunking": {"profile": "markdown-default", "version": "0.1", "max_units": 1200, "overlap_units": 120},
        "tokenization": {"profile": "technical-default", "version": "0.1"},
        "lexical": {"profile": "bm25-v1", "version": "0.1", "statistics_policy": "scope_partition"},
        "embedding": {
            "required": True, "profile": "technical-default", "version": "0.1",
            "model": "local-nomic", "model_version": "r1", "input_types": ["query", "document"],
            "dimensions": 3, "normalization": "l2", "metric": "cosine", "max_input_tokens": 8192,
        },
        "limits": {
            "max_chunks": 64, "max_source_bytes": 131072, "max_chunk_text_bytes": 512,
            "max_request_bytes": 2097152, "max_chunk_representation_bytes": 18000,
            "max_envelope_bytes": 16384, "max_metadata_bytes": 1024,
            "max_lexical_terms_per_chunk": 64, "max_lexical_term_bytes": 32,
        },
    }
    bundle["digest"] = profile_digest(bundle)
    identity = {key: bundle[key] for key in ("name", "version", "digest")}
    scope = {"type": "project", "id": "gateway-integration", "visibility": "private"}
    content = "Search service uses FlossWare and confirms CE-42 behavior."
    index_service = IndexService(tmp_path / "index.sqlite3", bundle)
    knowledge_service = KnowledgeService(tmp_path / "knowledge.sqlite3")
    monkeypatch.setattr(index_module, "_service", index_service)
    monkeypatch.setattr(knowledge_module, "_SERVICE", knowledge_service)

    _, created = knowledge_service.create({
        "scope": scope,
        "source_kind": "document",
        "content": content,
        "provenance": {"origin": "gateway-integration-test"},
        "retention_policy": {"policy": "test"},
        "index_profile": identity,
    }, "gateway-integration-source", "gateway-integration-test")
    source_id = created["source_id"]

    import runtime.graph as graph_module
    import runtime.server as server_module
    from runtime.graph import GraphService
    from runtime.reranking import EXPECTED_MODEL_ID, RerankingEngine

    graph_service = GraphService(tmp_path / "graph.sqlite3")
    graph_service.project({
        "operation_id": "knowledge-gateway-integration",
        "source_id": source_id,
        "source_revision": created["revision"],
        "revision_sequence": 1,
        "owner_projection_sequence": 1,
        "scope": scope,
        "nodes": [
            {"node_id": "node-search", "node_type": "service", "label": "Search"},
            {"node_id": "node-flossware", "node_type": "project", "label": "FlossWare"},
        ],
        "edges": [{
            "edge_id": "edge-search-flossware",
            "source_node_id": "node-search",
            "target_node_id": "node-flossware",
            "relationship_type": "uses",
            "directed": True,
        }],
    }, "gateway-integration-graph")
    monkeypatch.setattr(graph_module, "_service_instance", graph_service)

    class FixedCrossEncoder:
        def predict(self, pairs, **kwargs):
            return [0.9 for _ in pairs]

    monkeypatch.setattr(
        server_module, "classify_intent",
        lambda request: {"results": [{"intent": "relationship_exploration"}]},
    )

    class FixedEntityExtractor:
        def extract(self, text):
            return [{"text": "Search"}, {"text": "FlossWare"}]

    monkeypatch.setattr(server_module, "get_entity_extractor", lambda: FixedEntityExtractor())
    monkeypatch.setattr(
        server_module, "get_reranking_engine",
        lambda: RerankingEngine(
            model=FixedCrossEncoder(), model_id=EXPECTED_MODEL_ID, model_version="integration-test"
        ),
    )

    index_service.upsert({
        "operation_id": "gateway-integration-index",
        "request_id": "gateway-integration-test",
        "source": {
            "source_id": source_id,
            "revision": created["revision"],
            "revision_sequence": 1,
            "scope": scope,
        },
        "index_profile": identity,
        "representations": [{
            "chunk_id": "gateway-integration-chunk",
            "chunker": {"profile": "markdown-default", "version": "0.1"},
            "text": content,
            "lexical": {"profile": "bm25-v1", "version": "0.1",
                        "terms": ["search", "service", "uses", "flossware", "confirms", "behavior"]},
            "vector": {"input_type": "document", "model": "local-nomic", "version": "r1",
                       "dimensions": 3, "values": [1.0, 0.0, 0.0]},
            "metadata": {},
        }],
    }, "gateway-integration-index")

    propagated = []
    original_call = GatewayService._call

    def recording_call(self, method, path, payload=None, request_id="gateway", headers=None, timeout=30.0):
        if headers and headers.get("X-CE-Deadline"):
            propagated.append((headers["X-CE-Deadline"], timeout, path))
        return original_call(self, method, path, payload, request_id, headers, timeout)

    monkeypatch.setattr(GatewayService, "_call", recording_call)
    internal_paths = []

    class RecordingHandler(Handler):
        def do_POST(self):
            if self.headers.get("X-CE-Internal-Call") == "true":
                internal_paths.append(self.path)
            super().do_POST()

    server = BoundedThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
    base_url = f"http://127.0.0.1:{server.server_port}"
    for name in ("CE_INDEX_BASE_URL", "CE_TOKENIZATION_BASE_URL", "CE_EMBEDDING_BASE_URL", "CE_RERANKING_BASE_URL"):
        monkeypatch.setenv(name, base_url)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = {
            "request_id": "req-real-rag",
            "query": "How does Search relate to FlossWare?",
            "scope": scope,
            "mode": "lookup",
            "context_budget": {"unit": "provider_tokens", "model": "test-model", "max": 100},
        }
        request = Request(
            f"{base_url}/api/v1/requests",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-CE-Deadline": "2099-01-01T00:00:00Z",
            },
            method="POST",
        )
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read())
            assert response.status == 200
            from jsonschema import Draft202012Validator
            from pathlib import Path
            gateway_schema = json.loads(
                (Path(__file__).resolve().parents[1] / "docs/contracts/schemas/gateway.schema.json").read_text()
            )
            response_schema = {
                "$schema": gateway_schema["$schema"],
                "$defs": gateway_schema["$defs"],
                "$ref": "#/$defs/response",
            }
            Draft202012Validator(response_schema).validate(payload)
            assert payload["request_id"] == "req-real-rag"
            assert payload["index_freshness"] == "current"
            assert any(candidate["source_id"] == source_id for candidate in payload["candidates"])
            assert f"[{source_id}@1]" in payload["context"]
            assert payload["candidates"][0]["freshness"] == "verified_current"
            assert "Graph relationship: node-search -[uses]-> node-flossware" in payload["context"]
            assert payload["context_budget"]["used"] == len(payload["context"].encode("utf-8"))
            assert "/api/v1/graph/traversals" in internal_paths
            assert "/api/v1/reranking/rerank" in internal_paths
            assert propagated
            request_deadline = datetime(2099, 1, 1, tzinfo=timezone.utc)
            parsed = [
                datetime.fromisoformat(deadline.replace("Z", "+00:00"))
                for deadline, _, _ in propagated
            ]
            assert all(deadline <= request_deadline for deadline in parsed)
            assert any(deadline < request_deadline for deadline in parsed)
            assert all(0 < timeout <= 30.0 for _, timeout, _ in propagated)

        from runtime.graph import GraphError
        from runtime.reranking import RerankingError

        class FailedGraphService:
            def handle(self, *args, **kwargs):
                raise GraphError("dependency_unavailable", "injected Graph outage", 503)

        monkeypatch.setattr(server_module, "get_graph_service", lambda: FailedGraphService())
        graph_failure_body = {**body, "request_id": "req-graph-outage"}
        graph_failure_request = Request(
            f"{base_url}/api/v1/requests",
            data=json.dumps(graph_failure_body).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-CE-Deadline": "2099-01-01T00:00:00Z"},
            method="POST",
        )
        with urlopen(graph_failure_request, timeout=10) as response:
            graph_failure = json.loads(response.read())
            assert response.status == 200
            Draft202012Validator(response_schema).validate(graph_failure)
            assert graph_failure["status"] == "partial"
            assert "graph_degraded" in graph_failure["degradation_reasons"]
            assert any(
                failure.get("required") is True and failure["code"] == "required_evidence_unavailable"
                for failure in graph_failure["failures"]
            )
            assert graph_failure["candidates"]

        monkeypatch.setattr(server_module, "get_graph_service", lambda: graph_service)

        class FailedReranker:
            def rerank(self, request):
                raise RerankingError("service_unavailable", "injected reranker outage", 503)

        monkeypatch.setattr(server_module, "get_reranking_engine", lambda: FailedReranker())
        rerank_failure_body = {**body, "request_id": "req-reranker-outage"}
        rerank_failure_request = Request(
            f"{base_url}/api/v1/requests",
            data=json.dumps(rerank_failure_body).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-CE-Deadline": "2099-01-01T00:00:00Z"},
            method="POST",
        )
        with urlopen(rerank_failure_request, timeout=10) as response:
            rerank_failure = json.loads(response.read())
            assert response.status == 200
            Draft202012Validator(response_schema).validate(rerank_failure)
            assert rerank_failure["status"] == "partial"
            assert "reranking_degraded" in rerank_failure["degradation_reasons"]
            assert rerank_failure["candidates"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)



def test_gateway_assembly_deadline_returns_partial_context_instead_of_504(monkeypatch):
    import time

    monkeypatch.setenv("CE_GATEWAY_WRITE_PROFILE_NAME", "default")
    profile_bundle = {
        "name": "default", "version": "0.1", "digest": "d" * 64,
        "lexical": {"profile": "bm25-v1", "version": "0.1"},
        "embedding": {"profile": "technical-default", "version": "0.1"},
    }
    source_candidate = _candidate()

    class SlowAssemblyCandidate(dict):
        def get(self, key, default=None):
            if key == "text":
                time.sleep(0.12)
            return super().get(key, default)

    ranked_candidate = SlowAssemblyCandidate({
        **source_candidate, "rank": 1, "score": 10,
        "score_semantics": "rrf-v1", "evidence": [],
        "matched_exact_identifiers": ["CE-42"],
    })

    def transport(method, path, payload, request_id, headers, timeout):
        if path == "/api/v1/index/generations/active":
            return 200, {"generation_id": "generation-1", "index_profile": {
                "name": "default", "version": "0.1", "digest": "d" * 64,
            }}
        if path == "/api/v1/index/profiles/default/versions/0.1":
            return 200, {"bundle": profile_bundle}
        if path == "/api/v1/intent-classification/classify":
            return 200, {"results": [{"intent": "general"}]}
        if path == "/api/v1/entity-extraction/extract":
            return 200, {"entities": []}
        if path == "/api/v1/lexical-retrieval/search":
            return 200, {"candidates": [source_candidate], "truncated": False}
        if path == "/api/v1/vector-retrieval/search":
            return 200, {"candidates": [], "truncated": False}
        if path == "/api/v1/knowledge/sources/verify-revisions":
            return 200, {"results": [{
                "source_id": source_candidate["source_id"],
                "requested_revision_sequence": source_candidate["revision_sequence"],
                "status": "current",
            }]}
        if path == "/api/v1/ranking/rank":
            return 200, {"candidates": [ranked_candidate]}
        raise AssertionError(f"unexpected REST call: {method} {path}")

    result = GatewayService(transport=transport).search({
        "query": "find CE-42",
        "scope": {"type": "project", "id": "p1", "visibility": "private"},
        "mode": "lookup",
        "context_budget": {"unit": "provider_tokens", "model": "test-model", "max": 100},
    }, "req-assembly-deadline")

    assert result["status"] == "partial"
    assert result["degraded"] is True
    assert result["truncated"] is True
    assert "assembly_degraded" in result["degradation_reasons"]
    assert result["candidates"][0]["source_id"] == source_candidate["source_id"]
    assert "knowledge:src-1@1" in result["context"]


def test_context_budget_uses_configured_local_model_tokenizer(monkeypatch):
    import runtime.context_budget as context_budget

    class FakeTokenizer:
        def encode(self, text, add_special_tokens=False):
            assert text == "provider-specific text"
            assert add_special_tokens is False
            return [101, 102, 103, 104]

    monkeypatch.setenv("CE_GATEWAY_TOKENIZER_MAP", '{"test-model": "/provisioned/tokenizer"}')
    monkeypatch.setattr(context_budget, "_load_tokenizer", lambda path: FakeTokenizer())
    count, method, fallback = context_budget.count_context_tokens("provider-specific text", "test-model")
    assert count == 4
    assert method == "configured_model_tokenizer"
    assert fallback is None


def test_context_budget_fallback_is_explicit_and_uses_utf8_bytes(monkeypatch):
    from runtime.context_budget import count_context_tokens

    monkeypatch.delenv("CE_GATEWAY_TOKENIZER_MAP", raising=False)
    value = "Aé"
    count, method, fallback = count_context_tokens(value, "unconfigured-model")
    assert count == len(value.encode("utf-8"))
    assert method == "conservative_utf8_byte_upper_bound"
    assert fallback == "no_configured_tokenizer"
