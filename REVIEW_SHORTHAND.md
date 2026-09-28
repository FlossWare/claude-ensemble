# Review Shorthand Notation

Quick commands for multi-phase review using Arbiter/Workers pattern.  
**Works on:** Code (PRs, files), Documentation, Architecture, Design, Decisions, Schemas, Proposals—anything reviewable.

## Basic Review

```bash
# CODE REVIEWS
review PR#123                  # 2-phase review of PR
review ./src/main.py          # Review a file
review -3 PR#456              # 3-phase review (final arbiter)

# DOCUMENTATION REVIEWS
review ./docs/API.md          # API documentation
review ./ARCHITECTURE.md      # Architecture guide
review ./CONTRIBUTING.md      # Contributing guidelines
review -3 ./docs/API.md       # 3-phase doc review

# DESIGN REVIEWS
review ./design/feature.md    # Feature design
review ./design/schema.sql    # Database schema

# DECISION REVIEWS
review ./ADR/0001-*.md        # Architecture Decision Record
review ./DECISION_LOG.md      # Decision log

# PROPOSAL REVIEWS
review ./proposals/new-api.md # RFC or proposal
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

## Meta-Review (Challenge the Review)

Question whether a review was thorough. Works on any artifact type.

```bash
# CODE - Question a PR review
meta-review PR#123

# DOCUMENTATION - Question doc review quality
meta-review ./docs/API.md

# DESIGN - Question design review soundness
meta-review ./design/feature.md

# DECISION - Question if decision was thoroughly reviewed
meta-review ./ADR/0001-*.md

# This creates:
# 1. Workers: Challenge original findings for gaps
# 2. Arbiter: Synthesize whether review was sound
# 3. Findings: Saved to memory for learning
```

## What Gets Saved

Each review automatically saves to memory (searchable by artifact type):
1. **Code reviews** → `session_learnings` (tagged: PR, code)
2. **Doc reviews** → `session_learnings` (tagged: documentation)
3. **Design reviews** → `session_learnings` (tagged: design, architecture)
4. **Decision reviews** → `architecture_decisions` (decision rationale)
5. **Alerts** → `integration_status` if critical issues
6. **Cost** → `cost_patterns` (Thompson model selection during review)

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
| `./path/to/file` | File or directory to review |
| `-N` | N-phase review (e.g., `-3` for 3 phases) |
| `review` | 2-phase standard review |
| `meta-review` | Challenge the review findings |
| `--dry-run` | Simulate without saving |
| `--force` | Re-run even if exists |
| `--export` | Save results to file |

**Artifact types auto-detected:**
- PR → Pull Request
- `.md` files → Documentation (or Architecture/ADR if named appropriately)
- `design/` files → Design Document
- `.sql` files → Database Schema
- `.py`, `.js`, `.go` → Language-specific code

## Examples

```bash
# CODE REVIEW
review PR#123                           # Standard 2-phase
review -3 PR#456                        # 3-phase with final arbiter
meta-review PR#100                      # Challenge the review

# DOCUMENTATION REVIEW
review ./docs/API.md                    # Review docs
review -3 ./docs/API.md                 # 3-phase doc review
meta-review ./docs/API.md               # Question doc review quality

# DESIGN REVIEW
review ./design/feature.md              # Review design
meta-review ./design/feature.md         # Verify design soundness

# ARCHITECTURE DECISION
review ./ADR/0001-event-sourcing.md    # Review ADR
meta-review ./ADR/0001-*.md            # Question ADR thoroughness

# DATABASE SCHEMA
review ./design/schema.sql              # Review schema
review -3 ./design/schema.sql           # 3-phase critical schema

# ANALYSIS: Find all reviews
query-memory.py semantic-search "review documentation"
query-memory.py hybrid-search "meta-review"
memory-synthesis.py                     # All insights
```

## Behind the Scenes

Each `review` or `meta-review` command:
1. **Detects artifact type** (code, documentation, design, decision, schema, etc.)
2. **Runs multi-phase arbiter/workers** (different models challenge findings)
3. **Saves to memory** (findings, decisions, alerts, costs)
4. **Thompson routing** (selects best models per artifact type)
5. **Learning system** (captures outcomes for improvement)
6. **Alerting** (flags critical issues)
7. **Synthesis** (updates insights across all artifact types)

No configuration needed. Everything is automatic and searchable.
