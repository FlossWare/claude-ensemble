# AI Learn - Extract Global Learnings

Extract learnings from skills, workflows, and interactions into global memory.

## Usage

```bash
/ai-learn
```

## What It Does

1. **Analyzes** all skills and workflows in the repository
2. **Extracts** patterns, decisions, and best practices using multi-model consensus
3. **Categorizes** learnings by memory type (feedback, user, project, reference, technical)
4. **Stores** in global memory for cross-session sharing

## Multi-Model Approach

- **Workers**: Claude Opus, Claude Sonnet, GPT-4o, Gemini analyze independently
- **Arbiter**: Claude Opus synthesizes consensus and resolves conflicts
- **Consensus**: Only high-agreement learnings are stored

## Learning Sources

- Skill execution patterns
- Workflow orchestration strategies
- Multi-AI coordination methods
- User interaction preferences
- Error patterns and resolutions
- Best practices discovered
- Anti-patterns avoided

## Output

All learnings stored in `memory/` directory:
- Version controlled in git
- Shared across all sessions
- Accessible to arbiters and workers
- Indexed in `memory/MEMORY.md`

## When to Run

- After implementing new skills/workflows
- After discovering new patterns
- Periodically to consolidate knowledge
- Before major changes (to preserve learnings)

## Related

- `/ai-prompt` - Multi-model consensus prompts
- Workflow: `extract-learning.js`
- Global memory: `memory/README.md`
