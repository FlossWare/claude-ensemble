#!/usr/bin/env python3
"""Route Claude Ensemble REST calls to local handlers or remote service URLs."""

from __future__ import annotations

from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

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
_MAX_FORWARD_HOPS = 8


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: N802
        return None


class ServiceRouter:
    """Resolve logical services and forward REST calls to remote Ensemble nodes."""

    def __init__(self, *, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._opener = build_opener(_NoRedirectHandler)

    def is_local(self, url: str | None) -> bool:
        if not url:
            return True

        parsed = urlsplit(url)
        hostname = (parsed.hostname or "").lower()
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        local_names = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "::", self.host.lower()}
        return hostname in local_names and port == self.port

    @staticmethod
    def remote_url(base_url: str, path: str, query: str) -> str:
        base = urlsplit(base_url)
        suffix = path if path.startswith("/") else f"/{path}"
        combined_path = f"{base.path.rstrip('/')}{suffix}"
        return urlunsplit((base.scheme, base.netloc, combined_path, query, ""))

    @staticmethod
    def validate_url(base_url: str) -> None:
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("service URL must use http or https")

    @staticmethod
    def is_loopback_url(base_url: str) -> bool:
        hostname = (urlsplit(base_url).hostname or "").lower()
        return hostname in {"localhost", "127.0.0.1", "::1"}

    def forward(
        self,
        *,
        base_url: str,
        method: str,
        path: str,
        query: str,
        headers: dict[str, str],
        body: bytes,
        service_token: str | None = None,
        hop_count: int = 0,
    ) -> tuple[int, list[tuple[str, str]], bytes]:
        self.validate_url(base_url)
        if hop_count >= _MAX_FORWARD_HOPS:
            raise ValueError("forwarding hop limit exceeded")

        target = self.remote_url(base_url, path, query)
        outgoing = {
            key: value
            for key, value in headers.items()
            if key.lower() not in _HOP_BY_HOP_HEADERS
            and key.lower() not in {"host", "authorization", "cookie"}
        }
        outgoing["X-Claude-Ensemble-Forwarded"] = str(hop_count + 1)
        if service_token:
            outgoing["Authorization"] = f"Bearer {service_token}"

        request = Request(target, data=body or None, headers=outgoing, method=method)
        try:
            with self._opener.open(request, timeout=30) as response:
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
        except (URLError, TimeoutError, OSError) as exc:
            raise ConnectionError("service forwarding failed") from exc
