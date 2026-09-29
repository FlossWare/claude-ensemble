"""Language-neutral merge-request review contract.

The contract is deliberately independent of Claude Code, GitLab, or a model
provider. Platform adapters normalize external events into ReviewRequest and
review implementations return ReviewResult.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewRequest:
    request_id: str
    platform: str
    repository: str
    merge_request_id: int
    title: str
    author: str
    source_branch: str
    target_branch: str
    source_url: str = ""
    action: str = "open"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ReviewRequest":
        if not isinstance(value, dict):
            raise ValueError("review request must be a JSON object")
        required = (
            "request_id", "platform", "repository", "merge_request_id",
            "title", "author", "source_branch", "target_branch",
        )
        missing = [name for name in required if name not in value]
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")
        if value["platform"] not in {"gitlab", "github", "bitbucket"}:
            raise ValueError("platform must be gitlab, github, or bitbucket")
        if (
            not isinstance(value["merge_request_id"], int)
            or isinstance(value["merge_request_id"], bool)
            or value["merge_request_id"] < 1
        ):
            raise ValueError("merge_request_id must be a positive integer")
        for name in (
            "request_id", "repository", "title", "author",
            "source_branch", "target_branch",
        ):
            if not isinstance(value[name], str) or not value[name].strip():
                raise ValueError(f"{name} must be a nonblank string")
        metadata = value.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be an object")
        return cls(
            request_id=value["request_id"],
            platform=value["platform"],
            repository=value["repository"],
            merge_request_id=value["merge_request_id"],
            title=value["title"],
            author=value["author"],
            source_branch=value["source_branch"],
            target_branch=value["target_branch"],
            source_url=str(value.get("source_url", "")),
            action=str(value.get("action", "open")),
            metadata=metadata,
        )


@dataclass(frozen=True)
class ReviewResult:
    request_id: str
    status: str
    decision: str = "comment"
    summary: str = ""
    findings: list[dict[str, Any]] = field(default_factory=list)
    model: str = ""
    cost_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any],
        expected_request_id: str | None = None,
    ) -> "ReviewResult":
        if not isinstance(value, dict):
            raise ValueError("review result must be a JSON object")
        required = (
            "request_id", "status", "decision", "summary",
            "findings", "model", "cost_usd", "metadata",
        )
        missing = [name for name in required if name not in value]
        if missing:
            raise ValueError(
                f"review result missing required fields: {', '.join(missing)}"
            )
        if not isinstance(value["request_id"], str) or not value["request_id"].strip():
            raise ValueError("review result request_id must be a nonblank string")
        if expected_request_id is not None and value["request_id"] != expected_request_id:
            raise ValueError("review result request_id does not match request")
        for name in ("status", "decision", "summary", "model"):
            if not isinstance(value[name], str):
                raise ValueError(f"review result {name} must be a string")
        if not isinstance(value["findings"], list):
            raise ValueError("review result findings must be a list")
        if not isinstance(value["metadata"], dict):
            raise ValueError("review result metadata must be an object")
        if (
            isinstance(value["cost_usd"], bool)
            or not isinstance(value["cost_usd"], (int, float))
        ):
            raise ValueError("review result cost_usd must be a number")
        return cls(
            request_id=value["request_id"],
            status=value["status"],
            decision=value["decision"],
            summary=value["summary"],
            findings=value["findings"],
            model=value["model"],
            cost_usd=float(value["cost_usd"]),
            metadata=value["metadata"],
        )
