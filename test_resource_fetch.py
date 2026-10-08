from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from resource_fetch import ResourceFetchError, ResourceFetcher


def test_fetch_file_uri(tmp_path: Path) -> None:
    source = tmp_path / "rfc.txt"
    source.write_text("RFC test content", encoding="utf-8")

    resource = ResourceFetcher().fetch(source.as_uri())

    assert resource.content == b"RFC test content"
    assert resource.filename == "rfc.txt"
    assert resource.size == len(resource.content)
    assert resource.final_uri == source.as_uri()


def test_file_uri_rejects_remote_host() -> None:
    with pytest.raises(ResourceFetchError, match="local host"):
        ResourceFetcher().fetch("file://example.com/tmp/test.txt")


def test_unsupported_scheme_is_rejected() -> None:
    with pytest.raises(ResourceFetchError, match="unsupported URI scheme"):
        ResourceFetcher().fetch("gopher://example.com/rfc.txt")


def test_file_size_limit(tmp_path: Path) -> None:
    source = tmp_path / "large.txt"
    source.write_bytes(b"123456")

    with pytest.raises(ResourceFetchError, match="maximum size"):
        ResourceFetcher(max_bytes=5).fetch(source.as_uri())


def test_http_resource_metadata_and_content() -> None:
    response = MagicMock()
    response.headers.get.return_value = None
    response.headers.get_content_type.return_value = "text/plain"
    response.geturl.return_value = "https://example.test/final/rfc.txt"
    response.status = 200
    response.read.side_effect = [b"RFC content", b""]

    context = MagicMock()
    context.__enter__.return_value = response
    context.__exit__.return_value = False

    with patch("resource_fetch.urlopen", return_value=context) as urlopen:
        resource = ResourceFetcher().fetch("https://example.test/rfc.txt")

    urlopen.assert_called_once()
    assert resource.content == b"RFC content"
    assert resource.content_type == "text/plain"
    assert resource.filename == "rfc.txt"
    assert resource.status == 200
    assert resource.final_uri == "https://example.test/final/rfc.txt"


def test_content_disposition_filename_is_used() -> None:
    response = MagicMock()
    response.headers.get.side_effect = lambda name: (
        'attachment; filename="rfc-9110.pdf"'
        if name == "Content-Disposition"
        else None
    )
    response.headers.get_content_type.return_value = "application/pdf"
    response.geturl.return_value = "https://example.test/download"
    response.status = 200
    response.read.side_effect = [b"pdf", b""]

    context = MagicMock()
    context.__enter__.return_value = response
    context.__exit__.return_value = False

    with patch("resource_fetch.urlopen", return_value=context):
        resource = ResourceFetcher().fetch("https://example.test/download")

    assert resource.filename == "rfc-9110.pdf"


def test_network_resource_is_bounded() -> None:
    response = MagicMock()
    response.headers.get.return_value = None
    response.headers.get_content_type.return_value = "application/octet-stream"
    response.geturl.return_value = "https://example.test/big"
    response.status = 200
    response.read.side_effect = [b"12345", b"6"]

    context = MagicMock()
    context.__enter__.return_value = response
    context.__exit__.return_value = False

    with patch("resource_fetch.urlopen", return_value=context):
        with pytest.raises(ResourceFetchError, match="maximum size"):
            ResourceFetcher(max_bytes=5).fetch("https://example.test/big")


def test_empty_uri_is_rejected() -> None:
    with pytest.raises(ResourceFetchError, match="must not be empty"):
        ResourceFetcher().fetch("   ")
