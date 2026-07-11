---
name: use-rsync
description: "Always use rsync for file copies, not scp or cp"
metadata:
  type: feedback
  date: 2026-07-10
---

# Use rsync for File Copies

**User feedback:** "yes and use rsync. remember that"

## Context

I was trying to copy 849 PDFs (7.2GB) from NAS to aio-01 and tried multiple methods:
- rsync (correct)
- scp (wrong - slow, no resume)
- find + rsync (correct but failed due to server-ap routing issue)

**User preference:** Always use rsync

## Why rsync

✅ **Advantages:**
- Resumes on failure (--partial)
- Efficient (only copies changes)
- Preserves permissions/timestamps
- Progress reporting
- Network efficient (delta transfer)

❌ **Don't use:**
- scp (no resume, copies everything)
- cp (local only, no network)

## Correct rsync pattern

```bash
rsync -avh --partial --progress --timeout=300 \
  /source/path/ \
  user@host:/dest/path/
```

**Flags:**
- `-a` = archive (preserve permissions, recursive)
- `-v` = verbose
- `-h` = human-readable sizes
- `--partial` = keep partial files (resume)
- `--progress` = show progress
- `--timeout=300` = 5min timeout per file

## Related

- Server-ap had routing issue (2026-07-10) - caused rsync failures
- After reboot, rsync works fine

---

**Remember:** rsync is the standard tool for file copies.
