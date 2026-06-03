# doc-review

Review project documentation using worker/arbiter pattern to identify issues with accuracy, completeness, clarity, consistency, and freshness. Auto-creates GitLab issues for problems found.

## What it does

Launches a multi-agent workflow that:
1. **Discovery**: Finds all documentation files (*.md, docs/*, README, etc.)
2. **Parallel Review**: 5 specialized reviewers analyze in parallel
   - Accuracy Reviewer: Verifies code examples, file paths, API signatures
   - Completeness Reviewer: Checks for missing sections, incomplete docs
   - Clarity Reviewer: Evaluates readability, sentence length, structure
   - Consistency Reviewer: Checks terminology, formatting, cross-references
   - Freshness Reviewer: Detects stale references, outdated screenshots
3. **Arbiter Synthesis**: Consolidates findings, prioritizes by severity
4. **Issue Creation**: Auto-creates GitLab issues for CRITICAL/HIGH findings

## Usage

```bash
# Review all documentation
/doc-review

# Review specific file
/doc-review README.md

# Review directory
/doc-review docs/

# Dry run (no issues created)
/doc-review --dry-run

# Set severity threshold (only report HIGH+)
/doc-review --severity high

# Auto-fix minor issues (typos, formatting)
/doc-review --auto-fix
```

## Configuration

The workflow uses consensus and execution strategies from `~/.claude/model-config.json`.

**Configure strategies:**
```bash
# Set consensus strategy (how workers decide)
python scripts/model-manager.py set-strategies doc-review --consensus majority

# Set execution strategy (how workers run)
python scripts/model-manager.py set-strategies doc-review --execution cascade

# Set both at once
python scripts/model-manager.py set-strategies doc-review \
  --consensus weighted \
  --execution batched

# List all available strategies
python scripts/model-manager.py list-strategies
```

**Consensus Strategies:**
- `single` (default) - One arbiter judges all workers (1x cost)
- `majority` - Simple majority vote, no arbiter (0.7x cost)
- `weighted` - Confidence-based voting (0.8x cost)
- `rotating` - Democratic, each AI judges others (3x cost)
- `pairwise` - Tournament-style pairs (1.5x cost)

**Execution Strategies:**
- `parallel` (default) - All workers simultaneously (fastest)
- `sequential` - One at a time (resource-friendly)
- `batched` - Process in batches of 2 (balanced)
- `cascade` - Fast workers first, escalate if needed (adaptive, 0.3-1x cost)
- `weighted_parallel` - Priority-based parallel (fast initial feedback)

## Output

Returns structured report with:
- **Critical Issues**: Broken code examples, missing required sections
- **High Issues**: Stale references, incorrect API docs
- **Medium Issues**: Clarity problems, inconsistent terminology
- **Low Issues**: Typos, minor formatting

## Examples

```bash
# Before release, verify all docs
/doc-review --severity medium

# Quick check on README
/doc-review README.md

# Fix obvious issues automatically
/doc-review --auto-fix --dry-run  # preview first
/doc-review --auto-fix             # apply fixes
```

## Requirements

- GitLab project (for issue creation)
- Code must be in git repository (for freshness checks)

## Cost

Typical review of 30-50 doc files:
- Tokens: ~50K (5 workers + arbiter)
- Time: 3-5 minutes
- Cost: ~$0.50-$1.00

## See Also

- `/code-review` - Review code instead of docs
- `/autoresolve` - Auto-resolve TODOs/issues
- `AUTO_DOC_REVIEW.md` - Full documentation review guide
