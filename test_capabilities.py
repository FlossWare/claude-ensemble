from __future__ import annotations

import pytest

from capabilities import (
    CapabilityError,
    CapabilityRegistry,
    CapabilityRequest,
    CapabilityResult,
    MCPAdapter,
)


def test_registry_resolves_and_executes_capability() -> None:
    registry = CapabilityRegistry()
    registry.register(
        "resource.fetch",
        lambda request: CapabilityResult.ok(
            request.name,
            {"uri": request.arguments["uri"]},
        ),
    )

    result = registry.execute(
        CapabilityRequest("RESOURCE.FETCH", {"uri": "file:///tmp/a"})
    )

    assert result.success is True
    assert result.data == {"uri": "file:///tmp/a"}
    assert registry.names() == ("resource.fetch",)


def test_registry_rejects_duplicate_and_unknown_capabilities() -> None:
    registry = CapabilityRegistry()
    handler = lambda request: CapabilityResult.ok(request.name)

    registry.register("repository.read", handler)

    with pytest.raises(CapabilityError, match="already registered"):
        registry.register("REPOSITORY.READ", handler)

    with pytest.raises(CapabilityError, match="unknown capability"):
        registry.resolve("knowledge.search")


class FakeMCPClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def call_tool(self, tool_name: str, arguments) -> object:
        self.calls.append((tool_name, dict(arguments)))
        return {"ok": True}


def test_mcp_adapter_delegates_without_exposing_transport() -> None:
    client = FakeMCPClient()
    adapter = MCPAdapter(
        client,
        {"repository.read": "github_get_pull_request"},
    )
    registry = CapabilityRegistry()
    adapter.register_with(registry)

    result = registry.execute(
        CapabilityRequest("repository.read", {"repository": "FlossWare/claude-ensemble"})
    )

    assert result.success is True
    assert result.data == {"ok": True}
    assert result.metadata == {
        "transport": "mcp",
        "tool": "github_get_pull_request",
    }
    assert client.calls == [
        (
            "github_get_pull_request",
            {"repository": "FlossWare/claude-ensemble"},
        )
    ]


def test_mcp_adapter_reports_transport_failure_without_leaking_exception_text() -> None:
    class FailingClient:
        def call_tool(self, tool_name, arguments):
            raise RuntimeError("secret token should not escape")

    adapter = MCPAdapter(
        FailingClient(),
        {"knowledge.search": "search_knowledge"},
    )

    result = adapter.execute(CapabilityRequest("knowledge.search"))

    assert result.success is False
    assert result.error == "MCP capability failed: RuntimeError"
    assert "secret token" not in (result.error or "")


def test_mcp_adapter_reports_unbound_capability() -> None:
    adapter = MCPAdapter(FakeMCPClient(), {"resource.fetch": "fetch_resource"})

    result = adapter.execute(CapabilityRequest("repository.read"))

    assert result.success is False
    assert result.error == "capability is not bound to an MCP tool"
