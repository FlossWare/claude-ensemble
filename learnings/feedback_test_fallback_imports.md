---
name: feedback_test_fallback_imports
description: Always test fallback imports thoroughly and investigate failures instead of moving on
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d1146380-ec6c-4ed4-b700-da20e393e95c
---

When adding fallback imports (try/except ImportError patterns), ALWAYS verify they work before claiming success. Never assume a simple fallback will "just work."

**Why:** I added fallback imports like `from models import ...` without considering import ambiguity. With multiple `models.py` files in sys.path (lib/models.py and web/backend/models.py), Python imported the wrong one. I then claimed the fix worked without actually testing if the backend started, and when `curl http://localhost:9000/` returned no response, I didn't investigate - just moved on. This wasted the user's time with multiple broken iterations.

**How to apply:**
- When adding fallback imports in codebases with multiple modules of the same name, use explicit imports (`from backend.models import`) or importlib with exact file paths
- When a service doesn't respond to basic connectivity tests (curl, ping, health check), STOP and investigate the root cause - don't assume it's a different issue
- After claiming a fix is complete, verify the fix actually works by running/testing the affected code path
- Test fallback code paths just as thoroughly as the primary path - they're not "just in case" code, they're production code
- If I can't test something myself, explicitly tell the user "I cannot verify this works - please test and report back" rather than claiming success

Related: [[feedback_testing]] (if it exists - about always testing changes before reporting completion)
