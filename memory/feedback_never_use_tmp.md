---
name: never-use-tmp
description: "NEVER use /tmp for any data - it's tmpfs (RAM-backed) and runs out of inodes/space constantly"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 87f86bea-63f4-4075-afa5-1899ccbce831
---

NEVER use /tmp for storing data, e2e test artifacts, extracted files, or any working data.

**Why:** /tmp is tmpfs on this machine (RAM-backed, 32GB). It runs out of inodes (1M limit) and space constantly due to accumulated repo clones from previous sessions. User has said "dont use /tmp!" at least 3 times across sessions.

**How to apply:** Use /home filesystem for all working data. For pxe-os e2e tests, use `e2e-data/` directory within the project. For temp files needed by scripts, use a subdirectory within the project or /home/sfloess/Development/. The ONLY thing that should use /tmp is Claude Code's internal task directory (which we can't control).
