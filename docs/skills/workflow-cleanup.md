---
name: workflow-cleanup
description: Clean accumulated workflow conversation history - extract learnings first, then clear
tags: [maintenance, workflows, cleanup]
---

# Workflow Cleanup - Extract Learnings & Clear History

Clean accumulated autonomous workflow conversation transcripts (code-review, code-solve, pr-review, doc-improve).

## Usage

```bash
/workflow-cleanup                  # Interactive: shows stats, confirms before clearing
/workflow-cleanup --dry-run        # Show what would be cleared
/workflow-cleanup --auto           # Auto-clear without confirmation
```

## What This Does

1. **Scan** - Find all workflow transcript directories
2. **Analyze** - Check sizes and patterns
3. **Extract Learnings** - Look for important patterns/insights
4. **Save** - Record learnings to memory if found
5. **Clear** - Remove accumulated transcripts

## What Gets Cleared

✅ **Safe to clear:**
- `~/.claude/projects/*/subagents/workflows/*` - Workflow execution logs
- `~/.claude/projects/*/workflows/*` - Workflow cached results
- Autonomous workflow transcripts (each run is independent)

❌ **NOT cleared:**
- Main conversation files (`.jsonl` at project root)
- Memory files (`memory/`)
- Skill definitions (`skills/`)
- Workflow scripts (`workflows/*.js`)
- Regular subagent transcripts (non-workflow)

## Why Clear

**Workflow transcripts accumulate because:**
- Multi-AI consensus runs spawn many subagents
- Each worker + arbiter has full conversation logs
- These pile up over time (can reach 1-2MB per project)
- Not needed - each workflow run is independent

**Benefits:**
- Free up disk space
- Prevent context bloat
- Keep Claude Code responsive

## Example Output

```
📊 Workflow Cleanup Analysis
═══════════════════════════════════════

Found workflow transcripts in 48 projects:

Top 10 by size:
  1.5M  /home/.claude/projects/-home-sfloess/.../workflows
  890K  /home/.claude/projects/.../nexus-java-review/.../workflows
  720K  /home/.claude/projects/.../VirtOS-ai-review/.../workflows
  ...

Total: 12.4MB across 48 projects

🔍 Extracting learnings...
   ✓ No new patterns found (already in memory)

💭 Clear 12.4MB of workflow transcripts? [Y/n]: y

🗑️  Clearing...
   ✓ Cleared 48 workflow directories
   ✓ Freed 12.4MB

✅ Cleanup complete!
```

## When to Run

- **Monthly** - Routine cleanup
- **Before large workflow runs** - Free up space
- **When context limits hit** - Immediate cleanup
- **Quarterly** - Thorough maintenance

## Integration

### Cron Schedule
```bash
# Monthly cleanup (first of month at 2am)
0 2 1 * * /workflow-cleanup --auto
```

### Manual
```bash
# Quick check
/workflow-cleanup --dry-run

# Interactive cleanup
/workflow-cleanup

# Auto cleanup
/workflow-cleanup --auto
```

## Learning Extraction

Before clearing, the skill checks for:
- Common patterns across runs
- Frequent issues found
- Consensus trends
- Performance insights

Saves findings to memory for future reference.

## Safety

- **Dry run available** - See before clearing
- **Confirmation required** - Unless `--auto` flag
- **Backups not needed** - Transcripts are expendable logs
- **No impact on workflows** - Each run generates fresh transcripts

---

**Version**: 1.0  
**Created**: 2026-06-04  
**Global**: Works across all projects
