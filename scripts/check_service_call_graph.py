#!/usr/bin/env python3
"""Validate the declarative REST caller graph in contract JSON Schemas."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "docs" / "contracts" / "schemas"
EXTERNAL_CALLERS = {"client", "hook-adapter", "operator", "health-probe"}
FORBIDDEN_CALLS = {
    ("index", "memory"),
    ("index", "knowledge"),
    ("graph", "memory"),
    ("graph", "knowledge"),
    ("thompson", "learning"),
}


def main() -> int:
    errors: list[str] = []
    graph: dict[str, set[str]] = {}
    schema_files = sorted(SCHEMA_DIR.glob("*.schema.json"))
    if not schema_files:
        print(f"ERROR: no schemas found in {SCHEMA_DIR}", file=sys.stderr)
        return 2

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
            callers = contract.get("x-callers") if isinstance(contract, dict) else None
            if not isinstance(callers, list) or not callers or any(
                not isinstance(caller, str) or not caller.strip() for caller in callers
            ):
                errors.append(f"{path.name} {endpoint}: x-callers must be a non-empty string array")
                continue
            if len(callers) != len(set(callers)):
                errors.append(f"{path.name} {endpoint}: duplicate x-callers entry")
            for caller in callers:
                if caller == service:
                    errors.append(f"{path.name} {endpoint}: service cannot call its own REST endpoint")
                if (caller, service) in FORBIDDEN_CALLS:
                    errors.append(f"{path.name} {endpoint}: forbidden call edge {caller} -> {service}")
                if caller not in EXTERNAL_CALLERS:
                    graph.setdefault(caller, set()).add(service)
                    graph.setdefault(service, set())

    # DFS cycle detection over service-to-service edges. External actors are
    # intentionally excluded because they do not participate in service cycles.
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
    edge_count = sum(len(children) for children in graph.values())
    print(
        f"OK: {len(schema_files) - 1} service schemas; all endpoints declare x-callers; "
        f"{edge_count} service call edges; no forbidden edges or cycles."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
