# Claude Code Learnings

Critical lessons learned about Claude Code workflows, skills, and plugin systems during development.

## Files

### claude-code-workflows.md
Complete documentation about Claude Code workflow registration, discovery, and the difference between file existence vs. discoverability.

**Key Findings**:
- Workflow files existing in `~/.claude/workflows/` ≠ automatically registered
- Registration mechanism is unclear/undocumented
- Some workflows appear in available list, others don't despite identical structure

### workflow-imports-lesson.md  
Essential lesson about ES6 imports in workflows and the two invocation modes.

**Key Findings**:
- Named workflows (registered): Can use imports
- scriptPath workflows: Must be self-contained, no imports
- Error messages can be misleading
- Self-contained workflows are always safer

## How to Use These Learnings

These files are meant to be referenced when:
1. Creating new workflows
2. Debugging workflow issues
3. Understanding why workflows aren't discovered
4. Deciding between import-based vs self-contained

## Memory System

These learnings are also stored in Claude Code's memory system at:
```
~/.claude/projects/-home-sfloess/memory/
```

This allows Claude to reference them in future sessions automatically.

## Key Takeaways

1. **Always create self-contained workflows** for maximum compatibility
2. **Test both invocation methods** (name and scriptPath)
3. **File existence ≠ discoverability** - always verify with actual invocation
4. **Import statements break scriptPath** invocation
5. **Registration is mysterious** - empirical testing required

---

**Created**: 2026-06-03  
**Context**: Debugging and fixing code-solve workflow
