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
WORKFLOW_MANIFEST = SCHEMA_DIR.parent / "service-call-workflows.json"
# Index is a sink: it must never initiate a call to another logical service.
SINK_SERVICES = {"index"}


def main() -> int:
    errors: list[str] = []
    graph: dict[str, set[str]] = {name: set() for name in SERVICE_NAMES}
    declared_edges: set[tuple[str, str]] = set()
    workflow_edges: set[tuple[str, str]] = set()
    try:
        manifest = json.loads(WORKFLOW_MANIFEST.read_text(encoding="utf-8"))
        if manifest.get("version") != 1 or not isinstance(manifest.get("edges"), list):
            raise ValueError("manifest must have version 1 and an edges array")
        for index, item in enumerate(manifest["edges"], start=1):
            if not isinstance(item, dict):
                errors.append(f"workflow manifest edge {index}: must be an object")
                continue
            caller, callee = item.get("caller"), item.get("callee")
            if caller not in SERVICE_NAMES or callee not in SERVICE_NAMES:
                errors.append(f"workflow manifest edge {index}: unknown service edge {caller!r} -> {callee!r}")
                continue
            if not isinstance(item.get("workflow"), str) or not item["workflow"].strip():
                errors.append(f"workflow manifest edge {index}: workflow rationale is required")
            if not isinstance(item.get("contracts"), list) or not item["contracts"]:
                errors.append(f"workflow manifest edge {index}: contract references are required")
            if not isinstance(item.get("acceptance_test"), str) or not item["acceptance_test"].startswith("AT-"):
                errors.append(f"workflow manifest edge {index}: acceptance_test must name an AT-* scenario")
            edge = (caller, callee)
            if edge in workflow_edges:
                errors.append(f"workflow manifest: duplicate edge {caller} -> {callee}")
            workflow_edges.add(edge)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"cannot load workflow manifest {WORKFLOW_MANIFEST}: {exc}")
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
                if edge not in workflow_edges:
                    errors.append(f"{where}: undeclared workflow edge {caller} -> {service}")
                graph[caller].add(service)

    for edge in sorted(workflow_edges - declared_edges):
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
