# Claude Code Practices for Red Hat Work

**Last Updated:** 2026-09-25  
**Scope:** Red Hat Disseminator, UXE Search, and related projects  
**Approved Models:** Claude (Haiku, Sonnet, Opus), Google Gemini, JetBrains Cursor  
**No Personal Keys:** All API work uses official RH-approved keys only

---

## Core Principles

1. **User is the arbiter** — Models provide analysis; you make final decisions
2. **Model diversity prevents blind spots** — Don't use same model family for critical reviews
3. **Memory tracks context** — Decisions, project state, preferences persist across sessions
4. **Multi-AI consensus for critical work** — Sonnet + Opus for bugs, security, breaking changes
5. **Worktrees for branches** — Keep main repo clean, isolate branch work
6. **Always ask before git push** — Never auto-push; user confirms first

---

## When to Use Each Model

### **Haiku 4.5** (Fastest, cheapest)
- Code reading and navigation
- Simple refactoring
- Test writing
- Documentation
- Debugging straightforward issues
- Default for routine tasks

### **Sonnet 4.5** (Balanced)
- Code review and architecture analysis
- Feature design
- Multi-step problem solving
- Initial review of complex changes (use before Opus)
- Domain-specific validation (SQL, Solr queries, etc.)

### **Opus 5** (Strongest reasoning)
- Critical bug analysis (security, logic flaws)
- Adversarial review of Sonnet findings
- Deep technical design (keyset pagination, distributed systems)
- Breaking change impact analysis
- Final arbitration on disagreement

### **Opus 4.8** (Good alternative)
- Adversarial challenge of Opus 5 (different perspective)
- When Opus 5 unavailable
- Time-sensitive critical work (slightly faster than 5)

### **Google Gemini** (Different reasoning style)
- Alternative perspective on disputed issues
- Breaking confirmation bias when Opus+Sonnet agree but you doubt
- Not primary choice, but good for external validation

### **Cursor** (IDE-integrated)
- Coding directly in IDE
- Real-time fix suggestions
- Test-driven development
- When you want interactive iteration

---

## Multi-AI Consensus Rules

### **Use consensus when:**
- ✅ Security findings or vulnerabilities
- ✅ Breaking changes or API redesigns
- ✅ Critical bugs (data loss, silent failures)
- ✅ Domain-specific correctness (Solr queries, SQL, etc.)
- ✅ Architectural decisions
- ✅ Code destined for production merge

### **Consensus process:**

**Step 1: Initial Review (Sonnet 4.5)**
- Review the code, design, or issue
- Flag findings with confidence/severity
- Surface open questions

**Step 2: Adversarial Challenge (Opus 5 or 4.8)**
- Challenge Sonnet's findings
- Find false alarms or missed edge cases
- Push back on recommendations
- Validate domain-specific claims

**Step 3: You Decide**
- Read both reviews
- You are the arbiter (not another model)
- Ask clarifying questions if needed
- Make the call

### **Safe pairings (avoid confirmation bias):**
- ✅ Sonnet 4.5 + Opus 5 (different reasoning styles)
- ✅ Sonnet 4.5 + Opus 4.8 (forces external challenge)
- ✅ Opus 5 + Gemini (completely different architecture)
- ❌ Opus 5 + Opus 4.8 (too similar, confirmation bias risk)
- ❌ Same model reviewing itself (circular)
- ❌ Both models same family without diversity (e.g., two Opus models)

### **Domain-expert review requirement:**
If someone (Greg, Yugank, etc.) already reviewed and found issues:
- Don't start with model consensus
- Ask the expert for fix direction first
- Then validate the fix with models
- Model consensus can't replace domain expertise

---

## Memory System

### **What to save:**

**Feedback (preferences & past corrections):**
```
name: always_ask_before_push
description: Never auto-push code; always ask user for confirmation
memory_type: feedback
```

**Reference (how things work):**
```
name: gitlab_api_patterns
description: GitLab API endpoints, token handling, MR creation
memory_type: reference
```

