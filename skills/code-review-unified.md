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
/code-review --workers=opus,haiku               # Skip sonnet
```

## Arbiter Selection

### Auto (Based on Strategy)
```bash
/code-review --strategy=rotating  # Auto-rotates
```

### Manual Override
```bash
/code-review --arbiter=opus    # Always Opus
/code-review --arbiter=sonnet  # Always Sonnet
/code-review --arbiter=haiku   # Always Haiku
```

## Usage Examples

### Example 1: Brutal Review (Most Thorough)
```bash
/code-review --strategy=rotating --workers=opus,sonnet,haiku,gemini
```
- 4 worker models
- Rotating arbiter (most fair)
- Highest quality, highest cost

### Example 2: Fast Review
```bash
/code-review --strategy=majority --workers=opus,sonnet
```
- 2 workers only
- Majority vote (no arbiter)
- Fast, low cost

### Example 3: Opus-Led Review
```bash
/code-review --strategy=single --arbiter=opus --workers=opus,sonnet,haiku
```
- 3 workers
- Opus always arbitrates
- Consistent decision-making

### Example 4: Weighted Consensus
```bash
/code-review --strategy=weighted --workers=opus,sonnet,haiku
```
- 3 workers
- Confidence-weighted voting
- Quality over quantity

## Options

- `--strategy=MODE` - Consensus strategy (rotating/single/majority/weighted/pairwise)
- `--arbiter=MODEL` - Override arbiter model (opus/sonnet/haiku/gemini)
- `--workers=LIST` - Comma-separated worker models
- `--path=DIR` - Target directory (default: .)
- `--create-issues` - Create GitHub issues (default: true)
- `--sync` - Sync with remote first (default: true)

## Output

```
═══════════════════════════════════════
🔍 Multi-Model Code Review
═══════════════════════════════════════
Strategy: rotating
Workers: opus, sonnet, haiku
Arbiter: auto (rotating)
═══════════════════════════════════════

🔧 Detecting platform...
✅ Platform: github (using gh)

🔍 Scanning...
Found 12 potential issues

🤖 Running rotating strategy review...
🎯 Strategy: rotating | Workers: opus, sonnet, haiku
✅ Multi-model review complete

⚖️ Arbiter making decisions (rotating strategy)...
⚖️ Arbiter: Opus (rotating strategy)
⚖️ Arbiter: Sonnet (rotating strategy)
⚖️ Arbiter: Haiku (rotating strategy)
✅ Decisions complete

═══════════════════════════════════════
📊 Code Review Results
═══════════════════════════════════════
Total Scanned: 12
Reviewed: 10
Real Issues: 3
False Positives: 7
Strategy: rotating
Consensus: 95% avg
═══════════════════════════════════════

📝 Creating 3 GitHub issues...
✅ Created 3 issues
```

## Strategy Comparison

| Strategy | Speed | Cost | Quality | Bias | Use When |
|----------|-------|------|---------|------|----------|
| **rotating** | Medium | High | Highest | None | Production, critical |
| **single** | Fast | Low | Good | Some | Quick scans |
| **majority** | Fastest | Lowest | Good | None | Speed priority |
| **weighted** | Slow | High | Highest | None | Complex issues |
| **pairwise** | Medium | Medium | High | Low | Balanced needs |

## Migration from auto-review-brutal

**Before**:
```bash
/auto-review-brutal
```

**Now**:
```bash
/code-review --strategy=rotating
```

**Same functionality**, but with:
- ✅ Strategy selection
- ✅ Worker configuration  
- ✅ Arbiter swapping
- ✅ Better performance

## Cost Optimization

### Minimize Cost
```bash
/code-review --strategy=majority --workers=opus,sonnet
```
- 2 workers, no arbiter
- ~40% cost reduction

### Balance Cost/Quality
```bash
/code-review --strategy=single --workers=opus,sonnet,haiku
```
- 3 workers, 1 arbiter
- Standard cost

### Maximum Quality
```bash
/code-review --strategy=rotating --workers=opus,sonnet,haiku,gemini
```
- 4 workers, rotating arbiter
- ~150% cost increase

## Files

- `~/.claude/workflows/code-review.js`
- `~/.claude/workflows/shared/consensus-engine.js` (enhanced)
- `~/.claude/skills/code-review-unified.md`

## See Also

- `/pr-review` - PR-specific review
- `/code-solve` - Auto-resolve issues
- `/code-improve` - Iterative improvement

---

**Version**: 2.0 (Unified)  
**Created**: 2026-06-03  
**Global**: Works on all projects
