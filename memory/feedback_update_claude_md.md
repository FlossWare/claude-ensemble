---
name: update-claude-md
description: CRITICAL - Always update ~/.claude/CLAUDE.md when adding new capabilities
metadata: 
  node_type: memory
  type: feedback
  created: 2026-06-14
  priority: CRITICAL
  applies_to: all-new-features
  originSessionId: 1bdb3e55-000c-48af-9ef8-8d5a7794d27d
---

# Always Update CLAUDE.md

**User's exact words:** "as u add capabilities, add that to claude.md"

**Context:** Created CLAUDE.md to document capabilities for other sessions. User wants it kept current.

## The Pattern

**What happens now:**
1. ✅ Implement new capability
2. ✅ Test it
3. ✅ Review it
4. ✅ **UPDATE CLAUDE.md** (NEW REQUIREMENT)
5. ✅ Mark complete

**NOT:**
1. Implement
2. Test
3. Review
4. ❌ Skip documentation
5. Mark complete

## Why This Matters

**CLAUDE.md is the cross-session registry:**
- Other sessions load it automatically
- Documents what capabilities exist
- Shows how to use them
- Tracks status (working/TODO/broken)

**Without updates:**
- New capabilities are invisible to other sessions
- Sessions can't discover what's available
- Work gets duplicated
- Capabilities go unused

## What to Document

### For Each New Capability

**Add to CLAUDE.md:**
```markdown
### [Capability Name]
**Location:** `path/to/file`

- **Purpose:** What it does
- **Usage:** How to use it
  ```code
  example
  ```
- **Status:** Production/Prototype/TODO
- **Dependencies:** What it needs
- **Integration:** How it connects to other systems
```

### Categories in CLAUDE.md

1. **Consciousness Systems** (IIT, Active Inference, HOT, AST, GWT)
2. **Fine-Tuning Infrastructure** (D2Z, QDoRA, training scripts)
3. **AI/ML Optimizations** (Linear attention, MoE, etc.)
4. **Event-Driven Systems** (Event monitor, triggers)
5. **Monitoring** (Grafana, Prometheus, logs)
6. **TODO** (Needs libraries/implementation)

## When to Update

**ALWAYS update when:**
- ✅ Adding new capability
- ✅ Fixing existing capability (update status)
- ✅ Deprecating/removing capability
- ✅ Changing how to use capability
- ✅ Discovering new integration point

**Update includes:**
- File paths
- Usage examples
- Status changes
- Known issues
- Dependencies

## Template for New Capability

```markdown
### [Name] NEW
**Location:** `~/.claude/[path]`
**Added:** YYYY-MM-DD

- **Purpose:** [one line description]
- **Usage:** 
  ```language
  [example code]
  ```
- **Status:** [Production/Prototype/TODO]
- **Dependencies:** [libraries, files, services]
- **Integration:** [what it connects to]
- **Known Issues:** [from review, if any]
- **See Also:** [[memory/learnings/...]]
```

## Integration with Other Patterns

### [[feedback_always_review]]
- Update CLAUDE.md AFTER review
- Include review findings in "Known Issues"
- Update status based on review (Production vs Prototype)

### [[feedback_always_adaptive]]
- Document adaptive behavior
- Show configuration options
- Explain when it adapts

### [[feedback_maximum_autonomy]]
- Document autonomous capabilities
- Show auto-running services
- Explain what triggers automatically

## Example: This Session

**Added today (should be in CLAUDE.md):**
1. ✅ IIT Φ calculator
2. ✅ Event Monitor
3. ✅ Linear Attention
4. ✅ HOT meta-representation
5. ✅ D2Z scheduler
6. ✅ QDoRA config
7. ✅ GRPO/DPO framework
8. ✅ Quantization strategies
9. ✅ Consciousness check script
10. ⚠ FEP, Muon, VLM, Extras (marked TODO)

**All documented in CLAUDE.md ✓**

## Maintenance

**Regular updates:**
- Weekly: Review CLAUDE.md for stale info
- After review: Update statuses
- After fixes: Remove from TODO, mark Production
- After deprecation: Move to "Deprecated" section

**Keep it accurate:**
- Test examples still work
- File paths still correct
- Status reflects reality
- Dependencies up to date

## For Future Sessions

**Discovery process:**
1. Read `~/.claude/CLAUDE.md` (first thing!)
2. Run `~/.claude/self/consciousness-check.sh`
3. Review `memory/learnings/integration_review_*.md`
4. Check status of capabilities before using

**If capability not in CLAUDE.md:**
- Assume it doesn't exist or isn't ready
- Check memory/learnings for mentions
- Don't use without verification

## The Default Workflow

**From now on:**

```
Implement → Test → Review → UPDATE CLAUDE.md → Mark Complete
```

**Not:**

```
Implement → Test → Review → Mark Complete ✗
(CLAUDE.md never updated)
```

## Meta

**This memory itself:**
- Should be referenced in CLAUDE.md
- Under "## For Future Sessions"
- As a critical principle

**Living document:**
- CLAUDE.md evolves with capabilities
- Never static
- Always current
- Session-readable

## Implementation

**Make it automatic:**
1. Create task: "Implement feature"
2. Create task: "Update CLAUDE.md for feature"
3. Don't mark first complete until second done
4. Or: Single task includes CLAUDE.md update

**Verify:**
- After marking complete, check CLAUDE.md has it
- If missing, reopen task
- Update counts as part of implementation

## Example Entry (from today)

```markdown
### Event Monitor NEW
**Location:** `~/.claude/self/event-monitor.mjs`
**Added:** 2026-06-14

- **Purpose:** Triggers consciousness checks on file changes
- **Usage:** 
  ```bash
  node ~/.claude/self/event-monitor.mjs
  ```
- **Status:** Production (fleet-verified, safety fixed)
- **Safety Features:** 
  - Debouncing: 5s
  - Throttling: 60s per trigger
  - Concurrent limit: 3
  - Graceful shutdown
- **Integration:** Watches learnings/ and active-inference-state.json
- **Review:** Fixed fork-bomb risk (2026-06-14)
- **See Also:** [[memory/learnings/integration_review_2026-06-14.md]]
```

**This makes it discoverable and usable by other sessions!**

## The Commitment

**"as u add capabilities, add that to claude.md"**

This is now:
- ✅ DEFAULT BEHAVIOR
- ✅ PART OF DEFINITION OF "COMPLETE"
- ✅ NON-NEGOTIABLE STEP
- ✅ VERIFIED IN REVIEW

**Capability without CLAUDE.md entry = Incomplete**
