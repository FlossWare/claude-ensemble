# Review Shorthand Notation

Quick commands for arbiter/workers code review pattern without typing full arbitration configs.

## Basic Review

```bash
# 2-phase review (default)
review PR#123

# 3-phase review (with final arbiter for critical decisions)
review -3 PR#456

# Review a file instead of PR
review ./src/main.py

# Review a directory
review ./src/
```

## What Happens Automatically

**Phase 1 (Workers → Arbiter):**
- 3 workers: Sonnet (correctness), Haiku (performance), Fable (testing)
- 1 arbiter: Opus (synthesizes findings)

**Phase 2 (Adversarial Challenge):**
- 3 different workers: Opus (security), Gemini (architecture), Cursor (implementation)
- 1 arbiter: Gemini (cross-architecture perspective)

**Phase 3 (Optional, -3 flag):**
- Final arbiter: Opus (breaks ties, makes go/no-go decision)

## Meta-Review (Review the Review)

```bash
# Run arbiter/workers review ON the review findings
review-review PR#123

# This creates:
# 1. Phase 1: Workers review the original findings
# 2. Phase 2: Workers challenge the findings
# 3. Arbiter: Synthesizes whether the original review was sound
```

## What Gets Saved

Each review automatically saves to memory:
1. **Review findings** → `session_learnings`
2. **Key decisions** → `architecture_decisions`
3. **Alerts** → `integration_status` if critical issues
4. **Cost** → `cost_patterns` (Thompson model selection during review)

## Query Results

```bash
# Find all reviews
query-memory.py semantic-search "code review"

# Find reviews of specific file
query-memory.py semantic-search "review src/main.py"

# Find reviews with findings
query-memory.py semantic-search "critical finding"

# View synthesis of all reviews
memory-synthesis.py
```

## Advanced Options

```bash
# Custom phase count
review -4 PR#789  # 4-phase review (not common)

# Specific model for arbiter
ARBITER_MODEL=sonnet review PR#123

# Dry-run (show what would happen, don't save)
review --dry-run PR#123

# Force re-review (overwrite previous findings)
review --force PR#123

# Export review to file
review --export=review.md PR#123
```

## Notation Reference

| Symbol | Meaning |
|--------|---------|
| `PR#N` | GitHub PR number |
| `-N` | N-phase review |
| `review` | 2-phase standard review |
| `review-review` | Meta-review of findings |
| `--dry-run` | Simulate without saving |
| `--force` | Re-run even if exists |
| `--export` | Save results to file |

## Examples

```bash
# Simple: Review PR 123 with standard 2 phases
review PR#123

# Complex: 3-phase review of critical API file with export
review -3 ./src/api/payment.py --export=payment-review.md

# Meta: Question whether a previous review was thorough
review-review PR#100

# Analysis: What did we learn from all code reviews?
query-memory.py semantic-search "code review findings"
memory-synthesis.py
```

## Behind the Scenes

Each `review` command invokes:
1. Multi-phase arbiter/workers workflow
2. Saves findings to memory service
3. Thompson selects models for cost optimization
4. Learning system captures outcomes
5. Alerts if critical issues found
6. Synthesis updates insights

No manual configuration needed.
