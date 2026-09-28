# Review Shorthand Notation

Quick commands for multi-phase review using Arbiter/Workers pattern.  
**Works on:** Code (PRs, files), Documentation, Architecture, Design, Decisions, Schemas, Proposals—anything reviewable.

## Basic Commands

Support **arbitrary tier counts** in three ways:

```bash
# METHOD 1: Symlink names (predefined)
review PR#123                         # 1 tier
meta-review PR#123                    # 2 tiers
meta-meta-review PR#123               # 3 tiers
meta-meta-meta-review PR#123          # 4 tiers

# METHOD 2: --tiers flag (any count)
review --tiers 5 PR#123               # 5 tiers
review --tiers 10 ./docs/API.md       # 10 tiers
review --tiers 100 ./design/schema    # 100 tiers (if needed)

# METHOD 3: --meta flag repetition (any count)
review --meta PR#123                  # 2 tiers
review --meta --meta PR#123           # 3 tiers
review --meta --meta --meta PR#123    # 4 tiers
review --meta --meta --meta --meta PR#123  # 5 tiers

# WITH CUSTOM PHASE COUNT
review -3 PR#789                      # 1 tier, 3 phases each
review --tiers 5 -3 PR#789            # 5 tiers, 3 phases each
review --meta --meta -3 PR#789        # 3 tiers, 3 phases each
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

## Tiered Reviews

Each `meta-` prefix adds another review tier. Each tier uses different workers to challenge the previous tier's findings.

### 1-Tier: `review`
```bash
review PR#123                # Workers analyze, Arbiter synthesizes
review ./docs/API.md         # Works on any artifact
```

**Flow:**
1. Workers analyze the artifact
2. Arbiter synthesizes findings
3. Results saved to memory

### 2-Tier: `meta-review`
```bash
meta-review PR#123           # Review + Re-review
meta-review ./docs/API.md    # Higher confidence
```

**Flow:**
1. **Tier 1:** Workers analyze, Arbiter synthesizes findings
2. **Tier 2:** Different workers challenge those findings
3. **Tier 2:** New Arbiter validates review quality
4. Result: Double-checked, high-confidence findings

### 3-Tier: `meta-meta-review`
```bash
meta-meta-review PR#123      # Triple-checked
meta-meta-review ./design/*  # Ultra-thorough vetting
```

**Flow:**
1. **Tier 1:** Workers analyze, Arbiter synthesizes
2. **Tier 2:** Different workers challenge findings
3. **Tier 3:** Third set of workers challenge tier 2's findings
4. **Tier 3:** Final arbiter validates the entire chain

### 4+-Tier: `meta-meta-meta-review`
```bash
meta-meta-meta-review PR#789  # 4 tiers (extreme vetting)
```

**When to use each:**
- `review` — Routine code, docs, designs
- `meta-review` — Critical code, important decisions, security
- `meta-meta-review` — Breaking changes, major APIs, compliance
- `meta-meta-meta-review` — Extremely high-risk changes

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
| `-N` | N-phase per tier (e.g., `-3` for 3 phases each) |
| `review` | 1-tier (workers → arbiter) |
| `meta-review` | 2-tiers (review + re-review) |
| `meta-meta-review` | 3-tiers (review + 2× re-review) |
| `meta-meta-meta-review` | 4-tiers |
| Each `meta-` | Adds another review tier |
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
# 1-TIER REVIEW
review PR#123                    # Standard
review ./docs/API.md             # Review docs
review -3 PR#456                 # 3-phase

# 2-TIER META-REVIEW
meta-review PR#123               # Review + re-review
meta-review ./docs/API.md        # Docs: 2-tier
meta-review ./design/feature.md  # Design: 2-tier
meta-review -3 PR#456            # 3-phase × 2 tiers

# 3-TIER ULTRA-THOROUGH
meta-meta-review PR#789          # 3-tier review
meta-meta-review ./ADR/0001-*    # Decision: 3-tier

# 4-TIER EXTREME VETTING
meta-meta-meta-review PR#999     # Ultra-critical PR

# ANALYSIS
query-memory.py semantic-search "review"
query-memory.py hybrid-search "meta-review"
memory-synthesis.py              # All insights
```

**Tier Scaling:**
- More `meta-` = higher confidence, more cost, takes longer
- Each tier uses different models (workers rotate)
- Each tier challenges the previous tier's findings
- All tiers saved to memory (searchable)

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
