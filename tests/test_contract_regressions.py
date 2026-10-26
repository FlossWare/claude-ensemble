#!/usr/bin/env python3
"""Regression tests for static contract gates and v1 RRF golden arithmetic."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_contracts.py"
GRAPH_PATH = ROOT / "scripts" / "check_service_call_graph.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_contracts", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class ContractGateTests(unittest.TestCase):
    def test_repository_static_gates_pass(self):
        for script in (VALIDATOR_PATH, GRAPH_PATH):
            with self.subTest(script=script.name):
                result = subprocess.run([sys.executable, str(script)], cwd=ROOT, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_duplicate_json_keys_are_rejected(self):
        validator = load_validator()
        with self.assertRaisesRegex(ValueError, "duplicate JSON object key"):
            validator.parse_json('{"metric":"cosine","metric":"euclidean"}')

    def _temporary_contract_tree(self):
        tmp = tempfile.TemporaryDirectory()
        base = Path(tmp.name)
        shutil.copytree(ROOT / "docs", base / "docs")
        (base / "scripts").mkdir()
        shutil.copy2(VALIDATOR_PATH, base / "scripts" / VALIDATOR_PATH.name)
        shutil.copy2(GRAPH_PATH, base / "scripts" / GRAPH_PATH.name)
        return tmp, base

    def test_schema_invalid_annotated_example_fails(self):
        tmp, base = self._temporary_contract_tree()
        self.addCleanup(tmp.cleanup)
        path = base / "docs" / "contracts" / "VECTOR-RETRIEVAL.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn('"metric": "cosine"', text)
        path.write_text(text.replace('"metric": "cosine"', '"metric": "not-a-metric"', 1), encoding="utf-8")
        result = subprocess.run([sys.executable, str(base / "scripts" / VALIDATOR_PATH.name)], cwd=base, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("not-a-metric", result.stderr)

    def test_unknown_caller_fails_call_graph_gate(self):
        tmp, base = self._temporary_contract_tree()
        self.addCleanup(tmp.cleanup)
        path = base / "docs" / "contracts" / "schemas" / "chunking.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        endpoint = next(iter(schema["x-endpoints"].values()))
        endpoint["x-callers"].append("memroy")
        path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
        result = subprocess.run([sys.executable, str(base / "scripts" / GRAPH_PATH.name)], cwd=base, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("unknown caller", result.stderr)

    def test_index_cannot_be_declared_as_a_caller(self):
        tmp, base = self._temporary_contract_tree()
        self.addCleanup(tmp.cleanup)
        path = base / "docs" / "contracts" / "schemas" / "chunking.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        endpoint = next(iter(schema["x-endpoints"].values()))
        endpoint["x-callers"].append("index")
        path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
        result = subprocess.run([sys.executable, str(base / "scripts" / GRAPH_PATH.name)], cwd=base, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("sink service", result.stderr)

    def test_traceability_acceptance_ids_are_complete(self):
        acceptance = (ROOT / "docs" / "ARCHITECTURE-REVIEW-ACCEPTANCE.md").read_text(encoding="utf-8")
        traceability = (ROOT / "docs" / "TRACEABILITY.md").read_text(encoding="utf-8")
        defined = set(__import__("re").findall(r"^### (AT-[A-Z0-9-]+):", acceptance, __import__("re").MULTILINE))
        referenced = set(__import__("re").findall(r"\\bAT-[A-Z0-9-]+\\b", traceability))
        self.assertEqual(len(defined), 59, "update the expected scenario count when acceptance scenarios change")
        self.assertEqual(referenced - defined, set(), "traceability contains undefined AT-* references")
        self.assertEqual(defined - referenced, set(), "acceptance scenarios missing from traceability")

    def test_duplicate_method_path_route_fails(self):
        tmp, base = self._temporary_contract_tree()
        self.addCleanup(tmp.cleanup)
        path = base / "docs" / "contracts" / "schemas" / "chunking.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        original = next(iter(schema["x-endpoints"]))
        schema["x-endpoints"]["GET /api/v1/gateway/health"] = schema["x-endpoints"].pop(original)
        path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
        result = subprocess.run([sys.executable, str(base / "scripts" / VALIDATOR_PATH.name)], cwd=base, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("duplicate route", result.stderr)

    def test_rrf_integer_golden_vectors(self):
        def contribution(rank: int) -> int:
            return 1_000_000_000_000 // (60 + rank)

        score_324 = contribution(3) + contribution(24)
        score_1212 = contribution(12) + contribution(12)
        self.assertEqual(score_324, 27_777_777_777)
        self.assertEqual(score_1212, 27_777_777_776)
        self.assertGreater(score_324, score_1212)
        scores = [
            contribution(3) + contribution(80),
            contribution(80) + contribution(3),
            contribution(24) + contribution(30),
            contribution(30) + contribution(24),
        ]
        self.assertEqual(scores, [23_015_873_015] * 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
