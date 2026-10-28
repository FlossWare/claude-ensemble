"""Format-aware source adapters for RFCs, patents, repositories, and documents.

Adapters normalize source material only. They do not chunk, tokenize, embed, or
index; callers submit normalized records to the existing Memory REST API.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree

MAX_SOURCE_BYTES = 262_144
TEXT_SUFFIXES = {".c", ".cc", ".cpp", ".h", ".hpp", ".java", ".js", ".jsx", ".ts",
                 ".tsx", ".py", ".rs", ".go", ".rb", ".sh", ".sql", ".md", ".rst",
                 ".txt", ".json", ".yaml", ".yml", ".toml", ".xml", ".html", ".css"}
SOURCE_ID_RE = re.compile(r"^[A-Za-z0-9._~-]{1,128}$")


class SourceIngestionError(ValueError):
    """A source cannot be normalized safely."""


@dataclass(frozen=True)
class SourceDocument:
    source_key: str
    source_uri: str
    title: str
    source_type: str
    media_type: str
    content: str
    metadata: dict[str, object]
    content_sha256: str
    source_revision: str
    imported_at: str

    def to_memory_payload(self, *, scope: dict[str, str], index_profile: dict[str, str]) -> dict[str, object]:
        """Build a canonical Memory create/update payload; Index remains downstream."""
        provenance = {
            "origin": self.source_type,
            "source_uri": self.source_uri,
            "imported_at": self.imported_at,
            "source_revision": self.source_revision,
            "content_sha256": self.content_sha256,
            "title": self.title,
            "source_type": self.source_type,
            "media_type": self.media_type,
            "metadata": self.metadata,
        }
        return {
            "scope": scope,
            "type": "semantic",
            "content": self.content,
            "provenance": provenance,
            "retention_policy": {"kind": "retained"},
            "index_profile": index_profile,
            "request_id": str(uuid.uuid4()),
        }


class SourceAdapter(Protocol):
    def read(self, source: str | Path) -> list[SourceDocument]: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _document(source_key: str, uri: str, title: str, source_type: str, media_type: str,
              content: str, metadata: dict[str, object] | None = None,
              revision: str | None = None) -> SourceDocument:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise SourceIngestionError(f"{uri}: parsed content is empty")
    encoded = normalized.encode("utf-8")
    if len(encoded) > MAX_SOURCE_BYTES:
        raise SourceIngestionError(f"{uri}: normalized content exceeds {MAX_SOURCE_BYTES} UTF-8 bytes")
    digest = hashlib.sha256(encoded).hexdigest()
    return SourceDocument(
        source_key=source_key, source_uri=uri, title=title or Path(uri).name or uri,
        source_type=source_type, media_type=media_type, content=normalized,
        metadata=metadata or {}, content_sha256=digest,
        source_revision=revision or digest, imported_at=_now(),
    )


def _safe_read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise SourceIngestionError(f"not a regular non-symlink file: {path}")
    data = path.read_bytes()
    if len(data) > MAX_SOURCE_BYTES:
        raise SourceIngestionError(f"{path}: source exceeds {MAX_SOURCE_BYTES} bytes")
    return data


class RfcAdapter:
    """Parse a local RFC text file, retaining numbered section headings."""

    def read(self, source: str | Path) -> list[SourceDocument]:
        path = Path(source).expanduser().resolve()
        raw = _safe_read(path)
        text = raw.decode("utf-8", errors="replace")
        title = ""
        rfc_number = None
        for line in text.splitlines()[:80]:
            match = re.match(r"\s*Request for Comments:\s*(\d+)", line, re.I)
            if match:
                rfc_number = match.group(1)
            if re.match(r"\s*Title:\s*", line, re.I):
                title = re.sub(r"^\s*Title:\s*", "", line, flags=re.I).strip()
        sections: list[dict[str, str]] = []
        current: dict[str, str] | None = None
        body: list[str] = []
        for line in text.splitlines():
            # RFC section headings commonly use "1. Title" or "1.2. Title".
            match = re.match(r"^\s*(\d+(?:\.\d+)*\.?\s+\S.*)$", line)
            if match and len(line) < 180 and not line.strip().startswith(("RFC ", "Request for Comments")):
                if current:
                    current["content"] = "\n".join(body).strip()
                    sections.append(current)
                current = {"heading": match.group(1).strip()}
                body = []
            elif current:
                body.append(line)
        if current:
            current["content"] = "\n".join(body).strip()
            sections.append(current)
        # Preserve the complete document; section metadata is additive provenance.
        return [_document(
            f"rfc:{rfc_number or path.name}", path.as_uri(), title or path.stem,
            "rfc", "text/plain", text,
            {"rfc_number": rfc_number, "sections": sections, "format": "rfc-text"},
        )]


class _PatentHtmlText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1
        elif tag in {"p", "div", "section", "h1", "h2", "h3", "li", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1
        elif tag in {"p", "div", "section", "h1", "h2", "h3", "li"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def _xml_local(element: ElementTree.Element) -> str:
    return element.tag.rsplit("}", 1)[-1].lower()


class PatentAdapter:
    """Parse patent XML (including common publication XML) or saved patent HTML."""

    def read(self, source: str | Path) -> list[SourceDocument]:
        path = Path(source).expanduser().resolve()
        raw = _safe_read(path)
        decoded = raw.decode("utf-8", errors="replace")
        metadata: dict[str, object] = {"format": path.suffix.lower().lstrip(".")}
        sections: list[str] = []
        title = path.stem
        patent_id = None
        try:
            root = ElementTree.fromstring(decoded)
            for element in root.iter():
                tag = _xml_local(element)
                value = " ".join("".join(element.itertext()).split())
                if not value:
                    continue
                if tag in {"invention-title", "title"} and title == path.stem:
                    title = value
                elif tag in {"doc-number", "publication-number", "application-number"} and patent_id is None:
                    patent_id = value
                elif tag in {"abstract", "description", "claims", "claim-text"}:
                    label = {"abstract": "Abstract", "description": "Description",
                             "claims": "Claims", "claim-text": "Claim"}[tag]
                    sections.append(f"## {label}\n\n{value}")
            content = f"# {title}\n\n" + "\n\n".join(sections) if sections else decoded
        except ElementTree.ParseError:
            parser = _PatentHtmlText()
            parser.feed(decoded)
            content = html.unescape("".join(parser.parts))
            content = re.sub(r"[ \t]+", " ", content)
            content = re.sub(r"\n{3,}", "\n\n", content).strip()
            title_match = re.search(r"<title[^>]*>(.*?)</title>", decoded, re.I | re.S)
            if title_match:
                title = html.unescape(re.sub(r"<[^>]+>", "", title_match.group(1))).strip() or title
            patent_id_match = re.search(r"\b(?:publication|patent)\s*(?:number|no\.?|#)\s*[: ]\s*([A-Z0-9-]+)", content, re.I)
            patent_id = patent_id or (patent_id_match.group(1) if patent_id_match else None)
        metadata["patent_id"] = patent_id
        metadata["sections"] = sections
        return [_document(f"patent:{patent_id or path.name}", path.as_uri(), title,
                          "patent", "text/plain", content, metadata)]


def _extract_symbols(text: str, suffix: str) -> list[str]:
    patterns = [
        r"^\s*(?:public|protected|private|static|final|abstract|async|export|def|func|fn|class|interface|enum|struct|trait|type|function)\b[^;{}]*?\b([A-Za-z_$][\w$]*)\s*(?:\(|\{|:)",
        r"^\s*(?:class|interface|struct|enum|trait|def|function|func|fn)\s+([A-Za-z_$][\w$]*)",
    ]
    symbols: list[str] = []
    for line in text.splitlines():
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                name = match.group(1)
                if name not in symbols:
                    symbols.append(name)
                break
        if len(symbols) >= 500:
            break
    return symbols


class GitRepositoryAdapter:
    """Read a local Git working tree while preserving relative paths and symbols."""

    def __init__(self, *, max_files: int = 5000) -> None:
        self.max_files = max_files

    def read(self, source: str | Path) -> list[SourceDocument]:
        root = Path(source).expanduser().resolve()
        if not root.is_dir():
            raise SourceIngestionError(f"repository path is not a directory: {root}")
        documents: list[SourceDocument] = []
        errors: list[str] = []
        candidates = sorted(p for p in root.rglob("*")
                            if p.is_file() and not p.is_symlink()
                            and ".git" not in p.relative_to(root).parts
                            and p.suffix.lower() in TEXT_SUFFIXES)
        if len(candidates) > self.max_files:
            raise SourceIngestionError(f"repository has {len(candidates)} eligible files; limit is {self.max_files}")
        for path in candidates:
            relative = path.relative_to(root).as_posix()
            try:
                raw = _safe_read(path)
                text = raw.decode("utf-8")
                symbols = _extract_symbols(text, path.suffix.lower())
                documents.append(_document(
                    f"repo:{root.name}/{relative}", path.as_uri(), relative, "source_code",
                    "text/plain", text,
                    {"repository": root.name, "relative_path": relative, "symbols": symbols,
                     "file_extension": path.suffix.lower()},
                ))
            except (UnicodeDecodeError, OSError, SourceIngestionError) as exc:
                errors.append(f"{relative}: {exc}")
        if not documents and errors:
            raise SourceIngestionError("no repository files were ingested: " + "; ".join(errors[:5]))
        return documents


class DocumentAdapter:
    """Parse Markdown/text directly and PDF text through optional pypdf."""

    def read(self, source: str | Path) -> list[SourceDocument]:
        path = Path(source).expanduser().resolve()
        raw = _safe_read(path)
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader
            except ImportError as exc:
                raise SourceIngestionError("PDF ingestion requires optional dependency pypdf") from exc
            import io
            reader = PdfReader(io.BytesIO(raw), strict=True)
            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
            metadata = {"page_count": len(reader.pages), "format": "pdf"}
            media_type = "application/pdf"
        elif suffix in {".md", ".markdown", ".rst", ".txt"}:
            text = raw.decode("utf-8", errors="replace")
            metadata = {"format": suffix.lstrip(".")}
            media_type = "text/markdown" if suffix in {".md", ".markdown"} else "text/plain"
        else:
            raise SourceIngestionError(f"unsupported document format: {suffix or '(no extension)'}")
        return [_document(f"document:{path.name}", path.as_uri(), path.stem,
                          "document", media_type, text, metadata)]


class SourceManifest:
    """Durable source-to-Memory mapping and hash ledger for idempotent imports."""

    def __init__(self, path: str | Path):
        self.path = str(Path(path).expanduser())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS source_items (
                    source_key TEXT PRIMARY KEY,
                    content_sha256 TEXT NOT NULL,
                    source_revision TEXT NOT NULL,
                    memory_id TEXT,
                    state TEXT NOT NULL,
                    last_error TEXT,
                    updated_at TEXT NOT NULL
                )
            """)

    def get(self, source_key: str) -> dict[str, object] | None:
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM source_items WHERE source_key=?", (source_key,)).fetchone()
            return dict(row) if row else None

    def record(self, document: SourceDocument, *, memory_id: str | None, state: str,
               error: str | None = None) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute("""
                INSERT INTO source_items(source_key,content_sha256,source_revision,memory_id,state,last_error,updated_at)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(source_key) DO UPDATE SET
                    content_sha256=excluded.content_sha256,
                    source_revision=excluded.source_revision,
                    memory_id=COALESCE(excluded.memory_id,source_items.memory_id),
                    state=excluded.state,last_error=excluded.last_error,updated_at=excluded.updated_at
            """, (document.source_key, document.content_sha256, document.source_revision,
                  memory_id, state, error, _now()))

    def active_keys(self) -> set[str]:
        with sqlite3.connect(self.path) as db:
            return {row[0] for row in db.execute(
                "SELECT source_key FROM source_items WHERE state='active'")}


class MemoryRestClient:
    """Small HTTP client that submits normalized records to canonical Memory."""

    def __init__(self, base_url: str, *, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def request(self, method: str, path: str, payload: dict[str, object] | None = None,
                idempotency_key: str | None = None) -> tuple[int, dict[str, object]]:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json", "X-Request-ID": str(uuid.uuid4())}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        req = Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with urlopen(req, timeout=self.timeout) as response:
                raw = response.read()
                return response.status, json.loads(raw.decode("utf-8")) if raw else {}
        except HTTPError as exc:
            raw = exc.read()
            try:
                parsed = json.loads(raw.decode("utf-8")) if raw else {}
            except (UnicodeDecodeError, json.JSONDecodeError):
                parsed = {"error": {"message": raw.decode("utf-8", errors="replace")[:512]}}
            return exc.code, parsed
        except (URLError, TimeoutError) as exc:
            raise SourceIngestionError(f"Memory REST request failed: {exc}") from exc


def stable_memory_id(source_key: str) -> str:
    """Deterministic Memory ID for source identity; never contains a path/locator."""
    return hashlib.sha256(source_key.encode("utf-8")).hexdigest()[:32]
