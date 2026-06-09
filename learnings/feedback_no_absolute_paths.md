---
name: feedback_no_absolute_paths
description: "Never use absolute paths or username references in documentation or memory"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f26c00bc-2e0f-4df4-8b1f-d7888af7de1f
---

Do not refer to absolute paths, home directories, or usernames in any documentation, memory, or communication.

**Why:** User requested no absolute home directory paths or username references - for privacy, security, and portability reasons.

**How to apply:**
- Use `~/` instead of `/home/username/`
- Use relative paths like `../jcollections/` when referring to sibling projects
- Use generic descriptions like "local development directory" instead of specific paths
- Keep file paths out of documentation where possible
- When working with files, use the paths but don't document or save them to memory
