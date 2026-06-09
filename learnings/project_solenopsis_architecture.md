---
name: project-solenopsis-architecture
description: Three-tier Salesforce integration framework with dependency chain JCommons → SOAP → Session
metadata: 
  node_type: memory
  type: project
  originSessionId: a575e68b-00c2-4b26-9226-a3cc67abcc1d
---

User maintains a three-tier Salesforce SOAP integration framework:

**Architecture:**
```
FlossWare JCommons (foundation utilities)
    ↓ (dependency)
Solenopsis SOAP (Salesforce SOAP clients)
    ↓ (dependency)
Solenopsis Session (auth & session management)
```

**Current Versions (as of 2026-05-15):**
- FlossWare JCommons: 1.14 (renamed from Commons)
- Solenopsis SOAP: 1.11
- Solenopsis Session: 1.16

**Why:** Changes in Commons can affect SOAP and Session. Dependency updates cascade upward. Version bumps happen via CI/CD and cause git rebase conflicts.

**How to apply:**
- When updating Commons, check if SOAP and Session need version bumps
- When updating SOAP, check if Session needs version bumps
- Use `git pull --rebase github main` to handle CI/CD version bump conflicts
- Maintain consistency: if Commons is 1.10, SOAP should reference 1.10+, etc.

**CI/CD Behavior:**
- Pushes to main trigger auto version bump and deploy to packagecloud.io
- Auto-commits are tagged with "[ci skip]" to prevent loops
- Creates tags automatically (1.10, 1.11, etc.)

This is an active project under continuous improvement, not legacy maintenance.
