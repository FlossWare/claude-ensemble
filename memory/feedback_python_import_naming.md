---
name: python-import-naming
description: Always use underscores (not hyphens) in Python filenames for importability
metadata: 
  node_type: memory
  type: feedback
  date: 2026-07-01
  originSessionId: e8c8e210-7731-4cf4-b2b1-d1559c501374
---

# Python Import Naming Convention

**Rule:** Always use underscores in Python filenames, never hyphens.

**Why:** Python import system cannot import modules with hyphens in filenames.

**Example:**
```python
# ❌ WRONG - cannot import
# File: axial-attention.py
from axial-attention import AxialAttention  # ImportError!

# ✅ CORRECT - can import
# File: axial_attention.py
from axial_attention import AxialAttention  # Works!
```

**Impact discovered (2026-06-15):**
- 35 implementations blocked by hyphenated filenames
- Usability: 28% → 41% after renaming
- All files in `~/.claude/self/*.py` affected

**How to apply:**

When creating new Python files:
```bash
# ✅ Use underscores
touch my_module.py
touch attention_mechanism.py
touch transformer_optimizer.py

# ❌ Never use hyphens
# touch my-module.py  # WRONG
```

When renaming existing files:
```bash
# Rename all hyphenated files
for f in *.py; do
  new=$(echo "$f" | tr '-' '_')
  if [ "$f" != "$new" ]; then
    mv "$f" "$new"
  fi
done
```

**Related patterns:**
- [[feedback_always_verify_before_documenting]] - Test actual imports before claiming "working"
- Test command: `python3 -c "import module_name; print('OK')"`

**Exception:** None. This is a Python language requirement, not a style preference.
