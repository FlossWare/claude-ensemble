#!/usr/bin/env python3
"""Static contract gate: schemas, endpoint bindings, JSON examples, and annotated example instances."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "docs" / "contracts" / "schemas"
FENCE = re.compile(r"^(?:`{3}|~{3})json\s*\n(.*?)^(?:`{3}|~{3})\s*$", re.MULTILINE | re.DOTALL)
EXAMPLE_SCHEMA = re.compile(r"^\s*<!--\s*schema-example:\s*([^\s]+)\s*-->\s*$", re.MULTILINE)
SERVICE_NAMES = {p.name.removesuffix(".schema.json") for p in SCHEMA_DIR.glob("*.schema.json")} - {"index-profile"}
EXTERNAL_CALLERS = {"client", "hook-adapter", "operator", "health-probe"}
SINK_SERVICES = {"index"}


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def parse_json(text: str) -> Any:
    return json.loads(text, object_pairs_hook=reject_duplicate_keys)


def resolve_pointer(document: Any, pointer: str) -> Any:
    if pointer in ("", "#"):
        return document
    if not pointer.startswith("#/"):
        raise ValueError(f"unsupported JSON pointer fragment {pointer!r}")
    current = document
    for token in pointer[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        current = current[int(token)] if isinstance(current, list) else current[token]
    return current


def resolve_ref(schema_path: Path, ref: str, schemas: dict[Path, dict[str, Any]]) -> Any:
    if ref.startswith("#"):
        target_path, fragment = schema_path, ref
    else:
        file_part, separator, fragment_part = ref.partition("#")
        if Path(file_part).name != file_part:
            raise ValueError(f"only schema-local or sibling-schema references are permitted, got {ref!r}")
        target_path = SCHEMA_DIR / file_part
        fragment = "#" + fragment_part if separator else "#"
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

    for path in schema_files:
        try:
            schemas[path] = parse_json(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: cannot parse schema JSON: {exc}")

    global_routes: dict[tuple[str, str], str] = {}
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
        if path.name == "index-profile.schema.json":
            if endpoints is not None:
                errors.append(f"{path.name}: profile schema must not declare x-endpoints")
            continue
        if not isinstance(endpoints, dict) or not endpoints:
            errors.append(f"{path.relative_to(ROOT)}: missing non-empty x-endpoints")
            continue

        service = path.name.removesuffix(".schema.json")
        for endpoint, binding in endpoints.items():
            where = f"{path.name} {endpoint}"
            if not isinstance(binding, dict):
                errors.append(f"{where}: endpoint binding must be an object")
                continue
            parts = endpoint.split(" ", 1)
            if len(parts) != 2 or parts[0] not in {"GET", "POST", "PUT", "PATCH", "DELETE"} or not parts[1].startswith("/"):
                errors.append(f"{where}: endpoint key must be 'METHOD /absolute/path'")
            else:
                method, route = parts
                normalized_route = re.sub(r"\{[^{}]+\}", "{}", route)
                key = (method, normalized_route)
                previous = global_routes.get(key)
                if previous:
                    errors.append(f"{where}: duplicate route {method} {normalized_route} also declared by {previous}")
                else:
                    global_routes[key] = where

            method = parts[0] if len(parts) == 2 else ""
            for key in ("response", "error_response"):
                ref = binding.get(key)
                if not isinstance(ref, str) or not ref:
                    errors.append(f"{where}: required {key} binding is missing")
                else:
                    try:
                        resolve_ref(path, ref, schemas)
                    except Exception as exc:
                        errors.append(f"{where}: invalid {key} {ref!r}: {exc}")
            if method in {"POST", "PUT", "PATCH", "DELETE"}:
                ref = binding.get("request")
                if not isinstance(ref, str) or not ref:
                    errors.append(f"{where}: mutating endpoint requires request binding")
                else:
                    try:
                        resolve_ref(path, ref, schemas)
                    except Exception as exc:
                        errors.append(f"{where}: invalid request {ref!r}: {exc}")
            elif binding.get("request") is not None:
                try:
                    resolve_ref(path, binding["request"], schemas)
                except Exception as exc:
                    errors.append(f"{where}: invalid request {binding['request']!r}: {exc}")

            status = binding.get("success_status")
            if not isinstance(status, int) or isinstance(status, bool) or not 200 <= status <= 299:
                errors.append(f"{where}: success_status must be a 2xx integer")
            error_statuses = binding.get("error_statuses")
            if not isinstance(error_statuses, list) or not error_statuses:
                errors.append(f"{where}: error_statuses must be a non-empty array")
            elif any(not isinstance(s, int) or isinstance(s, bool) or not 400 <= s <= 599 for s in error_statuses):
                errors.append(f"{where}: error_statuses must contain only 4xx/5xx integers")
            elif len(error_statuses) != len(set(error_statuses)):
                errors.append(f"{where}: duplicate error status")

            callers = binding.get("x-callers")
            if not isinstance(callers, list) or not callers or any(not isinstance(c, str) or not c.strip() for c in callers):
                errors.append(f"{where}: x-callers must be a non-empty string array")
            elif len(callers) != len(set(callers)):
                errors.append(f"{where}: duplicate x-callers")
            else:
                for caller in callers:
                    if caller not in SERVICE_NAMES and caller not in EXTERNAL_CALLERS:
                        errors.append(f"{where}: unknown caller {caller!r}; use a declared service or approved external actor")
                    if caller == service:
                        errors.append(f"{where}: service cannot call its own REST endpoint")
                    if caller in SINK_SERVICES:
                        errors.append(f"{where}: sink service {caller!r} cannot call another logical service")

    example_count = 0
    annotated_count = 0
    for path in sorted((ROOT / "docs").rglob("*.md")):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{path.relative_to(ROOT)}: cannot read: {exc}")
            continue
        for index, match in enumerate(FENCE.finditer(content), start=1):
            example_count += 1
            try:
                instance = parse_json(match.group(1))
            except (json.JSONDecodeError, ValueError) as exc:
                errors.append(f"{path.relative_to(ROOT)} JSON example {index}: invalid JSON: {exc}")
                continue
            prefix = content[:match.start()]
            annotations = list(EXAMPLE_SCHEMA.finditer(prefix))
            annotation = annotations[-1] if annotations else None
            if annotation and content[annotation.end():match.start()].strip():
                annotation = None
            if annotation:
                annotated_count += 1
                target = annotation.group(1)
                schema_file, sep, fragment = target.partition("#")
                schema_path = (ROOT / schema_file).resolve()
                try:
                    schema_path.relative_to(ROOT.resolve())
                    schema = schemas.get(schema_path)
                    if schema is None:
                        raise ValueError(f"schema file is not in the loaded schema registry: {schema_file}")
                    definition = resolve_pointer(schema, "#" + fragment if sep else "#")
                    Draft202012Validator(definition).validate(instance)
                except Exception as exc:
                    errors.append(f"{path.relative_to(ROOT)} JSON example {index} against {target}: {exc}")

    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1
    print(
        f"OK: {len(schemas)} Draft 2020-12 schemas; references and endpoint bindings valid; "
        f"{len(global_routes)} unique method/path routes; {example_count} JSON examples parsed with duplicate-key rejection; "
        f"{annotated_count} examples validated against explicitly annotated schemas. Unannotated examples are parse-checked only."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
