---
name: code-review-unified
description: This skill should be used when the user asks to "review code", "code review", "check code quality", "find bugs", "security review", or discusses analyzing code with multiple AI models and consensus strategies.
version: 2.0.0
---

# Code Review - Unified Multi-Model Review with Strategies

**Replaces**: auto-review-brutal + built-in code-review  
**Now**: One unified workflow with configurable consensus strategies

## Features

- **5 Consensus Strategies** - rotating, single, majority, weighted, pairwise
- **Configurable Workers** - Choose which AI models review
- **Swappable Arbiter** - Pick which model makes final decision
- **Platform Agnostic** - Works with GitHub, GitLab, Bitbucket
- **Review-Only Mode** - Can report without creating issues

## Consensus Strategies

### 1. **rotating** (Most Democratic) ⭐ RECOMMENDED
```bash
/code-review --strategy=rotating
```
- Different arbiter each time (Opus → Sonnet → Haiku → repeat)
- Prevents single-model bias
- Most fair consensus
- **Use for**: Critical code, production, high-stakes

### 2. **single** (Fastest)
```bash
/code-review --strategy=single --arbiter=opus
```
- One arbiter judges all (default: Opus)
- Fastest, lowest cost
- Potential bias
- **Use for**: Quick scans, lower-risk code

### 3. **majority** (No Arbiter Overhead)
```bash
/code-review --strategy=majority
```
- Simple vote count, no arbiter
- Very fast
- Democratic
- **Use for**: Clear-cut issues, speed priority

### 4. **weighted** (Confidence-Based)
```bash
/code-review --strategy=weighted
```
- Votes weighted by confidence scores
- Higher confidence = more influence
- Quality-aware
- **Use for**: Complex issues, uncertain cases

### 5. **pairwise** (Balanced)
```bash
/code-review --strategy=pairwise
```
- Workers review in pairs
- Cross-validation
- Balanced approach
- **Use for**: Medium complexity

## Worker Configuration

### Default Workers
```bash
/code-review  # Uses: opus, sonnet, haiku
```

### Custom Workers
```bash
/code-review --workers=opus,sonnet,haiku,gemini  # 4 models
/code-review --workers=opus,sonnet              # 2 models (faster)
```

## Options

- `--strategy=MODE` - Consensus strategy (rotating/single/majority/weighted/pairwise)
- `--arbiter=MODEL` - Override arbiter model (opus/sonnet/haiku/gemini)
- `--workers=LIST` - Comma-separated worker models
- `--path=DIR` - Target directory (default: .)
- `--create-issues` - Create GitHub issues (default: true)
- `--sync` - Sync with remote first (default: true)

## Strategy Comparison

| Strategy | Speed | Cost | Quality | Bias | Use When |
|----------|-------|------|---------|------|----------|
| **rotating** | Medium | High | Highest | None | Production, critical |
| **single** | Fast | Low | Good | Some | Quick scans |
| **majority** | Fastest | Lowest | Good | None | Speed priority |
| **weighted** | Slow | High | Highest | None | Complex issues |
| **pairwise** | Medium | Medium | High | Low | Balanced needs |

## Files

- `~/.claude/workflows/code-review.js`
- `~/.claude/workflows/shared/consensus-engine.js` (enhanced)
- `~/.claude/skills/code-review-unified.md`

---

**Version**: 2.0 (Unified)  
**Created**: 2026-06-03  
**Global**: Works on all projects
