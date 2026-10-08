"""Regression tests for the Claude Ensemble hook lifecycle boundaries."""
from pathlib import Path
import json
import subprocess
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

    def test_legacy_post_task_hook_is_inert_at_runtime(self):
        script = (
            "const hook = require('./hooks/post-task-analysis.js'); "
            "hook.execute().then(result => process.stdout.write(JSON.stringify(result)));"
        )
        completed = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        result = json.loads(completed.stdout)
        self.assertEqual(result["skipped"], True)
        self.assertEqual(
            result["reason"], "disabled_until_learning_service_delegation"
        )

    def test_legacy_post_task_hook_has_no_executable_learning_side_effects(self):
        hook = self.read("hooks/post-task-analysis.js")
        self.assertIn('event: "WorkflowComplete"', hook)
        self.assertIn("enabled: false", hook)
        self.assertNotIn('event: "UserPromptSubmit"', hook)
        # Historical identifiers in comments are allowed. Reject executable
        # invocation/import patterns instead of banning explanatory text.
        for forbidden in (
            "require('../learning/post_task_analyzer",
            'require("../learning/post_task_analyzer',
            "child_process",
            "spawn(",
            "execFile(",
            "fork(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, hook)

    def test_legacy_workflow_hook_cannot_write_learning_storage_directly(self):
        hook = self.read("hooks/post-workflow-learning.js")
        self.assertIn("disabled_until_learning_service_delegation", hook)
        self.assertNotIn("storeLearnings(", hook)
        self.assertNotIn("postgres-adapter", hook)

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
