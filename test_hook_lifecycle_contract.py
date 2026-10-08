"""Regression tests for the Claude Ensemble hook lifecycle boundaries.

These source-level tests protect architectural boundaries that can otherwise
regress without a runtime test noticing that a hook was registered wrongly.
"""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent


class HookLifecycleContractTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_prompt_hook_is_read_only_context_retrieval(self):
        hook = self.read("hooks/memory-search-on-prompt.js")
        self.assertIn("/memory/search", hook)
        self.assertIn("UserPromptSubmit", hook)
        self.assertNotIn("storeLearnings(", hook)
        self.assertNotIn("post_task_analyzer", hook)
        self.assertNotIn("thompson", hook.lower())

    def test_legacy_post_task_hook_cannot_run_on_prompt_submission(self):
        hook = self.read("hooks/post-task-analysis.js")
        self.assertIn('event: "WorkflowComplete"', hook)
        self.assertIn("enabled: false", hook)
        self.assertNotIn('event: "UserPromptSubmit"', hook)

    def test_lifecycle_contract_requires_idempotency_and_evidence_gating(self):
        contract = self.read("docs/CLAUDE_CONTEXT_HOOK_LIFECYCLE.md")
        required_contracts = (
            "stable event/run identifier",
            "must be idempotent",
            "Missing or invalid outcome evidence",
            "Knowledge promotion is a separate explicit operation",
            "must remain disabled",
        )
        for requirement in required_contracts:
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, contract)

    def test_session_end_scripts_are_not_claimed_as_exactly_once(self):
        contract = self.read("docs/CLAUDE_CONTEXT_HOOK_LIFECYCLE.md")
        self.assertIn("no stable per-event idempotency key", contract)
        self.assertIn("Do not register both session-end scripts", contract)


if __name__ == "__main__":
    unittest.main()
