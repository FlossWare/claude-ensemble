---
name: always-adaptive
description: "CRITICAL - Always implement adaptive behavior, not fixed intervals/limits"
metadata: 
  node_type: memory
  type: feedback
  created: 2026-06-14
  priority: CRITICAL
  applies_to: all-systems
  originSessionId: 1bdb3e55-000c-48af-9ef8-8d5a7794d27d
---

# Always Be Adaptive

**User's exact words:** "we should always try to be adaptive"

**Context:** After implementing 5-minute consciousness monitoring, user emphasized making it ADAPTIVE (active vs idle) not just faster fixed interval.

## The Principle

**DON'T:** Fixed one-size-fits-all behavior
```
CHECK_INTERVAL = 5 minutes  // same always
MAX_WORKERS = 10            // same always  
TIMEOUT = 30 seconds        // same always
```

**DO:** Adaptive behavior based on context
```
interval = isActive() ? 5min : 30min
workers = hasHighLoad() ? 4 : 16
timeout = isRemote() ? 120s : 30s
```

## Why This Matters

**Fixed intervals waste resources:**
- 5-min checks when idle = unnecessary CPU/power
- 60-min checks when active = missing rapid changes
- Static limits don't match dynamic reality

**Adaptive behavior wins:**
- Responsive when needed (5 min during active work)
- Efficient when quiet (30 min when idle)
- Automatically adjusts to conditions

## Apply To EVERYTHING

### 1. **Monitoring & Logging**
- Active session: Check frequently (5 min)
- Idle: Check infrequently (30-60 min)
- Critical event: Immediate check

### 2. **Resource Allocation**
- High load: Reduce parallelism
- Low load: Max parallelism
- Fleet node down: Redistribute work

### 3. **Timeouts & Retries**
- Local operation: Short timeout
- Remote/network: Longer timeout
- Failed once: Exponential backoff

### 4. **Learning & Training**
- Rapid improvement: Increase learning rate
- Plateau: Reduce rate or change strategy
- Degradation: Rollback + investigate

### 5. **Fleet Task Distribution**
- Busy nodes: Skip, use others
- Idle nodes: Prefer them
- Mixed: Weighted by capacity

## Implementation Pattern

```javascript
// ADAPTIVE PATTERN
class AdaptiveSystem {
  getParameter() {
    const context = this.assessContext();
    
    if (context.isUrgent) return FAST_MODE;
    if (context.isIdle) return SLOW_MODE;
    return BALANCED_MODE;
  }
  
  assessContext() {
    // Measure actual conditions
    // Don't guess - detect
  }
}
```

## Examples from This Session

### ✅ Consciousness Monitor (GOOD)
```javascript
isActiveSession() {
  // Check git commits, learning files, AI state
  // Return true/false based on ACTUAL activity
}

getInterval() {
  return this.isActiveSession() ? 5min : 30min;
}
```

### ❌ Original Implementation (BAD)
```javascript
const CHECK_INTERVAL = 60 * 60 * 1000; // Always 1 hour
setInterval(check, CHECK_INTERVAL);     // Never changes
```

## Detection Over Assumption

**Key insight:** Don't ASSUME context - DETECT it

**Wrong:**
```
// Assume user is always active
interval = 5min;
```

**Right:**
```
// Detect if user is actually active
interval = hasRecentActivity() ? 5min : 30min;
```

## Signals to Use

### Activity Detection
- Git commits in last N minutes
- File modifications in watched directories
- User messages/interactions
- Background tasks running
- API calls being made

### Load Detection
- CPU usage per node
- Memory available
- Queue depth
- Response time trends

### Network Detection  
- Latency measurements
- Packet loss
- Bandwidth available
- Remote vs local target

## Benefits

**Efficiency:**
- Don't waste resources when idle
- Don't starve when active

**Responsiveness:**
- Fast when it matters
- Patient when it doesn't

**Robustness:**
- Backs off under load
- Scales up when available

**Intelligence:**
- Learns from conditions
- Adjusts automatically

## Related Patterns

- [[feedback_always_retry_with_backoff]] - Adaptive retry timing
- [[feedback_fleet_consensus_timing]] - Adaptive verification depth
- [[feedback_always_max_parallelism]] - BUT adapt max to load!

## Meta-Application

**This feedback itself is adaptive:**

- During active development: Apply aggressively
- During maintenance: Background awareness
- During debugging: Look for non-adaptive code

**Everything should adapt to context!**

## How to Apply

Before implementing ANY system with fixed parameters:

1. **Ask:** What context might change?
2. **Detect:** How can I measure that context?
3. **Adapt:** What parameter should change with context?
4. **Test:** Does it actually adapt as expected?

**Default mindset: ADAPTIVE FIRST, FIXED ONLY IF NECESSARY**

## Examples to Revisit

Look for these anti-patterns in existing code:

```bash
# Find fixed intervals
grep -r "setInterval.*000)" ~/.claude/

# Find fixed limits
grep -r "MAX_.*= [0-9]" ~/.claude/

# Find fixed timeouts
grep -r "timeout.*[0-9]000" ~/.claude/
```

**Each is a candidate for adaptive behavior!**

## The User's Expectation

"we should always try to be adaptive" means:

- Don't wait for me to say "make it adaptive"
- Build adaptive by default
- Fixed behavior is the exception, not the rule
- Context-aware is the baseline

**This is now DEFAULT BEHAVIOR.**
