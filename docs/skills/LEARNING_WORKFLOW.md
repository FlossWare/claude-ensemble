# Learning Workflow with Claude Code

This repository serves as your **persistent knowledge base** for all learning sessions with Claude Code.

## Quick Start

### 1. Start Learning Session

```bash
cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
code .  # Launch Claude Code in this directory
```

### 2. Tell Claude What to Learn

Use **named sessions** for organization:

```
Session name: "rust-learning"
Prompt: "Deep research + code analysis on Rust: ownership, borrowing, lifetimes"
```

Or:

```
Session name: "kubernetes-internals"  
Prompt: "Learn Kubernetes architecture - etcd, kube-apiserver, controllers"
```

### 3. Claude Saves to Memory

Claude will automatically save findings to:
- `memory/reference_*.md` - Reference knowledge
- `memory/feedback_*.md` - Your preferences
- `memory/user_*.md` - Your context

### 4. Commit and Push

After the learning session:

```bash
git add memory/
git commit -m "feat: Learned Rust ownership and borrowing system"
git push
```

Or use the helper script:

```bash
./scripts/commit-learning.sh "Rust ownership and borrowing"
```

## Learning Session Types

### Deep Research Only
```
"Deep research on [topic]: [specific questions]"
```
- Web searches, fact verification
- ~100-200 agents, 2-4M tokens
- Saves verified findings to memory

### Code Analysis Only
```
"Code learning on [repo]: analyze [specific aspects]"
```
- Clone repo, analyze key files
- Focus on implementation details
- Extracts patterns and architecture

### Both (Recommended)
```
"Deep research + code analysis on [topic]"
```
- Combines web research + source code study
- Most comprehensive knowledge
- What we did for Haskell/Go today

## Example Commands

### Programming Languages
```
"Deep research + code learning: Rust (ownership, async, macros)"
"Deep research + code learning: Kotlin (coroutines, DSLs)"
```

### Frameworks/Tools
```
"Deep research: Kubernetes architecture and design patterns"
"Code learning: Docker engine internals"
```

### Specific Topics
```
"Deep research: Raft consensus algorithm with implementation examples"
"Code learning: PostgreSQL query planner (analyze src/backend/optimizer)"
```

## Memory Organization

Your knowledge base is organized in `memory/`:

```
memory/
├── MEMORY.md              # Index of all memories
├── reference_*.md         # Technology/language references
├── feedback_*.md          # Your preferences and workflow
├── user_*.md              # Your role and context
└── project_*.md           # Project-specific learnings
```

## Git History as Learning Log

View your learning history:

```bash
# See all learning sessions
git log --oneline memory/

# What did I learn about Go?
git log --grep="Go" --oneline

# Show learning from last week
git log --since="1 week ago" memory/
```

## Tips

### Use Multi-AI for Quality
Add "multi-ai" to prompts for adversarial verification:
```
"Use multi-ai to research [topic]"
```
- Different models verify each finding
- 3-vote consensus required
- Higher confidence results

### Named Sessions by Topic
Organize sessions:
- `rust-learning`
- `k8s-deep-dive`  
- `distributed-systems`
- `postgres-internals`

### Commit Messages
Format:
```
feat: Learned [topic] - [key aspects]
feat: Deep research on Rust ownership system
feat: Code analysis of Go runtime scheduler
```

## Advanced: Focus on Key Files

For large codebases, specify what to analyze:

```
"Code learning: PostgreSQL query planner
Focus on:
1. src/backend/optimizer/plan/planner.c
2. src/backend/optimizer/path/
3. Cost estimation algorithms
4. Join selection strategy"
```

Claude will analyze only the critical 10-15 files instead of scanning everything.

## Maintenance

### Keep Index Updated
After new memories are created, update `memory/MEMORY.md`:

```bash
# Claude usually does this automatically
# If needed, ask: "Update MEMORY.md index"
```

### Sync Across Machines
```bash
git pull  # Before starting new session
git push  # After completing session
```

## Why This Works

✅ **Persistent** - Knowledge saved forever in git  
✅ **Versioned** - Every learning session tracked  
✅ **Searchable** - Git history + grep + full text  
✅ **Portable** - Clone to any machine  
✅ **Shareable** - Push to GitLab, others can learn too  
✅ **Context** - Claude loads all memories in future sessions  

## Getting Help

Ask Claude:
- "What's in my memory about [topic]?"
- "Show my learning history"
- "Update MEMORY.md index"
- "What should I learn next about [area]?"
