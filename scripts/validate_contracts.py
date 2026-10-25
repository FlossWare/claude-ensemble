#!/usr/bin/env python3
"""Static contract gate: JSON Schema validity, endpoint bindings, and JSON examples."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "docs" / "contracts" / "schemas"
DOC_DIRS = (ROOT / "docs",)
JSON_FENCE = re.compile(r"^```json\s*\n(.*?)^\`\`\`\s*$", re.MULTILINE | re.DOTALL)


def resolve_pointer(document: dict[str, Any], ref: str) -> Any:
    if not ref.startswith("#/"):
        raise ValueError(f"only local JSON pointers are permitted, got {ref!r}")
    current: Any = document
    for token in ref[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(token)]
        else:
            current = current[token]
    return current


def walk_refs(value: Any):
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str):
            yield ref
        for child in value.values():
            yield from walk_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_refs(child)


def main() -> int:
    errors: list[str] = []
    schemas: dict[Path, dict[str, Any]] = {}
    schema_files = sorted(SCHEMA_DIR.glob("*.schema.json"))
    if len(schema_files) != 17:
        errors.append(f"expected 17 service/profile schemas, found {len(schema_files)}")

    for path in schema_files:
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            schemas[path] = schema
        except Exception as exc:  # schema errors include useful path/message details
            errors.append(f"{path.relative_to(ROOT)}: invalid JSON Schema: {exc}")
            continue

        for ref in walk_refs(schema):
            try:
                resolve_pointer(schema, ref)
            except Exception as exc:
                errors.append(f"{path.relative_to(ROOT)}: unresolved $ref {ref!r}: {exc}")

        endpoints = schema.get("x-endpoints")
        if path.name != "index-profile.schema.json":
            if not isinstance(endpoints, dict) or not endpoints:
                errors.append(f"{path.relative_to(ROOT)}: missing non-empty x-endpoints")
            else:
                for endpoint, binding in endpoints.items():
                    if not isinstance(binding, dict):
                        errors.append(f"{path.name} {endpoint}: endpoint binding must be an object")
                        continue
                    for key in ("request", "response", "error_response"):
                        ref = binding.get(key)
                        if ref is not None:
                            try:
                                resolve_pointer(schema, ref)
                            except Exception as exc:
                                errors.append(f"{path.name} {endpoint}: invalid {key} {ref!r}: {exc}")
                    if not isinstance(binding.get("success_status"), int):
                        errors.append(f"{path.name} {endpoint}: missing integer success_status")
                    if not isinstance(binding.get("error_statuses"), list):
                        errors.append(f"{path.name} {endpoint}: missing error_statuses array")
                    callers = binding.get("x-callers")
                    if not isinstance(callers, list) or not callers or any(
                        not isinstance(caller, str) or not caller.strip() for caller in callers
                    ):
                        errors.append(f"{path.name} {endpoint}: x-callers must be a non-empty string array")
                    elif len(callers) != len(set(callers)):
                        errors.append(f"{path.name} {endpoint}: duplicate x-callers")

    example_count = 0
    for directory in DOC_DIRS:
        for path in sorted(directory.rglob("*.md")):
            try:
                content = path.read_text(encoding="utf-8")
            except OSError as exc:
                errors.append(f"{path.relative_to(ROOT)}: cannot read: {exc}")
                continue
            for index, match in enumerate(JSON_FENCE.finditer(content), start=1):
                example_count += 1
                try:
                    json.loads(match.group(1))
                except json.JSONDecodeError as exc:
                    errors.append(
                        f"{path.relative_to(ROOT)} JSON example {index}: invalid JSON "
                        f"at line {exc.lineno}, column {exc.colno}: {exc.msg}"
                    )

    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1
    print(
        f"OK: {len(schemas)} Draft 2020-12 schemas; local references and endpoint bindings valid; "
        f"{example_count} fenced JSON examples parse."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
