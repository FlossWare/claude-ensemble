---
name: workflow-no-fs-execsync
description: Workflows do NOT have fs or execSync globals - must use agent() only
metadata: 
  node_type: memory
  type: feedback
  created: 2026-06-14
  originSessionId: 1bdb3e55-000c-48af-9ef8-8d5a7794d27d
---

Claude Code workflows do NOT have fs or execSync as globals, despite what older documentation may say.

**What's available:**
- ✅ agent() - call AI models
- ✅ parallel() - concurrent execution
- ✅ pipeline() - sequential stages
- ✅ log() - logging
- ✅ phase() - phase marking
- ✅ workflow() - call other workflows
- ❌ fs - NOT available (can't writeFileSync, readFileSync, etc.)
- ❌ execSync - NOT available (can't shell out, can't call Ollama via curl)
- ❌ require() - NOT available
- ❌ process.env - NOT available

**Why:** Confirmed via test workflow - `typeof fs === 'undefined'` and `typeof execSync === 'undefined'`

**How to apply:**
1. Use agent() for ALL work (AI calls to Anthropic/OpenAI/Google APIs)
2. Return data from workflows instead of writing to files
3. Can't call local Ollama models via execSync + curl
4. Can't save intermediate results to disk
5. Workflow results come from return statement

**Workarounds:**
- For Ollama: Need MCP server or API wrapper (can't use execSync)
- For files: Return data, have caller save it
- For state: Keep in workflow variables, return at end

**Example - WRONG:**
```javascript
const result = execSync('curl http://server-02:11434/api/generate ...')
fs.writeFileSync('/tmp/results.json', JSON.stringify(data))
```

**Example - CORRECT:**
```javascript
const result = await agent(prompt, {model: 'opus', schema: mySchema})
return { results: data }  // Caller saves if needed
```

Related: [[feedback_mcp_not_needed]] - This is WHY we can't easily use Ollama in workflows
