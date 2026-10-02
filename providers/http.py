"""Small standard-library HTTP helper for external model providers."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ProviderHTTPError(RuntimeError):
    """Raised when an external provider rejects or cannot receive a request."""

    def __init__(self, provider: str, status: int | None, detail: str):
        self.provider = provider
        self.status = status
        super().__init__(f"{provider} API request failed"
                         + (f" with HTTP {status}" if status else "")
                         + f": {detail}")


def post_json(
    *,
    provider: str,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: float,
) -> tuple[dict[str, Any], dict[str, str]]:
    """POST JSON and return decoded response plus response headers."""
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body), dict(response.headers.items())
    except HTTPError as exc:
        try:
            body = exc.read().decode("utf-8")
        except Exception:
            body = str(exc)
        raise ProviderHTTPError(provider, exc.code, body[:2000]) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ProviderHTTPError(provider, None, str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise ProviderHTTPError(provider, None, "provider returned invalid JSON") from exc