**Project (current initiatives, deadlines):**
```
name: cpsearch_10981_keyset_pagination
description: Keyset pagination fix - known bugs in AND vs OR logic, cursorMark alternative
memory_type: project
```

### **Storage:**
- Local files: `~/Development/redhat/scm/gitlab/.../memory/*.md`
- Check memory at session start
- Update memory when you learn something new

### **Don't save:**
- Code snippets (use git history)
- Architecture (read CLAUDE.md and codebase)
- Recent git changes (use `git log`)

---

## RH-Specific Practices

### **API Keys & Credentials**
- ✅ Use official GitLab token (GITLAB_TOKEN)
- ✅ Use official Anthropic key (if configured for RH)
- ❌ Never use personal OpenAI, Google, etc. keys
- ❌ Never commit .env files or credentials
- Secrets go in Bitwarden or secure vault, not disk

### **Git Workflow**
```bash
# Create isolated worktree for branch work
git worktree add /tmp/feature-branch -b feature-name

# Work in isolated tree (doesn't touch main repo)

# Push only after user confirmation
# "ready to push? [describe changes]"

# Never force-push main or published branches
```

### **Model Selection for RH Work**
- **Default:** Haiku 4.5 (cheapest, approved)
- **Complex tasks:** Sonnet 4.5 (balanced)
- **Critical work:** Sonnet + Opus consensus
- **Speed matters:** Opus 4.8 instead of 5

### **Approval Gates**
- **Before implementing:** Show plan, ask approval
- **Before pushing:** Show diff, ask confirmation
- **Before merging:** Show MR, ask user to merge
- **For breaking changes:** Get stakeholder buy-in first

---

## Anti-Blind-Spot Practices

### **Avoid confirmation bias:**
- When two models agree, ask: "Are we both missing something?"
- Use adversarial review (second model challenges, not validates)
- If a human already flagged issues (like Greg did on MR 1087), trust that first

### **Catch domain-specific gaps:**
- Models good at: syntax, structure, logic flow
- Models bad at: specialized semantics (Solr keyset pagination, crypto, etc.)
- If unsure: ask a domain expert before shipping

### **Verify before documenting:**
- Don't write design docs before consensus
- Don't claim "all tests pass" without running them
- Don't mark "complete" if you haven't tested the actual feature

---

## Practical Checklist for Critical Work

**Before implementing:**
- [ ] Read memory for context
- [ ] Understand what changed from last session
- [ ] Ask approval for approach

**During implementation:**
- [ ] Run tests as you go
- [ ] Don't assume—verify

**Before pushing:**
- [ ] Run full test suite
- [ ] Get consensus review (Sonnet + Opus if critical)
- [ ] Show diff to user
- [ ] Ask user to confirm push

**For breaking changes:**
- [ ] Get domain expert input (Greg, Yugank, etc.)
- [ ] Consensus review with models
- [ ] Release notes explaining change
- [ ] Deprecation plan if replacing old behavior

---

## Session Flow

**Session start:**
- [ ] Read memory for this project
- [ ] Check git status (any uncommitted changes?)
- [ ] Ask what you're working on

**During work:**
- [ ] Update memory with new findings
- [ ] Ask before risky actions (force push, delete files)
- [ ] Consensus review for critical changes

**Session end:**
- [ ] Offer to save any new feedback/learnings
- [ ] Remind about uncommitted changes
- [ ] Clean up any temp worktrees

---

## Questions? 

- **RH memory:** Preferences, projects, references → `~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/memory/MEMORY.md`
- **Project context:** What's the status of X? → Check RH memory files
- **RH practices:** How do we handle Y? → See Reference memories in RH memory
- **Personal context:** Fleet, orchestrator, personal projects → `~/.FlossWare/claude/MEMORY_INDEX.md`

---

**This replaces:** The old orchestrator-based CLAUDE.md (2026-07-10)  
**Simplified for:** Practical Red Hat development work, user-driven decisions, multi-AI consensus without fleet overhead
