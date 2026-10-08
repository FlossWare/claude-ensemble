"""MCP adapter for the transport-neutral capability layer.

This module deliberately has no MCP SDK dependency. The orchestration layer
knows only about capabilities; an MCP client is supplied as a small adapter
with a call_tool method.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from .core import CapabilityRequest, CapabilityResult


class MCPClient(Protocol):
    """Minimal MCP transport contract required by CE."""

    def call_tool(
        self,
        tool_name: str,
        arguments: Mapping[str, Any],
    ) -> Any:
        """Invoke one MCP tool and return its transport result."""


class MCPAdapter:
    """Expose selected MCP tools as named CE capabilities."""

    def __init__(
        self,
        client: MCPClient,
        bindings: Mapping[str, str],
    ) -> None:
        self._client = client
        self._bindings = {
            _normalize_name(capability): tool
            for capability, tool in bindings.items()
        }

    def has_capability(self, name: str) -> bool:
        return _normalize_name(name) in self._bindings

    def execute(self, request: CapabilityRequest) -> CapabilityResult:
        capability = _normalize_name(request.name)
        tool_name = self._bindings.get(capability)
        if tool_name is None:
            return CapabilityResult.failed(
                capability,
                "capability is not bound to an MCP tool",
            )

        try:
            data = self._client.call_tool(tool_name, request.arguments)
        except Exception as exc:
            return CapabilityResult.failed(
                capability,
                f"MCP capability failed: {type(exc).__name__}",
                metadata={"tool": tool_name},
            )

        return CapabilityResult.ok(
            capability,
            data,
            metadata={"transport": "mcp", "tool": tool_name},
        )

    def register_with(self, registry) -> None:
        """Register each bound MCP capability with a CE registry."""
        for capability in self._bindings:
            registry.register(capability, self.execute)


def _normalize_name(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("capability name must be a non-empty string")
    return name.strip().lower()
