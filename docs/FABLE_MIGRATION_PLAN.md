# Fable API Migration Plan (Issue #197)

## Summary
Fable API is failing across the codebase. This plan migrates all Fable references to working alternatives.

## Affected Files (20 found)

### Active Production Files
1. `.claude/mcp-servers/ollama-mcp-server.py` - MCP server routing
2. `.claude/self/dcab-router-layer1.js` - DCAB routing layer
3. `.claude/self/contextual-router-integration.py` - Contextual router
4. `.claude/fleet/fleet-agent-launcher.mjs` - Fleet orchestration
5. `.claude/fleet/production-router.mjs` - Production routing

### Backup/Archive Files
6-20. Files in `.claude/workflow-backups/` (2 backup directories)
   - These are old backups and can be left as-is (not actively used)

## Recommended Replacements

| Original Model | Replacement | Reason |
|---------------|-------------|---------|
| `fable` | `claude-3-5-sonnet-v2@20241022` | Same tier, Vertex AI available |
| `claude-fable-5` | `claude-3-5-sonnet-v2@20241022` | Sonnet is proven stable |
| Any fable reference | `gemini-2.5-flash-lite` | Google API working (but quota limited) |

## Migration Strategy

### Phase 1: Update Active Files (PRIORITY)
Replace all Fable references in production files (1-5 above) with Sonnet.

**Search pattern:**
```bash
grep -r "fable\|claude-fable" .claude/self/ .claude/fleet/ .claude/mcp-servers/
```

**Replace with:**
- Primary: `claude-3-5-sonnet-v2@20241022` (once Vertex AI works)
- Fallback: `gemini-2.5-flash-lite` (Google, quota limited)
- Emergency: `llama-3.3-70b` (via Cerebras, currently Cloudflare-blocked)

### Phase 2: Archive Cleanup (LOW PRIORITY)
Backup files in `.claude/workflow-backups/` can be:
1. Left as-is (they're archives, not active)
2. Documented with comment: `// Note: Fable deprecated, use Sonnet`
3. Deleted if confirmed unused

## Implementation Steps

1. **Test Vertex AI access** on fleet workers
   - Install `anthropic[vertex]` SDK
   - Authenticate gcloud on all workers
   - Test with simple "What is 2+2?" query

2. **Update routing configs**
   - `dcab-router-layer1.js`: Change Fable → Sonnet
   - `production-router.mjs`: Change Fable → Sonnet
   - `contextual-router-integration.py`: Change Fable → Sonnet

3. **Update fleet launcher**
   - `fleet-agent-launcher.mjs`: Update model selection logic

4. **Update MCP server**
   - `ollama-mcp-server.py`: Add Sonnet as fallback

5. **Test end-to-end**
   - Run fleet task with new routing
   - Verify no Fable API calls
   - Confirm Sonnet/Gemini responses

## Rollback Plan

If Vertex AI doesn't work:
1. Use OpenRouter free models as temporary fallback
2. Document quota exhaustion issue
3. Request API quota increases from IT

## Success Criteria

- ✅ Zero Fable API calls in logs
- ✅ All production files use Sonnet or Gemini
- ✅ Fleet orchestrator completes 4 ECC issues successfully
- ✅ No HTTP 404 errors for missing models

## Notes

- Fable was never a real Anthropic model - likely a misconfiguration
- All Anthropic models require either:
  - Direct API key (ANTHROPIC_API_KEY)
  - Vertex AI authentication (gcloud auth)
- Current bottleneck: Vertex AI not working on fleet workers

## Next Steps

**IMMEDIATE**: Get Vertex AI working on 4 authenticated workers (server-01, server-02, pi-01, pi-02)

**THEN**: Run migration script to replace all Fable references
