"""Small, model-neutral URI resource fetcher for Claude Ensemble.

The fetcher retrieves resources only. Parsing, indexing, Graph updates, and
model calls belong to downstream consumers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen
import re


DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_BYTES = 50 * 1024 * 1024
_SUPPORTED_SCHEMES = frozenset({"file", "ftp", "http", "https"})


class ResourceFetchError(RuntimeError):
    """Raised when a URI cannot be fetched safely."""


@dataclass(frozen=True)
class Resource:
    """Fetched resource and transport metadata."""

    uri: str
    content: bytes
    content_type: str | None
    filename: str | None
    size: int
    status: int | None = None
    final_uri: str | None = None


class ResourceFetcher:
    """Fetch file, FTP, HTTP, and HTTPS resources with bounded reads."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_bytes: int = DEFAULT_MAX_BYTES,
        user_agent: str = "Claude-Ensemble-ResourceFetcher/1.0",
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.user_agent = user_agent

    def fetch(self, uri: str) -> Resource:
        """Fetch a URI and return its bytes plus transport metadata."""
        if not uri or not uri.strip():
            raise ResourceFetchError("URI must not be empty")

        parsed = urlparse(uri)
        scheme = parsed.scheme.lower()
        if scheme not in _SUPPORTED_SCHEMES:
            raise ResourceFetchError(
                f"unsupported URI scheme: {parsed.scheme or '<none>'}"
            )

        if scheme == "file":
            return self._fetch_file(uri, parsed)
        return self._fetch_network(uri, parsed)

    def _fetch_file(self, uri: str, parsed) -> Resource:
        if parsed.netloc not in ("", "localhost"):
            raise ResourceFetchError("file URI must refer to the local host")

        path = Path(unquote(parsed.path))
        if not path.is_file():
            raise ResourceFetchError(f"file does not exist: {path}")

        try:
            size = path.stat().st_size
        except OSError as exc:
            raise ResourceFetchError(f"cannot stat file: {path}") from exc

        if size > self.max_bytes:
            raise ResourceFetchError(
                f"resource exceeds maximum size of {self.max_bytes} bytes"
            )

        try:
            content = path.read_bytes()
        except OSError as exc:
            raise ResourceFetchError(f"cannot read file: {path}") from exc

        return Resource(
            uri=uri,
            content=content,
            content_type=None,
            filename=path.name or None,
            size=len(content),
            final_uri=uri,
        )

    def _fetch_network(self, uri: str, parsed) -> Resource:
        if not parsed.netloc:
            raise ResourceFetchError("network URI must include a host")

        request = Request(uri, headers={"User-Agent": self.user_agent})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                content_length = response.headers.get("Content-Length")
                if content_length:
                    try:
                        declared_size = int(content_length)
                    except ValueError:
                        declared_size = None
                    if declared_size is not None and declared_size > self.max_bytes:
                        raise ResourceFetchError(
                            f"resource exceeds maximum size of {self.max_bytes} bytes"
                        )

                content = self._read_bounded(response)
                content_type = response.headers.get_content_type()
                filename = _filename_from_headers(response.headers.get("Content-Disposition"))
                if not filename:
                    filename = Path(urlparse(response.geturl()).path).name or None

                status = getattr(response, "status", None)
                final_uri = response.geturl()

                return Resource(
                    uri=uri,
                    content=content,
                    content_type=content_type,
                    filename=filename,
                    size=len(content),
                    status=status,
                    final_uri=final_uri,
                )
        except ResourceFetchError:
            raise
        except Exception as exc:
            raise ResourceFetchError(f"failed to fetch {uri}: {exc}") from exc

    def _read_bounded(self, response) -> bytes:
        chunks: list[bytes] = []
        total = 0
        remaining = self.max_bytes

        while remaining:
            chunk = response.read(min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            remaining -= len(chunk)

        if remaining == 0:
            extra = response.read(1)
            if extra:
                raise ResourceFetchError(
                    f"resource exceeds maximum size of {self.max_bytes} bytes"
                )

        return b"".join(chunks)


def _filename_from_headers(content_disposition: str | None) -> str | None:
    if not content_disposition:
        return None

    match = re.search(r"""filename\s*=\s*(?:"([^"]+)"|([^;\s]+))""", content_disposition, re.IGNORECASE)
    if not match:
        return None
    return match.group(1) or match.group(2)
