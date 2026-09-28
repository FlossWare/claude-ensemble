# Review Shorthand Notation

Quick commands for multi-phase review using Arbiter/Workers pattern.  
**Works on:** Code (PRs, files), Documentation, Architecture, Design, Decisions, Schemas, Proposals—anything reviewable.

## Basic Review

```bash
# STANDARD REVIEWS (2-phase: workers → arbiter)
review PR#123                  # Review a PR
review ./src/main.py          # Review a file
review ./docs/API.md          # Review documentation
review ./design/feature.md    # Review design

# MULTI-PHASE REVIEWS (arbiter gets final say)
review -3 PR#456              # 3-phase with final arbiter
review -3 ./docs/API.md       # 3-phase doc review
review -3 ./design/schema.sql # 3-phase critical design

# COMBINED REVIEW + META-REVIEW (validate the review)
review --meta PR#123          # Review, then meta-review findings
review -m ./docs/API.md       # Short form
review --meta -3 PR#456       # 3-phase + meta-review combo
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

## Review and Re-Review (Meta-Review)

### Combined: Review + Re-Review (Recommended for Critical Work)
```bash
review --meta PR#123                    # Review AND re-review in one command
review -m ./docs/API.md                 # Short form
review --meta -3 PR#456                 # 3-phase review + re-review combo
```

**What it does (Review → Re-Review):**
1. **Review Phase 1:** Workers analyze, Arbiter synthesizes findings
2. **Re-Review Phase 2:** Different workers challenge those findings
3. **Re-Review Phase 3:** New Arbiter validates the original review quality
4. **Result:** Double-checked, high-confidence findings

### Separate: Re-Review Only (for existing reviews)
```bash
meta-review PR#123                      # Re-review a previous review
meta-review ./docs/API.md               # Re-review documentation review
meta-review ./ADR/0001-*.md            # Re-review decision review
```

**When to use:** You already have findings from a review and want to validate them

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
# SINGLE REVIEW
review PR#123                           # Standard 2-phase
review ./docs/API.md                    # Review documentation
review ./design/feature.md              # Review design
review -3 PR#456                        # 3-phase critical review

# COMBINED REVIEW + META-REVIEW (Two-Tier Validation)
review --meta PR#123                    # Review + validate findings
review -m ./docs/API.md                 # Short form
review --meta -3 PR#456                 # 3-phase + meta-review combo

# SEPARATE META-REVIEW (if you already have findings)
meta-review PR#100                      # Challenge existing findings
meta-review ./docs/API.md               # Question doc review quality
meta-review ./ADR/0001-*.md            # Question decision thoroughness

# ANALYSIS: Find all reviews
query-memory.py semantic-search "review"
query-memory.py hybrid-search "meta-review findings"
memory-synthesis.py                     # All insights
```

**Two-Tier Review Comparison:**
- `review PR#123` → Workers find issues, Arbiter synthesizes
- `review --meta PR#123` → Same as above, PLUS workers challenge findings, new Arbiter validates review quality
- Result: Double-checked, highly confident findings

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
