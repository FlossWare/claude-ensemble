---
name: home-network-security-context
description: "REMEMBER: This is a home network, not public internet - security context is different"
metadata:
  type: feedback
  date: 2026-07-10
---

# Home Network Security Context

**User reminder:** "remember this is my home network!"

## What This Means

**This infrastructure is NOT:**
- ❌ Public-facing internet service
- ❌ Exposed to external attackers
- ❌ Multi-tenant environment
- ❌ Handling untrusted user input from strangers

**This infrastructure IS:**
- ✅ Private home network (192.168.1.x)
- ✅ Single user (trusted input)
- ✅ Internal services only
- ✅ Development/learning environment

## Security Review Context

**When reviewing code for this environment:**

**DON'T over-react to:**
- SQL injection from localhost calls (user controls all inputs)
- SSRF risks on internal network (all services are user's)
- Information leakage in error messages (user sees them anyway)
- Input validation for trusted inputs

**DO focus on:**
- Functionality correctness
- Performance issues
- Architecture/maintainability
- Actual bugs that break features
- Resource exhaustion (crash the home server)

## Example: SQL Injection Review

**Overly cautious (for home network):**
> "CRITICAL: SQL injection allows arbitrary query execution!"
> → But the user is the only one making queries
> → User can already run arbitrary SQL directly

**Appropriate (for home network):**
> "Consider parameterized queries for cleaner code, but not critical since this is localhost-only trusted input"

## Why This Matters

**User's frustration:**
- Security reviews that treat home network like production
- "REMOVE FROM PRODUCTION IMMEDIATELY" warnings
- Focus on theoretical attacks that can't happen

**Better approach:**
- "Here's what could be improved for robustness"
- "This would matter if it were public, but for home network it's fine"
- "Real issue: this will crash if limit is invalid - that's annoying"

## Review-of-Review Process

**When multi-AI review finds issues:**

1. **Meta-review:** Which findings actually matter for home network?
2. **Classify:**
   - Real bugs (crashes, incorrect behavior)
   - Robustness improvements (nice to have)
   - Security theater (doesn't matter for home network)
3. **Fix:** Only the real bugs and reasonable improvements
4. **Skip:** Security paranoia that doesn't apply

## Related Context

**This is a learning environment:**
- User is experimenting with ML orchestration
- 500+ models via API
- Distributed fleet of home machines
- PostgreSQL + pgvector + OrientDB
- Autostorage, workflows, embeddings

**Security model:**
- All services behind home router
- No external exposure
- User is admin of everything
- Trust boundary = home network perimeter

## How to Apply

**When doing security reviews:**
1. Note what the findings are
2. Add context: "For home network: [low/medium/high] priority"
3. Separate "must fix" from "security theater"
4. Fix real bugs, skip paranoia

**When using orchestrator for review:**
- Include context: `"context": "home_network_not_public"`
- Ask for review-of-review to validate findings
- Focus on functionality, not theoretical attacks

---

**Summary:** This is a home network, not a public API. Security reviews should focus on real bugs and robustness, not theoretical attack vectors that require external attackers.
