#!/usr/bin/env python3
"""Static contract gate: JSON Schema validity, references, endpoint bindings, and JSON examples."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "docs" / "contracts" / "schemas"
JSON_FENCE = re.compile(r"^\x60{3}json\s*\n(.*?)^\x60{3}\s*$", re.MULTILINE | re.DOTALL)


def resolve_pointer(document: Any, pointer: str) -> Any:
    if pointer in ("", "#"):
        return document
    if not pointer.startswith("#/"):
        raise ValueError(f"unsupported JSON pointer fragment {pointer!r}")
    current = document
    for token in pointer[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(token)]
        else:
            current = current[token]
    return current


def resolve_ref(schema_path: Path, ref: str, schemas: dict[Path, dict[str, Any]]) -> Any:
    if ref.startswith("#"):
        target_path = schema_path
        fragment = ref
    else:
        file_part, separator, fragment_part = ref.partition("#")
        if not separator or Path(file_part).name != file_part:
            raise ValueError(f"only schema-local or sibling-schema references are permitted, got {ref!r}")
        target_path = SCHEMA_DIR / file_part
        fragment = "#" + fragment_part
    target = schemas.get(target_path)
    if target is None:
        raise ValueError(f"referenced schema does not exist: {target_path.name}")
    return resolve_pointer(target, fragment)


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

    # Load the complete registry first so sibling-schema references resolve
    # independently of filename ordering.
    for path in schema_files:
        try:
            schemas[path] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: cannot parse schema JSON: {exc}")

    for path, schema in schemas.items():
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:
            errors.append(f"{path.relative_to(ROOT)}: invalid Draft 2020-12 schema: {exc}")
            continue

        for ref in walk_refs(schema):
            try:
                resolve_ref(path, ref, schemas)
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
                                resolve_ref(path, ref, schemas)
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
    for path in sorted((ROOT / "docs").rglob("*.md")):
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
        f"OK: {len(schemas)} Draft 2020-12 schemas; local and sibling references plus endpoint bindings valid; "
        f"{example_count} fenced JSON examples parse."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
