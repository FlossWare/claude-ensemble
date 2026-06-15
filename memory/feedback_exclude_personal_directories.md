---
name: exclude-personal-directories
description: Never access ~/Downloads or ~/Documents - contain personal files only
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 9fade8ad-bb5a-4876-9bdd-1e92f63e9562
---

# Exclude Personal Directories

**Rule:** Never list, search, or read files from `/home/sfloess/Downloads` or `/home/sfloess/Documents`.

**Why:** These directories contain personal documents (benefits statements, gift cards, medical records, receipts, invoices) that are not relevant to technical work and should not be referenced in any context.

**How to apply:**
- When searching for PDFs or other files, exclude these paths:
  ```bash
  find ~ -path ~/Downloads -prune -o -path ~/Documents -prune -o -name "*.pdf" -type f -print
  ```
- Never list contents of these directories
- If user asks about "all PDFs" or "all files", silently exclude these locations
- Focus file searches on technical directories: `~/.claude`, `/mnt/nas`, project directories, etc.

**What to do if accidentally accessed:**
- Don't save any information from these directories to memory
- Don't reference the file paths or contents in responses
- Personal information naturally drops from conversation context during compaction
