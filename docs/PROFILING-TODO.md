# Model Profiling Workflow - TODO

## Status: 95% Complete, Needs Final Debugging

The profiling system is almost done but has a workflow syntax issue that needs fixing.

## What Works:
- ✅ Database table (`learning.model_capabilities`) created
- ✅ Profiling logic designed (automated checks + free judge)
- ✅ Helper script (`scripts/profile-models.sh`)
- ✅ Documentation complete

## What's Broken:
- ❌ Workflow syntax error: "Unexpected keyword 'export'"
- Issue: Workflow runtime doesn't like something about the export statements

## Quick Fix Options:

### Option 1: Simpler Python Script (30 min)
Create `scripts/profile-models.py` that does the same thing:
```python
# Query unprofiled models from PostgreSQL
# For each model:
#   - Send 5 test tasks
#   - Run automated checks (pattern matching)
#   - Call Groq to judge quality
#   - Store scores in database
```

### Option 2: Fix Workflow Syntax (1 hour)
Debug the export/import issues in profile-model-capabilities.mjs
- Problem seems to be how we're exporting `const meta` and `export default`
- Compare to working workflows like `test-api-proxy.mjs`

### Option 3: Manual Quick Start (15 min)
Manually add capability scores for top 10 known models:
```sql
INSERT INTO learning.model_capabilities VALUES
  ('qwen/qwen3-coder:free', 'openrouter', 0.85, 0.75, 0.60, 0.70, 0.75, 2000, 1, 'Manual seed'),
  ('groq/llama-3.3-70b-versatile', 'groq', 0.75, 0.70, 0.80, 0.85, 0.80, 1500, 1, 'Manual seed'),
  -- etc...
```

## Recommended Path:

**For next session:**
1. Try Option 1 (Python script) - simpler, no workflow complexity
2. Profile top 20 models first (test the system)
3. Once working, batch profile all 252 models overnight

## Files:
- `workflows/profile-model-capabilities.mjs` - Needs fixing
- `scripts/profile-models.sh` - Works (helper)
- `learning.model_capabilities` - Ready (table exists)

## Current Capability Coverage:
- Total models: 252
- With capabilities: 0
- Coverage: 0%

Once profiling works, orchestrator will know which models are good at what!
