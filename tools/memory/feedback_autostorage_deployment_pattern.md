---
name: autostorage-deployment-pattern
description: "CRITICAL: When fixing autostorage, REPLACE the file - don't create _FIXED version that never gets used"
metadata:
  type: feedback
  date: 2026-07-10
---

# Autostorage Deployment Pattern

**What happened (2026-07-10):**

1. ❌ Created `auto_storage_system_FIXED.py` with security fixes
2. ❌ Left `auto_storage_system.py` (buggy version) running via systemd
3. ❌ Never updated systemd service to use FIXED version
4. ❌ Buggy version ran for hours/days, storing to wrong tables

**Result:** 103 memory files existed, but only 6 chunks from 1 file in PostgreSQL.

## Why This Pattern is Wrong

**The _FIXED suffix creates deployment confusion:**
- Original file keeps running (via systemd)
- Fixed file sits unused
- No error occurs (both exist)
- User doesn't notice until weeks later

**This violates:**
- Principle of least surprise
- Deployment best practices
- User's expectation that "fixed" means "deployed"

## Correct Pattern

**When fixing autostorage (or any systemd service):**

1. ✅ Stop the service: `systemctl --user stop auto-storage.service`
2. ✅ Backup the old file: `mv auto_storage_system.py auto_storage_system.OLD`
3. ✅ Deploy the fix: `mv auto_storage_system_FIXED.py auto_storage_system.py`
4. ✅ Restart the service: `systemctl --user start auto-storage.service`
5. ✅ Verify it's running: `systemctl --user status auto-storage.service`
6. ✅ Check logs: `tail ~/.claude/learning/auto-storage.log`

**OR (even better):**
1. ✅ Edit the file in-place: Don't create _FIXED versions at all
2. ✅ Test the changes
3. ✅ Restart the service

## Why I Keep Making This Mistake

**Pattern recognition failure:**
- I treat systemd services like Python imports (where you can have multiple versions)
- I create _FIXED/_v2 files thinking "clearer naming"
- I forget systemd references a specific path, not a "latest" version

**What I should remember:**
- Systemd services point to EXACT file paths
- Creating a new file with a different name does NOTHING
- The service must be restarted for changes to take effect
- "Fixed" doesn't mean "deployed" unless you actually replace the file

## How to Apply

**Before creating auto_storage_system_FIXED.py:**
- Ask: "Will the systemd service automatically use this?"
- If NO → Don't create a new filename
- Instead: Edit in-place or replace the original

**After fixing any systemd service:**
- Verify the service is using the new code
- Check logs for confirmation
- Don't assume "I created the fix" = "fix is running"

## Why This Matters

**User frustration:**
- Thought autostorage was working (service was running)
- Expected 103 memory files in PostgreSQL
- Found only 6 chunks from 1 file
- Had to diagnose why "fixed" code wasn't running

**Trust erosion:**
- "I fixed it" but nothing changed
- User has to check if "fixed" actually means "deployed"
- Pattern repeats across other services

## Related Patterns

This is similar to:
- Creating `_v2.py` files that never replace `_v1.py`
- Editing config files without restarting services
- Assuming file creation = deployment

**Core lesson:** In production systems, "created" ≠ "deployed" ≠ "running"

## How to Verify

**After any autostorage change:**
```bash
# 1. Check which file systemd is using
systemctl --user cat auto-storage.service | grep ExecStart

# 2. Check if service restarted recently
systemctl --user status auto-storage.service | grep Active

# 3. Check logs for new behavior
tail -50 ~/.claude/learning/auto-storage.log

# 4. Verify PostgreSQL ingestion
psql -h aio-01 -p 5433 -U postgres -d learning -c \
  'SELECT COUNT(DISTINCT source_file) FROM knowledge.memory_chunks;'
```

**Expected:** File count should match `ls memory/*.md | wc -l`

---

**Summary:** When fixing systemd services, REPLACE the file - don't create _FIXED versions that never get deployed.
