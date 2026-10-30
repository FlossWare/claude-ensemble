from __future__ import annotations

from runtime.gateway import GatewayService


def test_gateway_relationship_request_verifies_graph_support_and_reranks_only_non_exact():
    calls = []
    profile_bundle = {
        "name": "default", "version": "0.1", "digest": "d" * 64,
        "lexical": {"profile": "bm25-v1", "version": "0.1"},
        "embedding": {"profile": "technical-default", "version": "0.1"},
    }
    exact_candidate = {
        "source_id": "knowledge:source-exact", "source_revision": "rev-1",
        "revision_sequence": 1, "chunk_id": "chunk-exact",
        "chunker": {"profile": "markdown-default", "version": "0.1"},
        "retrieval_rank": 1, "text": "Service A implements CE-42.",
        "matched_exact_identifiers": [], "provenance": {"origin": "test"},
    }
    other_candidate = {
        "source_id": "knowledge:source-other", "source_revision": "rev-2",
        "revision_sequence": 2, "chunk_id": "chunk-other",
        "chunker": {"profile": "markdown-default", "version": "0.1"},
        "retrieval_rank": 2, "text": "Service B calls Service A.",
        "matched_exact_identifiers": [], "provenance": {"origin": "test"},
    }

    def fake_rest(method, path, payload, request_id, headers, timeout):
        calls.append((method, path, payload))
        if method == "GET" and path == "/api/v1/index/generations/active":
            return 200, {"generation_id": "generation-1", "index_profile": {
                "name": "default", "version": "0.1", "digest": "d" * 64,
            }}
        if method == "GET" and path == "/api/v1/index/profiles/default/versions/0.1":
            return 200, {"bundle": profile_bundle}
        if path == "/api/v1/intent-classification/classify":
            return 200, {"results": [{"intent": "relationship_exploration"}]}
        if path == "/api/v1/entity-extraction/extract":
            return 200, {"entities": [{"text": "Service A"}, {"text": "Service B"}]}
        if path == "/api/v1/lexical-retrieval/search":
            return 200, {"candidates": [exact_candidate, other_candidate], "truncated": False}
        if path == "/api/v1/vector-retrieval/search":
            return 200, {"candidates": [], "truncated": False}
        if path in {"/api/v1/knowledge/sources/verify-revisions",
                    "/api/v1/memories/verify-revisions"}:
            return 200, {"results": [
                {"source_id": item["source_id"],
                 "requested_revision_sequence": item["revision_sequence"], "status": "current"}
                for item in payload["items"]
            ]}
        if path == "/api/v1/graph/traversals":
            assert payload["entity_mentions"] == ["Service A", "Service B"]
            return 200, {
                "resolution_evidence": [{
                    "entity_mention": "Service A", "node_id": "node-a",
                    "supports": [{"source_id": "knowledge:graph-source", "source_revision": "rev-3",
                                  "revision_sequence": 3}],
                }],
                "paths": [{
                    "path_id": "path-1", "node_ids": ["node-a", "node-b"],
                    "edges": [{
                        "source_node_id": "node-a", "target_node_id": "node-b",
                        "relationship_type": "calls", "supports": [
                            {"source_id": "knowledge:graph-source", "source_revision": "rev-3",
                             "revision_sequence": 3}
                        ],
                    }],
                }],
                "truncated": False,
            }
        if path == "/api/v1/ranking/rank":
            return 200, {"candidates": [
                {**exact_candidate, "rank": 1, "score": 100, "score_semantics": "rrf-v1",
                 "evidence": [], "matched_exact_identifiers": ["CE-42"]},
                {**other_candidate, "rank": 2, "score": 50, "score_semantics": "rrf-v1",
                 "evidence": [], "matched_exact_identifiers": []},
            ]}
        if path == "/api/v1/reranking/rerank":
            assert len(payload["candidates"]) == 1
            assert payload["candidates"][0]["source_id"] == "knowledge:source-other"
            return 200, {"candidates": [{
                "source_id": "knowledge:source-other", "revision_sequence": 2,
                "chunk_id": "chunk-other",
                "chunker": {"profile": "markdown-default", "version": "0.1"},
                "rerank": 1,
            }]}
        raise AssertionError(f"unexpected REST call: {method} {path}")

    service = GatewayService(transport=fake_rest)
    response = service.search({
        "query": "How does Service A relate to Service B and CE-42?",
        "scope": {"type": "project", "id": "p1", "visibility": "private"},
        "mode": "lookup",
        "context_budget": {"unit": "provider_tokens", "model": "test-model", "max": 1000},
    }, "request-graph-rerank")

    assert response["status"] == "complete"
    assert [item["source_id"] for item in response["candidates"]] == [
        "knowledge:source-exact", "knowledge:source-other"
    ]
    assert "Graph relationship: node-a -[calls]-> node-b" in response["context"]
    assert any(path == "/api/v1/graph/traversals" for _, path, _ in calls)
    assert any(path == "/api/v1/reranking/rerank" for _, path, _ in calls)
    graph_verification = [
        payload for _, path, payload in calls
        if path == "/api/v1/knowledge/sources/verify-revisions"
    ]
    assert any(any(item["source_id"] == "knowledge:graph-source" for item in payload["items"])
               for payload in graph_verification)


def test_gateway_reranking_failure_falls_back_to_ranking_order():
    calls = []
    profile_bundle = {
        "name": "default", "version": "0.1", "digest": "d" * 64,
        "lexical": {"profile": "bm25-v1", "version": "0.1"},
        "embedding": {"profile": "technical-default", "version": "0.1"},
    }
    candidate = {
        "source_id": "knowledge:source-1", "source_revision": "rev-1",
        "revision_sequence": 1, "chunk_id": "chunk-1",
        "chunker": {"profile": "markdown-default", "version": "0.1"},
        "retrieval_rank": 1, "text": "A useful source chunk.",
        "matched_exact_identifiers": [], "provenance": {},
    }

    def fake_rest(method, path, payload, request_id, headers, timeout):
        calls.append(path)
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
            return 200, {"candidates": [candidate], "truncated": False}
        if path == "/api/v1/vector-retrieval/search":
            return 200, {"candidates": [], "truncated": False}
        if path == "/api/v1/knowledge/sources/verify-revisions":
            return 200, {"results": [{"source_id": "knowledge:source-1",
                                      "requested_revision_sequence": 1, "status": "current"}]}
        if path == "/api/v1/ranking/rank":
            return 200, {"candidates": [{**candidate, "rank": 1, "score": 10,
                                         "score_semantics": "rrf-v1", "evidence": []}]}
        if path == "/api/v1/reranking/rerank":
            from runtime.gateway import GatewayError
            raise GatewayError("dependency_unavailable", "reranker unavailable", 503, True)
        raise AssertionError(f"unexpected REST call: {method} {path}")

    response = GatewayService(transport=fake_rest).search({
        "query": "find useful source", "scope": {"type": "project", "id": "p1", "visibility": "private"},
        "mode": "lookup", "context_budget": {"unit": "provider_tokens", "model": "test-model", "max": 100},
    }, "request-rerank-fallback")

    assert response["status"] == "partial"
    assert response["candidates"][0]["source_id"] == "knowledge:source-1"
    assert "reranking_degraded" in response["degradation_reasons"]
    assert "/api/v1/reranking/rerank" in calls
