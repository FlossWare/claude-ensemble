"""Durability, support semantics, and bounded traversal tests for Graph."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from runtime.graph import GraphError, GraphService


SCOPE = {"type": "project", "id": "project-1", "visibility": "private"}


class GraphRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / "graph.sqlite3"
        self.service = GraphService(self.db_path)

    def projection(self, *, operation_id="memory-op-1", source_id="memory:m1",
                   source_revision="rev-1", revision_sequence=1, owner_sequence=1,
                   nodes=None, edges=None, scope=None):
        return {
            "operation_id": operation_id,
            "source_id": source_id,
            "source_revision": source_revision,
            "revision_sequence": revision_sequence,
            "owner_projection_sequence": owner_sequence,
            "scope": scope or SCOPE,
            "nodes": nodes if nodes is not None else [
                {"node_id": "node-a", "node_type": "service", "label": "Search", "aliases": ["Solr"]},
                {"node_id": "node-b", "node_type": "project", "label": "FlossWare"},
            ],
            "edges": edges if edges is not None else [{
                "edge_id": "edge-local-1", "source_node_id": "node-a", "target_node_id": "node-b",
                "relationship_type": "uses", "directed": True,
            }],
        }

    def test_projection_is_durable_idempotent_and_schema_conformant(self):
        request = self.projection()
        status, response = self.service.project(request, "request-1")
        self.assertEqual(status, 202)
        self.assertEqual(response["status"], "complete")
        self.assertEqual(response["terminal_disposition"], "applied")
        graph_schema = __import__("json").loads(
            (Path(__file__).resolve().parents[1] / "docs/contracts/schemas/graph.schema.json").read_text()
        )
        response_schema = {"$schema": graph_schema["$schema"], "$defs": graph_schema["$defs"],
                           "$ref": "#/$defs/operationResponse"}
        Draft202012Validator(response_schema).validate(response)
        restarted = GraphService(self.db_path)
        retry_status, retry = restarted.project(request, "request-2")
        self.assertEqual(retry_status, 202)
        self.assertEqual(retry["operation_id"], response["operation_id"])
        self.assertEqual(retry["request_id"], "request-2")
        operation = restarted.operation("memory-op-1", "status-request")
        self.assertEqual(operation["status"], "complete")
        self.assertEqual(operation["request_id"], "status-request")

    def test_two_sources_share_one_relationship_with_independent_supports(self):
        first = self.projection()
        self.service.project(first, "r1")
        second = self.projection(
            operation_id="knowledge-op-1", source_id="knowledge:k1",
            source_revision="knowledge-rev-1", owner_sequence=1,
            edges=[{"edge_id": "knowledge-edge-7", "source_node_id": "node-a",
                    "target_node_id": "node-b", "relationship_type": "uses", "directed": True}],
        )
        self.service.project(second, "r2")
        result = self.service.traverse({"scope": SCOPE, "start_node_ids": ["node-a"],
                                        "direction": "outgoing"}, "query-1")
        self.assertEqual(len(result["paths"]), 1)
        self.assertEqual(len(result["paths"][0]["edges"]), 1)
        self.assertEqual(len(result["paths"][0]["edges"][0]["supports"]), 2)
        self.assertEqual(
            [support["source_id"] for support in result["paths"][0]["edges"][0]["supports"]],
            ["knowledge:k1", "memory:m1"],
        )

    def test_parallel_relationship_types_and_source_edge_ids_survive_traversal(self):
        request = self.projection(edges=[
            {"edge_id": "edge-uses-1", "source_node_id": "node-a", "target_node_id": "node-b",
             "relationship_type": "uses", "directed": True, "provenance": {"origin": "design"}},
            {"edge_id": "edge-depends-2", "source_node_id": "node-a", "target_node_id": "node-b",
             "relationship_type": "depends_on", "directed": True, "provenance": {"origin": "build"}},
        ])
        self.service.project(request, "parallel-edges")
        result = self.service.traverse({
            "scope": SCOPE, "start_node_ids": ["node-a"], "direction": "outgoing"
        }, "parallel-query")

        self.assertEqual(len(result["paths"]), 2)
        returned = [
            (path["edges"][0]["relationship_type"], path["edges"][0]["supports"][0]["source_edge_id"])
            for path in result["paths"]
        ]
        self.assertEqual(returned, [
            ("depends_on", "edge-depends-2"),
            ("uses", "edge-uses-1"),
        ])
        self.assertEqual(len({path["path_id"] for path in result["paths"]}), 2)

    def test_entity_mentions_use_exact_casefolded_label_and_alias_support(self):
        self.service.project(self.projection(), "r1")
        result = self.service.traverse({"scope": SCOPE, "entity_mentions": ["sOlR"]}, "query-2")
        self.assertEqual(result["resolved_start_node_ids"], ["node-a"])
        self.assertEqual(result["resolution_evidence"][0]["entity_mention"], "sOlR")
        self.assertEqual(result["resolution_evidence"][0]["supports"][0]["attribute_kind"], "alias")
        no_match = self.service.traverse({"scope": SCOPE, "entity_mentions": ["ol"]}, "query-3")
        self.assertEqual(no_match["unresolved_entity_mentions"], ["ol"])
        self.assertEqual(no_match["paths"], [])

    def test_tombstone_removes_only_source_support_and_blocks_late_projection(self):
        request = self.projection()
        self.service.project(request, "r1")
        _, deleted = self.service.delete_source({
            "operation_id": "memory-delete-1", "source_id": "memory:m1",
            "revision_sequence": 2, "owner_projection_sequence": 2,
            "scope": SCOPE, "delete_scope": "source",
        }, "delete-request")
        self.assertEqual(deleted["status"], "complete")
        stale = self.projection(operation_id="memory-stale-1", source_revision="rev-1",
                                revision_sequence=1, owner_sequence=3)
        _, response = self.service.project(stale, "stale-request")
        self.assertEqual(response["status"], "superseded")
        _, stale_delete = self.service.delete_source({
            "operation_id": "memory-delete-stale", "source_id": "memory:m1",
            "revision_sequence": 1, "owner_projection_sequence": 4,
            "scope": SCOPE, "delete_scope": "source",
        }, "stale-delete-request")
        self.assertEqual(stale_delete["status"], "superseded")
        manifest = self.service.manifest({"limit": ["100"]}, "manifest-request")
        source = next(item for item in manifest["items"] if item["source_id"] == "memory:m1")
        self.assertEqual(source["status"], "tombstoned")
        with self.assertRaises(GraphError) as error:
            self.service.traverse({"scope": SCOPE, "start_node_ids": ["node-a"]}, "query-4")
        self.assertEqual(error.exception.status, 404)

    def test_source_deletion_makes_cross_source_edges_untraversable(self):
        # memory owns the relationship, while knowledge independently supports
        # its target node. Deleting knowledge must not leave a path to an
        # unsupported node through memory's still-present edge support.
        self.service.project(self.projection(
            operation_id="knowledge-node-b", source_id="knowledge:k1",
            owner_sequence=1, nodes=[
                {"node_id": "node-b", "node_type": "project", "label": "FlossWare"}
            ], edges=[],
        ), "knowledge-project")
        self.service.project(self.projection(
            operation_id="memory-edge-a-b", source_id="memory:m1",
            owner_sequence=1, nodes=[
                {"node_id": "node-a", "node_type": "service", "label": "Search"}
            ], edges=[{
                "edge_id": "edge-a-b", "source_node_id": "node-a",
                "target_node_id": "node-b", "relationship_type": "uses", "directed": True,
            }],
        ), "memory-project")

        self.service.delete_source({
            "operation_id": "knowledge-delete-k1", "source_id": "knowledge:k1",
            "revision_sequence": 2, "owner_projection_sequence": 2,
            "scope": SCOPE, "delete_scope": "source",
        }, "knowledge-delete")

        result = self.service.traverse({
            "scope": SCOPE, "start_node_ids": ["node-a"], "direction": "outgoing",
        }, "after-delete")
        self.assertEqual(result["paths"], [])
        self.assertFalse(any("node-b" in path["node_ids"] for path in result["paths"]))

    def test_reprojection_removing_node_makes_cross_source_edges_untraversable(self):
        self.service.project(self.projection(
            operation_id="knowledge-node-b", source_id="knowledge:k1",
            owner_sequence=1, nodes=[
                {"node_id": "node-b", "node_type": "project", "label": "FlossWare"}
            ], edges=[],
        ), "knowledge-project")
        self.service.project(self.projection(
            operation_id="memory-edge-a-b", source_id="memory:m1",
            owner_sequence=1, nodes=[
                {"node_id": "node-a", "node_type": "service", "label": "Search"}
            ], edges=[{
                "edge_id": "edge-a-b", "source_node_id": "node-a",
                "target_node_id": "node-b", "relationship_type": "uses", "directed": True,
            }],
        ), "memory-project")

        self.service.project(self.projection(
            operation_id="knowledge-revision-2", source_id="knowledge:k1",
            source_revision="knowledge-rev-2", revision_sequence=2, owner_sequence=2,
            nodes=[], edges=[],
        ), "knowledge-reproject")

        result = self.service.traverse({
            "scope": SCOPE, "start_node_ids": ["node-a"], "direction": "outgoing",
        }, "after-reprojection")
        self.assertEqual(result["paths"], [])

    def test_owner_checkpoint_stays_not_ready_until_contiguous_journal_replay(self):
        later = self.projection(operation_id="memory-op-2", source_id="memory:m2",
                                owner_sequence=2, nodes=[], edges=[])
        self.service.project(later, "later")
        with self.assertRaises(GraphError) as error:
            self.service.checkpoint({"owner": "memory", "sealed_projection_sequence": 2}, "cp-1")
        self.assertEqual(error.exception.code, "graph_replay_incomplete")
        earlier = self.projection(operation_id="memory-op-1", source_id="memory:m1",
                                  owner_sequence=1, nodes=[], edges=[])
        self.service.project(earlier, "earlier")
        status, memory_cp = self.service.checkpoint(
            {"owner": "memory", "sealed_projection_sequence": 2}, "cp-2")
        self.assertEqual(status, 200)
        self.assertEqual(memory_cp["terminal_projection_sequence"], 2)
        self.service.checkpoint({"owner": "knowledge", "sealed_projection_sequence": 0}, "cp-3")
        self.assertTrue(self.service.manifest({"limit": ["10"]}, "manifest")["ready"])

    def test_projection_conflicts_and_missing_endpoints_are_rejected(self):
        self.service.project(self.projection(), "r1")
        conflict = self.projection(operation_id="memory-conflict", source_revision="different",
                                   revision_sequence=1, owner_sequence=2)
        with self.assertRaises(GraphError) as error:
            self.service.project(conflict, "r2")
        self.assertEqual(error.exception.code, "revision_conflict")
        missing = self.projection(operation_id="memory-missing", source_id="memory:m2",
                                  revision_sequence=1, owner_sequence=2,
                                  nodes=[{"node_id": "node-c", "node_type": "thing", "label": "C"}],
                                  edges=[{"edge_id": "bad-edge", "source_node_id": "node-c",
                                          "target_node_id": "not-there", "relationship_type": "uses",
                                          "directed": True}])
        with self.assertRaises(GraphError) as missing_error:
            self.service.project(missing, "r3")
        self.assertEqual(missing_error.exception.code, "missing_endpoint_node")

    def test_traversal_requires_exactly_one_start_selector(self):
        with self.assertRaises(GraphError):
            self.service.traverse({"scope": SCOPE}, "bad-1")
        with self.assertRaises(GraphError):
            self.service.traverse({"scope": SCOPE, "start_node_ids": ["a"],
                                   "entity_mentions": ["a"]}, "bad-2")


if __name__ == "__main__":
    unittest.main(verbosity=2)
