"""Deterministic, dependency-free lexical tokenization for CE v1."""
from __future__ import annotations

import unicodedata
import re
from typing import Any

NORMALIZATION_VERSION = "0.1"
MAX_TEXT_BYTES = 262_144
MAX_TOKENS = 512
_TOKEN_RE = re.compile(
    r"""(?P<path>(?:[\w.@+~-]+[/\\])+[\w.@+~-]+)|"""
    r"""(?P<identifier>(?=[\w$]*[A-Za-z_\u0080-\U0010ffff])(?=[\w$]*[A-Z])(?=[\w$]*[a-z])[\w$]+)|"""
    r"""(?P<number>\d+(?:[.,]\d+)*)|"""
    r"""(?P<word>[^\W\d_]+)|"""
    r"""(?P<punctuation>[^\w\s])""",
    re.UNICODE,
)


class TokenizationError(ValueError):
    """A lexical tokenization request cannot be processed."""

    def __init__(self, code: str, message: str, *, status: int = 422):
        super().__init__(message)
        self.code = code
        self.status = status


def _bounded_string(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str) or len(value) > maximum:
        raise TokenizationError("invalid_parameter", f"{field} must be a string of at most {maximum} characters", status=400)
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise TokenizationError("invalid_parameter", f"{field} contains invalid Unicode", status=400) from exc
    if len(encoded) > MAX_TEXT_BYTES:
        raise TokenizationError("source_too_large", f"{field} exceeds the UTF-8 byte limit")
    return value


def tokenize(text: str, *, preserve_identifiers: bool = True,
             include_offsets: bool = True,
             include_normalized_terms: bool = True) -> list[dict[str, Any]]:
    """Tokenize text deterministically; offsets are Unicode code-point spans."""
    text = _bounded_string(text, "text", MAX_TEXT_BYTES)
    for name, value in (
        ("preserve_identifiers", preserve_identifiers),
        ("include_offsets", include_offsets),
        ("include_normalized_terms", include_normalized_terms),
    ):
        if type(value) is not bool:
            raise TokenizationError("invalid_parameter", f"options.{name} must be a boolean", status=400)

    result: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int, str]] = set()
    for match in _TOKEN_RE.finditer(text):
        surface = match.group(0)
        kind = match.lastgroup or "other"
        if kind == "identifier" and not preserve_identifiers:
            kind = "word"
        if kind == "punctuation" and surface.isspace():
            continue

        candidates: list[str] = []
        normalized = unicodedata.normalize("NFKC", surface).casefold()
        if kind in {"path", "identifier"} and preserve_identifiers:
            candidates.append(surface)
            if include_normalized_terms and normalized != surface:
                candidates.append(normalized)
        else:
            candidates.append(normalized if include_normalized_terms else surface)

        for term in candidates:
            if not term or len(term) > 128 or len(surface) > 512:
                continue
            identity = (term, match.start(), match.end(), kind)
            if identity in seen:
                continue
            seen.add(identity)
            token: dict[str, Any] = {
                "term": term,
                "surface": surface,
                "kind": kind,
            }
            if include_offsets:
                token["start_offset"] = match.start()
                token["end_offset"] = match.end()
            result.append(token)
            if len(result) > MAX_TOKENS:
                raise TokenizationError("source_too_large", f"text produces more than {MAX_TOKENS} lexical tokens")
    return result
