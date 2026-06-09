---
name: workflow-cleanup
description: Workflow conversation cleanup - clear autonomous workflow transcripts before they accumulate
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 26b434d9-2afa-4be4-be03-20d6d0fc2fe9
---

Always extract learnings from workflow transcripts BEFORE clearing them.

**Why:** Autonomous workflows (code-review, code-solve, pr-review, doc-improve) accumulate conversation context in subagent transcripts. These are execution logs that grow over time but are safe to delete since each workflow run is independent.

**How to apply:** Before clearing workflow history:
1. Check for patterns/learnings in recent runs
2. Save any valuable insights to memory
3. Then clear the accumulated transcripts

**Clearing process:**
```bash
# Safe to clear - these are autonomous workflow execution logs:
rm -rf ~/.claude/projects/*/subagents/workflows/*
rm -rf ~/.claude/projects/*/workflows/*
```

**What these are:**
- Subagent conversation transcripts from multi-AI workflows
- Worker + arbiter decision logs
- Cached workflow results
- NOT the main conversation history (that's separate)

**When to clear:**
- When context limits are hit
- Periodically for cleanup (monthly/quarterly)
- Before major workflow runs to free up space

**What NOT to clear:**
- Main conversation files (`.jsonl` at project root)
- Memory files
- Skill definitions
- Workflow scripts themselves
