"""Deterministic entity/identifier extraction with optional local CPU spaCy NER."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

PROFILE_NAME = "technical-default"
PROFILE_VERSION = "0.1"
MAX_TEXT_CHARS = 262_144
MAX_ENTITIES = 1000

# Known CE aliases are explicit mappings, not model guesses.
_ALIASES = (
    ("Claude Ensemble", "project", "Claude Ensemble"),
    ("claude-ensemble", "project", "Claude Ensemble"),
    ("CE", "project", "Claude Ensemble"),
)

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_WINDOWS_PATH_RE = re.compile(r"(?<![\w])(?:[A-Za-z]:\\(?:[^\\/:*?\"<>|\r\n]+\\)*[^\\/:*?\"<>|\r\n]+)")
_ABSOLUTE_PATH_RE = re.compile(r"(?<![\w])/(?:[A-Za-z0-9._@+~-]+/)*[A-Za-z0-9._@+~-]+")
_RELATIVE_PATH_RE = re.compile(r"(?<![\w./])(?:[A-Za-z0-9._@+~-]+/)+[A-Za-z0-9._@+~-]+")
_PULL_REQUEST_RE = re.compile(r"(?i)(?<!\w)(?:pull\s+request|pr)\s*#?\s*\d+\b")
_ISSUE_RE = re.compile(r"(?i)(?<!\w)issue\s*#?\s*\d+\b")
_HASH_ID_RE = re.compile(r"(?<!\w)#\d+\b")
_VERSION_RE = re.compile(r"(?<![\w])v?\d+\.\d+(?:\.\d+){0,2}(?:[-+][0-9A-Za-z.-]+)?(?![\w])")
_TECHNICAL_IDENTIFIER_RE = re.compile(
    r"\b(?:"
    r"[A-Z][a-z0-9]+[A-Z][A-Za-z0-9_$]*|"
    r"[a-z]+[A-Z][A-Za-z0-9_$]*|"
    r"[A-Z]{2,}[A-Z0-9]*|"
    r"[A-Za-z_$][A-Za-z0-9_$]*[_$][A-Za-z0-9_$]*|"
    r"[A-Za-z_$][A-Za-z0-9_$]*\d[A-Za-z0-9_$]*"
    r")\b"
)

_SPACY_LABELS = {
    "PERSON": "person",
    "ORG": "organization",
    "GPE": "location",
    "LOC": "location",
    "FAC": "facility",
    "PRODUCT": "product",
    "EVENT": "event",
    "WORK_OF_ART": "work_of_art",
    "LAW": "law",
    "LANGUAGE": "language",
    "NORP": "group",
}


class EntityExtractionError(ValueError):
    """An entity extraction request violates the v1 contract."""

    def __init__(self, code: str, message: str, *, status: int = 422):
        super().__init__(message)
        self.code = code
        self.status = status


def _candidate(kind: str, text: str, start: int, end: int, normalized: str,
               confidence: float, exact: bool, priority: int) -> dict[str, Any]:
    return {
        "kind": kind,
        "text": text,
        "normalized": normalized,
        "start_offset": start,
        "end_offset": end,
        "confidence": confidence,
        "exact": exact,
        "_priority": priority,
    }


def _trim_url(text: str, start: int, end: int) -> int:
    while end > start and text[end - 1] in ".,;:!?)]}":
        end -= 1
    return end


def _pattern_candidates(text: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for match in _URL_RE.finditer(text):
        end = _trim_url(text, match.start(), match.end())
        if end > match.start():
            surface = text[match.start():end]
            found.append(_candidate("url", surface, match.start(), end, surface, 1.0, True, 100))

    path_patterns = (
        ("file_path", _WINDOWS_PATH_RE),
        ("file_path", _ABSOLUTE_PATH_RE),
        ("file_path", _RELATIVE_PATH_RE),
    )
    for kind, pattern in path_patterns:
        for match in pattern.finditer(text):
            surface = match.group(0)
            found.append(_candidate(kind, surface, match.start(), match.end(), surface, 1.0, True, 95))

    for pattern, kind, priority in (
        (_PULL_REQUEST_RE, "pull_request_identifier", 92),
        (_ISSUE_RE, "issue_identifier", 92),
        (_HASH_ID_RE, "issue_identifier", 90),
        (_VERSION_RE, "version", 88),
    ):
        for match in pattern.finditer(text):
            surface = match.group(0)
            if kind == "pull_request_identifier":
                number = re.search(r"\d+", surface)
                normalized = f"pr:{number.group(0)}" if number else surface.casefold()
            elif kind == "issue_identifier":
                number = re.search(r"\d+", surface)
                normalized = number.group(0) if number else surface.casefold()
            else:
                normalized = surface.casefold()
            found.append(_candidate(kind, surface, match.start(), match.end(), normalized, 1.0, True, priority))

    for match in _TECHNICAL_IDENTIFIER_RE.finditer(text):
        surface = match.group(0)
        found.append(_candidate("technical_identifier", surface, match.start(), match.end(),
                                surface, 1.0, True, 70))
    return found


def _alias_candidates(text: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for alias, kind, canonical in _ALIASES:
        pattern = re.compile(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", re.IGNORECASE)
        for match in pattern.finditer(text):
            surface = text[match.start():match.end()]
            found.append(_candidate(kind, surface, match.start(), match.end(), canonical,
                                    1.0, False, 80))
    return found


class EntityExtractor:
    """Exact local workers plus a deterministic overlap arbiter."""

    def __init__(self, *, ner_model_path: str | None = None, nlp: Any = None):
        self.ner_model_path = ner_model_path if ner_model_path is not None else os.environ.get("CE_ENTITY_NER_MODEL_PATH")
        self._nlp = nlp
        self._ner_error: str | None = None

    def _load_nlp(self) -> Any:
        if self._nlp is not None:
            return self._nlp
        if not self.ner_model_path:
            return None
        path = Path(self.ner_model_path).expanduser()
        if not path.is_dir():
            self._ner_error = "configured local NER model directory does not exist"
            raise EntityExtractionError("service_unavailable", self._ner_error, status=503)
        try:
            import spacy
            spacy.require_cpu()
            self._nlp = spacy.load(str(path))
            self._ner_error = None
            return self._nlp
        except EntityExtractionError:
            raise
        except Exception as exc:
            self._ner_error = "configured local NER model could not be loaded offline on CPU"
            raise EntityExtractionError("service_unavailable", self._ner_error, status=503) from exc

    def readiness(self) -> dict[str, Any]:
        checks = [
            {"name": "technical-patterns", "status": "ok"},
            {"name": "known-aliases", "status": "ok"},
        ]
        if not self.ner_model_path and self._nlp is None:
            checks.append({"name": "local-ner-model", "status": "degraded"})
            return {"service": "entity-extraction", "status": "degraded", "ready": True, "checks": checks}
        try:
            self._load_nlp()
            checks.append({"name": "local-ner-model", "status": "ok"})
            return {"service": "entity-extraction", "status": "ready", "ready": True, "checks": checks}
        except EntityExtractionError as exc:
            checks.append({"name": "local-ner-model", "status": "not_ready", "code": exc.code})
            return {"service": "entity-extraction", "status": "not_ready", "ready": False, "checks": checks}

    def extract(self, text: Any) -> list[dict[str, Any]]:
        if not isinstance(text, str):
            raise EntityExtractionError("invalid_parameter", "text must be a string", status=400)
        if len(text) > MAX_TEXT_CHARS:
            raise EntityExtractionError("source_too_large", "text exceeds the character limit", status=413)
        try:
            text.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise EntityExtractionError("invalid_parameter", "text contains invalid Unicode", status=400) from exc

        candidates = _pattern_candidates(text)
        candidates.extend(_alias_candidates(text))
        nlp = self._load_nlp()
        if nlp is not None and text:
            try:
                doc = nlp(text)
            except Exception as exc:
                raise EntityExtractionError("service_unavailable", "local NER inference failed", status=503) from exc
            for entity in doc.ents:
                kind = _SPACY_LABELS.get(entity.label_)
                if kind is None:
                    continue
                surface = text[entity.start_char:entity.end_char]
                if surface:
                    # spaCy's standard NER API does not expose calibrated per-span
                    # probabilities. 0.5 explicitly means unscored model inference;
                    # callers should use exact=false and uncertainty-aware planning.
                    candidates.append(_candidate(kind, surface, entity.start_char, entity.end_char,
                                                 surface.casefold(), 0.5, False, 50))
        return self._arbitrate(candidates)

    @staticmethod
    def _arbitrate(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Higher-priority exact spans win overlaps. Stable tie-breaks make the result
        # reproducible regardless of worker execution order.
        candidates.sort(key=lambda item: (
            -item["_priority"], item["start_offset"], -(item["end_offset"] - item["start_offset"]),
            item["kind"], item["text"],
        ))
        accepted: list[dict[str, Any]] = []
        occupied = bytearray(max((item["end_offset"] for item in candidates), default=0))
        for candidate in candidates:
            start, end = candidate["start_offset"], candidate["end_offset"]
            if any(occupied[start:end]):
                continue
            occupied[start:end] = b"\x01" * (end - start)
            accepted.append(candidate)
        accepted.sort(key=lambda item: (item["start_offset"], item["end_offset"], item["kind"]))
        output = [{key: value for key, value in item.items() if key != "_priority"} for item in accepted]
        if len(output) > MAX_ENTITIES:
            raise EntityExtractionError("source_too_large", "text produces more than 1000 extracted entities", status=413)
        return output


_extractor: EntityExtractor | None = None


def get_extractor() -> EntityExtractor:
    global _extractor
    if _extractor is None:
        _extractor = EntityExtractor()
    return _extractor


def reset_extractor_for_tests() -> None:
    global _extractor
    _extractor = None
