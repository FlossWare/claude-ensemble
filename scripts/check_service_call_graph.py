#!/usr/bin/env python3
"""Validate declared REST caller edges against the v1 workflow allowlist."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "docs" / "contracts" / "schemas"
EXTERNAL_CALLERS = {"client", "hook-adapter", "operator", "health-probe"}
SERVICE_NAMES = {
    path.name.removesuffix(".schema.json")
    for path in SCHEMA_DIR.glob("*.schema.json")
    if path.name != "index-profile.schema.json"
}
# Each service-to-service edge must correspond to a documented v1 workflow.
# Changes to this allowlist require a matching workflow/contract and acceptance test.
WORKFLOW_EDGES = {
    ("embedding", "index"),
    ("gateway", "entity-extraction"),
    ("gateway", "graph"),
    ("gateway", "index"),
    ("gateway", "intent-classification"),
    ("gateway", "knowledge"),
    ("gateway", "learning"),
    ("gateway", "lexical-retrieval"),
    ("gateway", "memory"),
    ("gateway", "ranking"),
    ("gateway", "reranking"),
    ("gateway", "thompson"),
    ("gateway", "vector-retrieval"),
    ("knowledge", "chunking"),
    ("knowledge", "embedding"),
    ("knowledge", "graph"),
    ("knowledge", "index"),
    ("knowledge", "tokenization"),
    ("learning", "thompson"),
    ("lexical-retrieval", "index"),
    ("lexical-retrieval", "tokenization"),
    ("memory", "chunking"),
    ("memory", "embedding"),
    ("memory", "graph"),
    ("memory", "index"),
    ("memory", "tokenization"),
    ("tokenization", "index"),
    ("vector-retrieval", "embedding"),
    ("vector-retrieval", "index"),
}
# Index is a sink: it must never initiate a call to another logical service.
SINK_SERVICES = {"index"}


def main() -> int:
    errors: list[str] = []
    graph: dict[str, set[str]] = {name: set() for name in SERVICE_NAMES}
    declared_edges: set[tuple[str, str]] = set()
    schema_files = sorted(SCHEMA_DIR.glob("*.schema.json"))
    if len(schema_files) != 17:
        errors.append(f"expected 17 schemas, found {len(schema_files)}")

    for path in schema_files:
        service = path.name.removesuffix(".schema.json")
        if service == "index-profile":
            continue
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: cannot parse JSON: {exc}")
            continue
        endpoints = schema.get("x-endpoints")
        if not isinstance(endpoints, dict) or not endpoints:
            errors.append(f"{path.name}: missing non-empty x-endpoints map")
            continue
        for endpoint, contract in endpoints.items():
            where = f"{path.name} {endpoint}"
            callers = contract.get("x-callers") if isinstance(contract, dict) else None
            if not isinstance(callers, list) or not callers or any(
                not isinstance(caller, str) or not caller.strip() for caller in callers
            ):
                errors.append(f"{where}: x-callers must be a non-empty string array")
                continue
            if len(callers) != len(set(callers)):
                errors.append(f"{where}: duplicate x-callers entry")
            for caller in callers:
                if caller in EXTERNAL_CALLERS:
                    continue
                if caller not in SERVICE_NAMES:
                    errors.append(f"{where}: unknown caller {caller!r}; not a service or approved external actor")
                    continue
                if caller == service:
                    errors.append(f"{where}: service cannot call its own REST endpoint")
                    continue
                if caller in SINK_SERVICES:
                    errors.append(f"{where}: sink service {caller!r} cannot call another logical service")
                edge = (caller, service)
                declared_edges.add(edge)
                if edge not in WORKFLOW_EDGES:
                    errors.append(f"{where}: undeclared workflow edge {caller} -> {service}")
                graph[caller].add(service)

    for edge in sorted(WORKFLOW_EDGES - declared_edges):
        errors.append(f"workflow allowlist edge {edge[0]} -> {edge[1]} is not represented by any endpoint x-callers")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, stack: list[str]) -> None:
        if node in visiting:
            start = stack.index(node) if node in stack else 0
            errors.append("service-call cycle: " + " -> ".join(stack[start:] + [node]))
            return
        if node in visited:
            return
        visiting.add(node)
        stack.append(node)
        for child in sorted(graph.get(node, set())):
            visit(child, stack)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for service in sorted(graph):
        if service not in visited:
            visit(service, [])

    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1
    print(
        f"OK: {len(SERVICE_NAMES)} service schemas; {len(declared_edges)} declared service-call edges "
        "match the workflow allowlist; Index is a sink; no cycles."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
