# Review Shorthand Notation

Quick commands for multi-phase review using Arbiter/Workers pattern.  
**Works on:** Code (PRs, files), Documentation, Architecture, Design, Decisions, Schemas, Proposals—anything reviewable.

## Basic Commands

```bash
# REVIEW (single-tier: workers find issues, arbiter synthesizes)
review PR#123                  # Review a PR
review ./src/main.py          # Review a file
review ./docs/API.md          # Review documentation
review ./design/feature.md    # Review design
review -3 PR#456              # 3-phase review (more thorough)

# META-REVIEW (two-tier: review + re-review of findings)
meta-review PR#123            # Review AND re-review findings
meta-review ./docs/API.md     # Review AND re-review documentation
meta-review -3 PR#456         # 3-phase review + re-review combo
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

## Review vs Meta-Review

### Review (Single-Tier)
```bash
review PR#123                           # Standard review
review ./docs/API.md                    # Review documentation
review ./design/feature.md              # Review design
review -3 PR#456                        # 3-phase (more phases = more thorough)
```

**What happens:**
1. Workers analyze the artifact
2. Arbiter synthesizes findings
3. Results saved to memory

### Meta-Review (Two-Tier)
```bash
meta-review PR#123                      # Review AND re-review
meta-review ./docs/API.md               # Review AND re-review documentation
meta-review -3 PR#456                   # 3-phase review + re-review combo
```

**What happens:**
1. **Tier 1:** Workers analyze, Arbiter synthesizes findings
2. **Tier 2:** Different workers review those findings for gaps/issues
3. **Tier 2:** New Arbiter validates if original review was sound
4. Result: Double-checked, high-confidence findings

**Use meta-review for:**
- Critical code reviews
- Major architectural decisions
- Security-sensitive documentation
- Breaking API changes
- Any high-risk artifact

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
| `review` | Single-tier review (workers → arbiter) |
| `meta-review` | Two-tier review (review + re-review) |
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
# SINGLE-TIER REVIEW
review PR#123                           # Standard review
review ./docs/API.md                    # Review documentation
review ./design/feature.md              # Review design
review -3 PR#456                        # 3-phase critical review

# TWO-TIER META-REVIEW (review + re-review)
meta-review PR#100                      # Review AND re-review code
meta-review ./docs/API.md               # Review AND re-review documentation
meta-review ./ADR/0001-*.md            # Review AND re-review decision
meta-review -3 PR#456                   # 3-phase + re-review combo

# ANALYSIS: Find all reviews
query-memory.py semantic-search "review"
query-memory.py hybrid-search "meta-review"
memory-synthesis.py                     # All insights
```

**Comparison:**
- `review PR#123` — Workers analyze, Arbiter synthesizes
- `meta-review PR#123` — Workers analyze, Arbiter synthesizes, THEN different workers challenge findings, new Arbiter validates
- Result: Two-tier validation, higher confidence

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
