"""Contract and HTTP tests for deterministic Ranking."""
import base64
import json
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator

from runtime.ranking import RankingError, rank
from runtime.server import BoundedThreadingHTTPServer, Handler

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "docs/contracts/schemas/ranking.schema.json").read_text())


def make_candidate(chunk_id, rank_value, *, source_id="knowledge:doc1", sequence=1,
                   text=None, matched=None, source="lexical", score_semantics="bm25",
                   source_score=1.25, revision="rev-1"):
    return {
        "source_id": source_id,
        "source_revision": revision,
        "revision_sequence": sequence,
        "chunk_id": chunk_id,
        "chunker": {"profile": "markdown-default", "version": "0.1"},
        "retrieval_source": source,
        "retrieval_rank": rank_value,
        "source_score": source_score,
        "score_semantics": score_semantics,
        "text": text if text is not None else f"text for {chunk_id}",
        "matched_exact_identifiers": list(matched or []),
        "provenance": {"origin": "unit-test", "evidence_ids": [chunk_id]},
    }


def make_list(path, scope, candidates):
    encoded = base64.urlsafe_b64encode(scope.encode("utf-8")).decode("ascii").rstrip("=")
    return {
        "list_id": f"rl1:{path}:original:{encoded}",
        "retrieval_path": path,
        "query_variant_id": "original",
        "scope_partition_id": scope,
        "candidates": candidates,
    }


def request(lists, *, exact=None, limit=20):
    return {
        "request_id": "ranking-test-1",
        "policy": {"name": "rrf-v1", "version": "1"},
        "exact_identifiers": list(exact or []),
        "lists": lists,
        "limit": limit,
    }


