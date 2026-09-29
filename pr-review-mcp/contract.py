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
        required = (
            "request_id", "platform", "repository", "merge_request_id",
            "title", "author", "source_branch", "target_branch",
        )
        missing = [name for name in required if name not in value]
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")
        if value["platform"] not in {"gitlab", "github", "bitbucket"}:
            raise ValueError("platform must be gitlab, github, or bitbucket")
        return cls(
            request_id=str(value["request_id"]),
            platform=str(value["platform"]),
            repository=str(value["repository"]),
            merge_request_id=int(value["merge_request_id"]),
            title=str(value["title"]),
            author=str(value["author"]),
            source_branch=str(value["source_branch"]),
            target_branch=str(value["target_branch"]),
            source_url=str(value.get("source_url", "")),
            action=str(value.get("action", "open")),
            metadata=dict(value.get("metadata", {})),
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
