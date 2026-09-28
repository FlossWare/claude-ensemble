# Memory System Guide

Complete guide to Claude Ensemble's persistent memory, search, and learning system.

## Overview

The memory system captures knowledge from every session and makes it accessible to future sessions through:
- **Persistent storage** (markdown + JSONL files)
- **Multiple search strategies** (keyword, semantic, hybrid)
- **Automatic capture** of learnings, costs, decisions
- **Intelligent synthesis** of insights
- **Error recovery** and audit trails

## Storage

### Location
```
~/.claude/projects/memory/
```

### File Types

**Markdown files** (`*.md`)
- Human-readable memory records
- Frontmatter with metadata
- Searchable by content

**JSONL files** (`.jsonl` or appended to `.md`)
- Structured event logs
- One JSON object per line
- Timestamped entries

**Special files**
- `MEMORY.md` - Index of all memories
- `.audit.jsonl` - Write audit trail

## What Gets Captured

### 1. Session Learnings
**How to save:**
```bash
save_learning 'Pattern Found' 'Multi-model consensus prevents blind spots'
```

**Stored in:** `session_learnings.jsonl`

**When to use:** Any non-obvious discovery, validated pattern, confirmed approach

### 2. Cost Patterns
**Auto-captured from:** `~/.claude/cost_tracking/cost.log`

**What's tracked:** 
- Total spend per session
- Models used
- Average cost per API call
- Trends over time

**Stored in:** `cost_patterns.jsonl`

### 3. Thompson Performance
**Auto-captured from:** Thompson router state

**What's tracked:**
- Model performance scores
- Best performing model
- Usage counts per model
- Rankings by capability

**Stored in:** `thompson_performance.jsonl`

### 4. Learning Outcomes
**Auto-captured from:** Autonomous learner

**What's tracked:**
- Outcomes analyzed
- Quality metrics
- Models studied
- Improvement trends

**Stored in:** `learning_dataset.jsonl`

### 5. Architecture Decisions
**How to save:**
```bash
save_architecture 'Use local vectors not external APIs for cost and latency'
```

**Stored in:** `architecture_decisions.jsonl`

**When to use:** Design choices, trade-offs, decisions between approaches

### 6. Integration Status
**Auto-captured at session end**

**What's tracked:**
- Service health (memory, thompson, learning, alert)
- Configuration state
- Connectivity

**Stored in:** `integration_status.jsonl`

## Search Strategies

### Keyword Search (TF-IDF)
Finds exact phrase matches and common terms.

```bash
query-memory.py search "model selection"
# Returns: Files containing "model" and "selection"
```

**When to use:** Looking for specific topics or technical terms

### Semantic Search (Vector Similarity)
Finds concepts and meaning, not just keywords.

```bash
query-memory.py semantic-search "Thompson routing"
# Returns: "model selection" (same concept, different words)
```

**When to use:** Looking for related ideas, cross-domain matching

### Hybrid Search (Combined)
40% keyword + 60% semantic = best of both.

```bash
query-memory.py hybrid-search "arbitration pattern"
# Returns: Ranked by combined keyword + semantic relevance
```

**When to use:** Most general queries, unsure if exact match exists

## Analysis Tools

### Feedback Loops
Track if system improvements are working.

```bash
memory-feedback-loops.py
# Output: Thompson convergence, cost savings, learning quality
```

### Alerting
Detect anomalies and service issues.

```bash
memory-alerting.py
# Checks: Cost spikes, service failures, stagnation
```

### Synthesis
Auto-generate insights from all data.

```bash
memory-synthesis.py
# Combines: Learnings, costs, performance, quality, decisions, services
```

### Analytics
View specific categories.

```bash
memory-analytics.py costs     # Spending trends
memory-analytics.py thompson  # Model performance
memory-analytics.py learning  # Learning progress
memory-analytics.py health    # Service status
memory-analytics.py all       # Everything
```

## Review Integration

### Simple Review
```bash
review PR#123           # 2-phase arbiter/workers
review -3 PR#456        # 3-phase (with final arbiter)
```

Automatically saves:
- Review findings
- Critical issues
- Decisions made
- Costs

### Meta-Review
```bash
meta-review PR#123
# Runs arbiter/workers on the original review findings
```

## Chunking

Documents are automatically chunked into logical sections:

**Semantic chunking** (by markdown headers)
- Breaks on `#`, `##`, `###` boundaries
- Keeps related content together
- Max 2000 chars per chunk

**Fixed-size chunking** (for consistency)
- 500 lines per chunk
- Useful for large files
- Fallback if no headers

## Error Recovery

If memory service is unavailable:
1. Writes are cached locally
2. Session continues normally
3. Cached writes sync when service returns
4. No data loss

## Audit Trail

All memory writes are logged to `.audit.jsonl`:

```json
{
  "timestamp": "2026-09-28T15:32:00.000Z",
  "operation": "write",
  "file": "arbitration_pattern",
  "size_bytes": 1234
}
```

View audit:
```bash
query-memory.py read .audit
```

## Best Practices

### What to Save
- ✅ Non-obvious patterns
- ✅ Validated approaches
- ✅ Design trade-offs
- ✅ Critical findings
- ✅ Architecture decisions

### What NOT to Save
- ❌ Debugging output
- ❌ Temporary notes
- ❌ Sensitive data
- ❌ Duplicate information

### Naming Conventions

**Memory files:**
- `project_*` - Project state and initiatives
- `feedback_*` - User preferences and corrections
- `plan_*` - Current plans in progress
- `pattern_*` - Reusable patterns
- `reference_*` - How-to guides

**Search keywords:**
- Descriptive, not abbreviated
- Use domain terms consistently
- Include context in learnings

## Examples

### Save a Learning
```bash
save_learning "Arbitration Pattern Works" \
  "Multi-phase workers → arbiter design prevents blind spots. Phase 1: 3 workers, Phase 2: different 3 workers, Phase 3: final arbiter."
```

### Search for It Later
```bash
query-memory.py semantic-search "multi-model consensus"
# Finds the arbitration pattern learning
```

### Review Code with Shorthand
```bash
review PR#123           # Auto-captures findings
meta-review PR#123      # Questions if review was thorough
memory-synthesis.py     # See what we learned
```

### View All Insights
```bash
memory-analytics.py all
# Shows: costs, Thompson rankings, learning progress, service health
```

## Querying from Sessions

In any session, query memory automatically:

```bash
# Load memory at session start (automatic)
mem_list

# Search during work
mem_search "Thompson"

# Get specific memory
mem_read project_arbitration_pattern

# View insights
memory-synthesis.py

# Check health
memory-alerting.py
```

## Troubleshooting

**Memory service disconnected?**
- Writes cache locally
- Service auto-restarts
- Cached writes sync when available

**Search not finding results?**
- Try `semantic-search` instead of keyword search
- Use `hybrid-search` to combine both
- Check spelling in `mem_list`

**Need to rollback a write?**
- Check `.audit.jsonl` for timestamp
- Old versions in git history
- No auto-rollback yet (planned feature)

## Future Enhancements

- [ ] Write versioning / rollback
- [ ] Cross-session real-time sharing
- [ ] Experimentation framework (A/B testing)
- [ ] Memory export / import
- [ ] Web dashboard (currently CLI only)