class RankingUnitTests(unittest.TestCase):
    def test_fixed_point_rrf_fuses_candidates_and_preserves_evidence(self):
        lexical = make_list("lexical", "project-A", [
            make_candidate("chunk-a", 1, source="lexical", score_semantics="bm25", source_score=100.0),
            make_candidate("chunk-b", 2, source="lexical", score_semantics="bm25", source_score=8.0),
        ])
        vector = make_list("vector", "project-A", [
            make_candidate("chunk-a", 2, source="vector", score_semantics="cosine-distance", source_score=0.2),
            make_candidate("chunk-c", 1, source="vector", score_semantics="cosine-distance", source_score=0.1),
        ])
        result = rank(request([lexical, vector]))
        Draft202012Validator(SCHEMA).validate({**result, "request_id": "ranking-test-1"})
        self.assertEqual([item["chunk_id"] for item in result["candidates"]], ["chunk-a", "chunk-c", "chunk-b"])
        chunk_a = result["candidates"][0]
        self.assertEqual(chunk_a["score"], 1_000_000_000_000 // 61 + 1_000_000_000_000 // 62)
        self.assertEqual(len(chunk_a["evidence"]), 2)
        self.assertEqual({item["retrieval_path"] for item in chunk_a["evidence"]}, {"lexical", "vector"})
        self.assertEqual(chunk_a["score_semantics"], "rrf-v1-fixed-point-1e12")

    def test_cross_path_provenance_can_differ_without_conflicting_source_identity(self):
        lexical_candidate = make_candidate("shared", 1, source="lexical")
        vector_candidate = make_candidate("shared", 2, source="vector")
        vector_candidate["provenance"] = {
            "index_generation": "generation-1",
            "embedding_model": "nomic",
            "embedding_model_version": "revision-1",
        }
        result = rank(request([
            make_list("lexical", "project-A", [lexical_candidate]),
            make_list("vector", "project-A", [vector_candidate]),
        ]))
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(len(result["candidates"][0]["evidence"]), 2)
        self.assertEqual(result["candidates"][0]["provenance"], lexical_candidate["provenance"])
        evidence_by_path = {item["retrieval_path"]: item for item in result["candidates"][0]["evidence"]}
        self.assertEqual(evidence_by_path["lexical"]["provenance"], lexical_candidate["provenance"])
        self.assertEqual(evidence_by_path["vector"]["provenance"], vector_candidate["provenance"])

    def test_exact_identifier_tier_precedes_higher_rrf_score(self):
        lexical = make_list("lexical", "project-A", [
            make_candidate("common", 1),
            make_candidate("exact", 2, source_id="knowledge:doc2", matched=["REV-17"]),
        ])
        result = rank(request([lexical], exact=["REV-17"]))
        self.assertEqual([item["chunk_id"] for item in result["candidates"]], ["exact", "common"])
        self.assertEqual(result["candidates"][0]["matched_exact_identifiers"], ["REV-17"])

    def test_duplicates_in_one_list_count_once_at_earliest_rank_and_union_matches(self):
        candidates = [
            make_candidate("same", 4, matched=["ID-A"]),
            make_candidate("same", 1, matched=["ID-B"]),
        ]
        result = rank(request([make_list("lexical", "project-A", candidates)], exact=["ID-A", "ID-B"]))
        item = result["candidates"][0]
        self.assertEqual(item["score"], 1_000_000_000_000 // 61)
        self.assertEqual(item["matched_exact_identifiers"], ["ID-A", "ID-B"])
        self.assertEqual(len(item["evidence"]), 1)
        self.assertEqual(item["evidence"][0]["retrieval_rank"], 1)

    def test_distinct_source_revisions_are_not_deduplicated(self):
        candidates = [
            make_candidate("same-chunk", 1, sequence=1, revision="rev-1"),
            make_candidate("same-chunk", 2, sequence=2, revision="rev-2"),
        ]
        result = rank(request([make_list("lexical", "project-A", candidates)]))
        self.assertEqual(len(result["candidates"]), 2)
        self.assertEqual([item["revision_sequence"] for item in result["candidates"]], [1, 2])

    def test_sort_order_is_deterministic_for_ties(self):
        candidates = [
            make_candidate("chunk-z", 1, source_id="knowledge:z"),
            make_candidate("chunk-b", 1, source_id="knowledge:b"),
            make_candidate("chunk-a", 1, source_id="knowledge:a"),
        ]
        value = request([
            make_list("lexical", "project-A", [candidates[0]]),
            make_list("lexical", "project-B", [candidates[1]]),
            make_list("lexical", "project-C", [candidates[2]]),
        ])
        first = rank(value)
        second = rank(value)
        self.assertEqual(first, second)
        self.assertEqual([item["source_id"] for item in first["candidates"]],
                         ["knowledge:a", "knowledge:b", "knowledge:z"])

    def test_duplicate_list_id_is_rejected(self):
        ranked_list = make_list("lexical", "project-A", [make_candidate("a", 1)])
        with self.assertRaises(RankingError) as caught:
            rank(request([ranked_list, ranked_list]))
        self.assertEqual(caught.exception.code, "duplicate_list_id")
        self.assertEqual(caught.exception.status, 400)

    def test_duplicate_retrieval_rank_is_rejected(self):
        ranked_list = make_list("lexical", "project-A", [
            make_candidate("a", 1), make_candidate("b", 1, source_id="knowledge:doc2"),
        ])
        with self.assertRaises(RankingError) as caught:
            rank(request([ranked_list]))
        self.assertEqual(caught.exception.code, "duplicate_retrieval_rank")

    def test_candidate_identity_conflict_is_rejected(self):
        lexical = make_list("lexical", "project-A", [make_candidate("a", 1, text="first")])
        vector = make_list("vector", "project-A", [make_candidate("a", 1, source="vector", text="different")])
        with self.assertRaises(RankingError) as caught:
            rank(request([lexical, vector]))
        self.assertEqual(caught.exception.code, "candidate_identity_conflict")
        self.assertEqual(caught.exception.status, 409)

    def test_candidate_cannot_claim_unrequested_exact_identifier(self):
        ranked_list = make_list("lexical", "project-A", [make_candidate("a", 1, matched=["REV-17"])])
        with self.assertRaises(RankingError) as caught:
            rank(request([ranked_list], exact=[]))
        self.assertEqual(caught.exception.code, "invalid_candidate")

    def test_unsupported_policy_is_rejected(self):
        value = request([make_list("lexical", "project-A", [])])
        value["policy"] = {"name": "other", "version": "1"}
        with self.assertRaises(RankingError) as caught:
            rank(value)
        self.assertEqual(caught.exception.code, "unsupported_policy")
        self.assertEqual(caught.exception.status, 422)

    def test_empty_candidate_lists_are_valid(self):
        result = rank(request([make_list("lexical", "project-A", [])]))
        self.assertEqual(result["candidates"], [])


class RankingHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = BoundedThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=2)

    def request(self, method, path, body=None):
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {"X-CE-Request-ID": "ranking-http-test"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request_obj = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request_obj, timeout=3) as response:
                return response.status, response.headers, json.load(response)
        except HTTPError as error:
            return error.code, error.headers, json.load(error)

    def test_rank_endpoint_and_health_routes(self):
        body = request([make_list("lexical", "project-A", [make_candidate("a", 1)])])
        status, headers, result = self.request("POST", "/api/v1/ranking/rank", body)
        self.assertEqual(status, 200)
        self.assertEqual(result["request_id"], "ranking-http-test")
        self.assertEqual(headers["X-CE-Request-ID"], "ranking-http-test")
        Draft202012Validator(SCHEMA).validate(result)
        status, _, health = self.request("GET", "/api/v1/ranking/health")
        self.assertEqual(status, 200)
        self.assertEqual((health["service"], health["status"]), ("ranking", "alive"))
        status, _, ready = self.request("GET", "/api/v1/ranking/ready")
        self.assertEqual(status, 200)
        self.assertTrue(ready["ready"])

    def test_duplicate_rank_error_uses_common_envelope(self):
        body = request([make_list("lexical", "project-A", [
            make_candidate("a", 1), make_candidate("b", 1, source_id="knowledge:doc2"),
        ])])
        status, _, result = self.request("POST", "/api/v1/ranking/rank", body)
        self.assertEqual(status, 400)
        self.assertEqual(result["error"]["code"], "duplicate_retrieval_rank")
        Draft202012Validator(SCHEMA).validate(result)


if __name__ == "__main__":
    unittest.main()
