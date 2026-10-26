"""Deterministic, dependency-free v1 chunking implementation."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable

MAX_CONTENT_BYTES = 262_144
MAX_UNITS = 65_536
MAX_OVERLAP = 8_192
MAX_CHUNKS = 256


class ChunkingError(ValueError):
    """A request cannot be processed under the chunking contract."""

    def __init__(self, code: str, message: str, *, status: int = 422, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = details or {}


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
            raise ChunkingError("invalid_request", "policy must be an object", status=400)
        allowed = {"profile", "profile_version", "max_units", "overlap_units", "unit"}
        if set(value) != allowed:
            raise ChunkingError("invalid_request", "policy must contain exactly the documented fields", status=400)
        policy = cls(
            profile=value["profile"],
            profile_version=value["profile_version"],
            max_units=value["max_units"],
            overlap_units=value["overlap_units"],
            unit=value["unit"],
        )
        if not isinstance(policy.profile, str) or not policy.profile or len(policy.profile) > 128:
            raise ChunkingError("invalid_parameter", "policy.profile must be a non-empty string of at most 128 characters", status=400)
        if not isinstance(policy.profile_version, str) or not policy.profile_version or len(policy.profile_version) > 64:
            raise ChunkingError("invalid_parameter", "policy.profile_version must be a non-empty string of at most 64 characters", status=400)
        if type(policy.max_units) is not int or not 1 <= policy.max_units <= MAX_UNITS:
            raise ChunkingError("invalid_parameter", "policy.max_units must be between 1 and 65536", status=400)
        if type(policy.overlap_units) is not int or not 0 <= policy.overlap_units <= min(MAX_OVERLAP, policy.max_units - 1):
            raise ChunkingError("invalid_parameter", "policy.overlap_units must be between zero and min(8192, max_units - 1)", status=400)
        if policy.unit != "unicode_code_points":
            raise ChunkingError("unsupported_policy", "policy.unit must be unicode_code_points")
        return policy


# Explicit default used only when a caller omits the policy field.
DEFAULT_POLICY = Policy(
    profile="markdown-default",
    profile_version="0.1",
    max_units=1200,
    overlap_units=120,
    unit="unicode_code_points",
)


def validate_index_profile(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"name", "version", "digest"}:
        raise ChunkingError("invalid_request", "index_profile must contain name, version, and digest", status=400)
    if not isinstance(value["name"], str) or not 1 <= len(value["name"]) <= 128:
        raise ChunkingError("invalid_parameter", "index_profile.name is invalid", status=400)
    if not isinstance(value["version"], str) or not 1 <= len(value["version"]) <= 64:
        raise ChunkingError("invalid_parameter", "index_profile.version is invalid", status=400)
    digest = value["digest"]
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in digest):
        raise ChunkingError("invalid_parameter", "index_profile.digest must be a 64-character hexadecimal digest", status=400)
    return {"name": value["name"], "version": value["version"], "digest": digest}


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _choose_end(text: str, start: int, limit: int) -> int:
    """Prefer a newline/space boundary near the limit without creating empty chunks."""
    hard_end = min(len(text), start + limit)
    if hard_end == len(text):
        return hard_end
    floor = start + max(1, limit // 2)
    boundary = max(text.rfind("\n", floor, hard_end), text.rfind(" ", floor, hard_end))
    return boundary + 1 if boundary >= floor else hard_end


def _heading_path(text: str, offset: int, deadline_check: Callable[[], None] | None = None) -> list[str]:
    """Return ancestry from complete ATX heading lines preceding offset."""
    import re

    ancestry: list[tuple[int, str]] = []
    fence_char: str | None = None
    fence_length = 0
    position = 0
    for line_number, raw_line in enumerate(text.splitlines(keepends=True)):
        if deadline_check is not None and line_number % 64 == 0:
            deadline_check()
        line_end = position + len(raw_line)
        # A chunk boundary inside a heading line must never turn its prefix into
        # fabricated provenance.
        if line_end > offset:
            break
        line = raw_line.rstrip("\r\n")
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if indent <= 3 and stripped and stripped[0] in "`~":
            marker = stripped[0]
            run_length = len(stripped) - len(stripped.lstrip(marker))
            if run_length >= 3:
                if fence_char is None and (marker == "`" or "`" not in stripped):
                    fence_char, fence_length = marker, run_length
                    position = line_end
                    continue
                if fence_char == marker and run_length >= fence_length and not stripped[run_length:].strip():
                    fence_char, fence_length = None, 0
                    position = line_end
                    continue
        if fence_char is None and indent <= 3:
            match = re.match(r"^ {0,3}(#{1,6})(?:[ \t]+|$)(.*?)\s*$", line)
            if match:
                level = len(match.group(1))
                heading = match.group(2)
                heading = re.sub(r"[ \t]+#+[ \t]*$", "", heading).strip()
                # A recognized heading always closes the previous section at
                # its level, even when its label is empty or too long to expose as
                # provenance. Otherwise later chunks inherit a stale, false heading.
                ancestry = [(depth, value) for depth, value in ancestry if depth < level]
                # The schema caps heading provenance at 1024 characters. Omit
                # unsupported labels rather than returning a schema-invalid claim.
                if heading and len(heading) <= 1024:
                    ancestry.append((level, heading))
        position = line_end
    return [heading for _, heading in ancestry[-64:]]


def chunk_spans(content: str, policy: Policy, *, max_chunks: int = MAX_CHUNKS,
                deadline_check: Callable[[], None] | None = None) -> list[tuple[int, int]]:
    """Compute bounded source spans without constructing chunk response objects."""
    spans: list[tuple[int, int]] = []
    start = 0
    while start < len(content):
        if deadline_check is not None:
            deadline_check()
        end = _choose_end(content, start, policy.max_units)
        if end <= start:
            raise ChunkingError("internal_error", "chunker failed to advance", status=500)
        spans.append((start, end))
        if len(spans) > max_chunks:
            raise ChunkingError("source_too_large", f"source requires more than {max_chunks} chunks under the selected policy")
        if end == len(content):
            break
        effective_overlap = min(policy.overlap_units, end - start - 1)
        start = end - effective_overlap
    return spans


def chunk_document(*, source_id: str, revision: str, revision_sequence: int,
                   content: str, index_profile: dict[str, str], policy: Policy,
                   include_text: bool = True, include_line_spans: bool = True,
                   deadline_check: Callable[[], None] | None = None) -> dict[str, Any]:
    """Return deterministic chunks with code-point offsets into the original string."""
    if not isinstance(content, str) or not content:
        raise ChunkingError("invalid_request", "source.content must be a non-empty string", status=400)
    if len(content.encode("utf-8")) > MAX_CONTENT_BYTES:
        raise ChunkingError("source_too_large", "source content exceeds 262144 UTF-8 bytes")
    if not isinstance(source_id, str) or not 8 <= len(source_id) <= 138:
        raise ChunkingError("invalid_parameter", "source.source_id is invalid", status=400)
    if not (source_id.startswith("memory:") or source_id.startswith("knowledge:")):
        raise ChunkingError("invalid_parameter", "source.source_id must use a memory: or knowledge: owner prefix", status=400)
    if not isinstance(revision, str) or not 1 <= len(revision) <= 256:
        raise ChunkingError("invalid_parameter", "source.revision is invalid", status=400)
    if type(revision_sequence) is not int or not 1 <= revision_sequence <= 9_007_199_254_740_991:
        raise ChunkingError("invalid_parameter", "source.revision_sequence must be a positive safe integer", status=400)
    profile = validate_index_profile(index_profile)
    if type(include_text) is not bool or type(include_line_spans) is not bool:
        raise ChunkingError("invalid_parameter", "options.include_text and options.include_line_spans must be booleans", status=400)

    spans = chunk_spans(content, policy, deadline_check=deadline_check)

    chunks: list[dict[str, Any]] = []
    for ordinal, (start, end) in enumerate(spans):
        if deadline_check is not None:
            deadline_check()
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
            "heading_path": _heading_path(content, start, deadline_check) if policy.profile == "markdown-default" else [],
            "metadata": {},
        }
        if include_text:
            chunk["text"] = text
        if include_line_spans:
            chunk["start_line"] = _line_number(content, start)
            chunk["end_line"] = _line_number(content, max(start, end - 1))
        chunks.append(chunk)

    return {
        "index_profile": profile,
        "source_id": source_id,
        "source_revision": revision,
        "revision_sequence": revision_sequence,
        "chunker": {"profile": policy.profile, "version": policy.profile_version},
        "chunking_profile": {"profile": policy.profile, "version": policy.profile_version},
        "chunks": chunks,
    }
