---
name: feedback-naming-conventions
description: User prefers lowercase project names and main branch (not master) for modern Git practices
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5069eeef-3c97-47e3-b069-3f9236a0ac7c
---

Use lowercase for project and repository names, and use "main" as the default Git branch instead of "master".

**Why:**
User explicitly requested renaming "Metadata" to "metadata" (lowercase) and migrating from "master" to "main" branch. This reflects modern naming conventions and inclusive Git practices.

**How to apply:**
- When creating or referencing repositories, use lowercase names
- Default branch should always be "main" not "master"
- Update SCM URLs and documentation to reflect lowercase naming
- When migrating existing projects, rename both locally and on GitHub

**Examples:**
- Repository: github.com/solenopsis/metadata (not Metadata)
- Branch: main (not master)
- Maven artifact: org.solenopsis:metadata
