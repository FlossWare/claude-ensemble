"""Deterministic, dependency-free v1 chunking implementation."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

MAX_CONTENT_BYTES = 262_144
MAX_UNITS = 65_536
MAX_OVERLAP = 8_192


class ChunkingError(ValueError):
    """A request cannot be processed under the chunking contract."""


@dataclass(frozen=True)
class Policy:
    profile: str
    profile_version: str
    max_units: int
    overlap_units: int
    unit: str = "unicode_code_points"

    @classmethod
    def from_dict(cls, value: Any) -> "Policy":
        if not isinstance(value, dict):
            raise ChunkingError("policy must be an object")
        try:
            policy = cls(
                profile=value["profile"],
                profile_version=value["profile_version"],
                max_units=value["max_units"],
                overlap_units=value["overlap_units"],
                unit=value["unit"],
            )
        except (KeyError, TypeError) as exc:
            raise ChunkingError("policy is missing required fields") from exc
        if not isinstance(policy.profile, str) or not policy.profile or len(policy.profile) > 128:
            raise ChunkingError("invalid policy profile")
        if not isinstance(policy.profile_version, str) or not policy.profile_version or len(policy.profile_version) > 64:
            raise ChunkingError("invalid policy profile_version")
        if type(policy.max_units) is not int or not 1 <= policy.max_units <= MAX_UNITS:
            raise ChunkingError("max_units must be between 1 and 65536")
        if type(policy.overlap_units) is not int or not 0 <= policy.overlap_units <= min(MAX_OVERLAP, policy.max_units - 1):
            raise ChunkingError("overlap_units must be non-negative, at most 8192, and less than max_units")
        if policy.unit != "unicode_code_points":
            raise ChunkingError("unit must be unicode_code_points")
        return policy


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _choose_end(text: str, start: int, limit: int) -> int:
    """Prefer a newline/space boundary near the limit without creating empty chunks."""
    hard_end = min(len(text), start + limit)
    if hard_end == len(text):
        return hard_end
    floor = start + max(1, limit // 2)
    candidates = [text.rfind("\n", floor, hard_end), text.rfind(" ", floor, hard_end)]
    boundary = max(candidates)
    return boundary + 1 if boundary >= floor else hard_end


def chunk_document(*, source_id: str, revision: str, revision_sequence: int,
                   content: str, index_profile: dict[str, str], policy: Policy,
                   include_text: bool = True, include_line_spans: bool = True) -> dict[str, Any]:
    """Return deterministic chunks with code-point offsets into the original string."""
    if not isinstance(content, str):
        raise ChunkingError("source.content must be a string")
    if len(content.encode("utf-8")) > MAX_CONTENT_BYTES:
        raise ChunkingError("source content exceeds 262144 UTF-8 bytes")
    if not isinstance(source_id, str) or not source_id:
        raise ChunkingError("source.source_id is required")
    if not isinstance(revision, str) or not revision:
        raise ChunkingError("source.revision is required")
    if type(revision_sequence) is not int or revision_sequence < 1:
        raise ChunkingError("source.revision_sequence must be a positive integer")
    if not isinstance(index_profile, dict) or not all(isinstance(index_profile.get(k), str) and index_profile[k] for k in ("name", "version", "digest")):
        raise ChunkingError("index_profile must contain name, version, and digest")
    if len(index_profile["digest"]) != 64 or any(c not in "0123456789abcdefABCDEF" for c in index_profile["digest"]):
        raise ChunkingError("index_profile.digest must be a 64-character hexadecimal digest")

    spans: list[tuple[int, int]] = []
    start = 0
    while start < len(content):
        end = _choose_end(content, start, policy.max_units)
        if end <= start:
            raise ChunkingError("chunker failed to advance")
        spans.append((start, end))
        if end == len(content):
            break
        start = max(start + 1, end - policy.overlap_units)

    chunks: list[dict[str, Any]] = []
    for ordinal, (start, end) in enumerate(spans):
        text = content[start:end]
        identity = json.dumps({
            "source_id": source_id, "revision": revision,
            "revision_sequence": revision_sequence, "profile": policy.profile,
            "profile_version": policy.profile_version, "ordinal": ordinal,
            "start": start, "end": end, "text": text,
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        chunk: dict[str, Any] = {
            "chunk_id": "chk_" + hashlib.sha256(identity).hexdigest()[:32],
            "ordinal": ordinal,
            "start_offset": start,
            "end_offset": end,
            "heading_path": [],
            "metadata": {},
        }
        if include_text:
            chunk["text"] = text
        if include_line_spans:
            chunk["start_line"] = _line_number(content, start)
            chunk["end_line"] = _line_number(content, max(start, end - 1))
        # Preserve Markdown heading context without claiming parser-grade AST semantics.
        heading_path: list[str] = []
        for line in content[:start].splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#") and len(stripped) > 1 and stripped[1] == " ":
                level = len(stripped) - len(stripped.lstrip("#"))
                heading = stripped[level:].strip()
                heading_path = heading_path[:level - 1] + [heading]
        if heading_path:
            chunk["heading_path"] = heading_path
        chunks.append(chunk)

    return {
        "index_profile": dict(index_profile),
        "source_id": source_id,
        "source_revision": revision,
        "revision_sequence": revision_sequence,
        "chunker": {"profile": policy.profile, "version": policy.profile_version},
        "chunking_profile": {"profile": policy.profile, "version": policy.profile_version},
        "chunks": chunks,
    }
