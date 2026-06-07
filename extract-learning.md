---
name: extract-learning
description: Extract learnings from workflow execution (internal helper workflow)
---

# Extract Learning - Internal Workflow

**Internal helper workflow** - automatically called by other workflows to extract learnings.

## Purpose

This workflow analyzes execution data from other workflows and extracts:
- **User patterns**: Preferences, expertise levels, workflow usage
- **Code patterns**: Common bugs, architecture insights, tech stack
- **Recommendations**: Actionable improvements
- **Memory suggestions**: What to save for future sessions

## Usage

Called automatically by workflows at completion:

```javascript
await workflow('extract-learning', {
  workflow_name: 'code-solve',
  execution_data: { ...result }
})
```

## Supported Workflows

Has custom prompts for:
- code-solve
- code-review
- code-test
- code-pr-review
- code-security
- code-doc
- ai-prompt
- ai-chat

## Output Example

```
📊 LEARNINGS EXTRACTED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 USER PREFERENCES:
  • Prefers squash merges
  • Likes detailed commit messages

🎓 EXPERTISE LEVELS:
  ⭐ JavaScript: advanced
  📚 Docker: intermediate

🐛 COMMON BUG PATTERNS:
  • Missing null checks in async code
  • No error handling in API calls

💡 RECOMMENDATIONS:
  1. Add TypeScript for better type safety
  2. Write integration tests for API endpoints

📝 MEMORY SUGGESTIONS (2):
  🔴 HIGH PRIORITY:
    [feedback] User prefers minimal changes over large refactors
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Not a User-Facing Skill

This workflow is called internally and not meant to be invoked directly by users.
