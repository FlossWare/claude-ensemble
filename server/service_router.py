#!/usr/bin/env python3
"""Route Claude Ensemble REST calls to local handlers or remote service URLs."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


@dataclass(frozen=True)
class ServiceTarget:
    name: str
    url: str | None


class ServiceRouter:
    """Resolve a logical service to a local handler or a remote REST endpoint."""

    def __init__(self, *, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._handlers: dict[str, object] = {}

    def register(self, name: str, handler: object) -> None:
        self._handlers[name] = handler

    def target(self, name: str, url: str | None) -> ServiceTarget:
        return ServiceTarget(name=name, url=url)

    def is_local(self, url: str | None) -> bool:
        if not url:
            return True

        parsed = urlsplit(url)
        hostname = (parsed.hostname or "").lower()
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

        local_names = {"localhost", "127.0.0.1", "::1", self.host.lower()}
        return hostname in local_names and port == self.port

    def remote_url(self, base_url: str, path: str, query: str) -> str:
        base = urlsplit(base_url)
        suffix = path if path.startswith("/") else f"/{path}"
        combined_path = f"{base.path.rstrip('/')}{suffix}"
        return urlunsplit(
            (base.scheme, base.netloc, combined_path, query, "")
        )

    def forward(
        self,
        *,
        base_url: str,
        method: str,
        path: str,
        query: str,
        headers: dict[str, str],
        body: bytes,
    ) -> tuple[int, list[tuple[str, str]], bytes]:
        target = self.remote_url(base_url, path, query)
        outgoing = {
            key: value
            for key, value in headers.items()
            if key.lower() not in _HOP_BY_HOP_HEADERS
        }
        outgoing["X-Claude-Ensemble-Forwarded"] = "1"

        request = Request(target, data=body or None, headers=outgoing, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                response_headers = [
                    (key, value)
                    for key, value in response.headers.items()
                    if key.lower() not in _HOP_BY_HOP_HEADERS
                ]
                return response.status, response_headers, response.read()
        except HTTPError as exc:
            response_headers = [
                (key, value)
                for key, value in exc.headers.items()
                if key.lower() not in _HOP_BY_HOP_HEADERS
            ]
            return exc.code, response_headers, exc.read()
        except URLError as exc:
            raise ConnectionError(f"service forwarding failed: {exc.reason}") from exc
