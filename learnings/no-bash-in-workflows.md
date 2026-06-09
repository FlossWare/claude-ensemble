---
name: no-bash-in-workflows
description: Workflows should use Read tool instead of Bash commands to avoid permission prompts
metadata:
  node_type: memory
  type: feedback
  originSessionId: current
---

# No Bash Commands in Workflows - Use Read Tool

**Rule**: Workflows that spawn subagents should ALWAYS instruct agents to use the Read tool instead of Bash commands for file operations.

**Why**: Bash commands trigger permission prompts for users, even in `~/.claude/` directory, because subagents run in a separate permission context.

**User feedback**: "why am i being prompted for things like Bash command from the refactor-iterate workflow... i dont want to be promoted at all"

## The Problem

```javascript
// ❌ BAD: Triggers permission prompt
await agent(`Analyze file.

Execute:
sed -n '107,120p' file.js | wc -l
grep -n "pattern" file.js
cat file.js

Return analysis.`)
```

User sees permission prompt:
```
Bash command · from the "refactor-iterate" workflow
  sed -n '107,120p' /home/sfloess/.claude/repos/claude-global-skills/code-hygiene-review.js | wc -l
  Run shell command
```

## The Solution

```javascript
// ✅ GOOD: No permission prompts
await agent(`Analyze file: file.js

IMPORTANT: Use the Read tool to analyze the file, NOT Bash commands.
- Don't use sed, grep, cat, wc, or other shell commands
- Use Read tool for file content
- Analyze in your reasoning, return structured data

Identify patterns and return structured results.`, {
  schema: ANALYSIS_SCHEMA
})
```

## Instruction Template for Workflows

Add this to EVERY agent prompt that might need file access:

```
IMPORTANT: Use the Read tool to analyze files, NOT Bash commands.
- Don't use sed, grep, cat, wc, or other shell commands
- Use Read tool for file content
- Analyze in your reasoning, return structured data
```

## Common Operations - Before/After

### Count Lines
```javascript
// ❌ BAD
await agent(`Execute: sed -n '107,120p' file.js | wc -l`)

// ✅ GOOD
await agent(`Read file.js lines 107-120 and count them.

Use Read tool, NOT sed/wc.

Return line count.`, {
  schema: {
    type: 'object',
    properties: {
      line_count: { type: 'number' }
    }
  }
})
```

### Search for Pattern
```javascript
// ❌ BAD
await agent(`Execute: grep -n "detectPlatform" file.js`)

// ✅ GOOD
await agent(`Find all occurrences of "detectPlatform" in file.js

Use Read tool to read the file, then identify matches.

Return line numbers and context.`, {
  schema: {
    type: 'object',
    properties: {
      matches: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            line_number: { type: 'number' },
            line_content: { type: 'string' }
          }
        }
      }
    }
  }
})
```

### Read File Content
```javascript
// ❌ BAD
await agent(`Execute: cat file.js`)

// ✅ GOOD
await agent(`Read and analyze file.js

Use Read tool.

Return file content and analysis.`, {
  schema: {
    type: 'object',
    properties: {
      content: { type: 'string' },
      total_lines: { type: 'number' }
    }
  }
})
```

## Helper Functions Available

Created `shared/inline/file-analyzer.js` with:
- `readFileLines(agent, filepath, startLine, endLine)` - Read specific lines
- `analyzeFile(agent, filepath)` - Read and analyze entire file
- `findPattern(agent, filepath, pattern)` - Search for pattern
- `countLinesInRange(agent, filepath, startLine, endLine)` - Count lines

Copy these into workflows instead of using Bash commands.

## Where This Applies

### ✅ Always use Read tool in:
- Workflow agent prompts
- Subagent instructions
- Analysis tasks
- Code review tasks
- Refactoring tasks
- Any file inspection

### ⚠️ Bash is OK for:
- Git operations (git log, git diff) - these are expected
- Build commands (npm, cargo, make) - these are expected
- When explicitly building/deploying (not just analyzing)

## Updated Workflows

Applied to:
- ✅ `workflows/refactor-iterate.js` - Added "Use Read tool, NOT Bash" instruction
- ✅ `workflows/refactor-all-workflows.js` - Added to analysis and proposal phases
- 📝 TODO: Review all other workflows for Bash command usage

## Key Rule

**In workflow agent prompts, ALWAYS include**:
```
IMPORTANT: Use the Read tool to analyze files, NOT Bash commands.
```

This prevents permission prompts and provides better user experience.

---

**Status**: Active rule for all workflows  
**Date**: 2026-06-04  
**User impact**: Eliminates all permission prompts for file analysis  
**Related**: [[automation-preferences]]
