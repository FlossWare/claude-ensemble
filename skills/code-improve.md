# Code Improve - Iterative Quality Improvement

Systematically improve code quality through review → fix → verify cycles.

## Features

- **Iterative Loop** - Review → Fix → Verify → Repeat
- **Quality Scoring** - 0-100 score tracks progress
- **Target-Based** - Stop at quality threshold
- **Batch Fixing** - Fix N issues per iteration
- **Auto Mode** - Fully autonomous until target reached
- **Multi-Model** - Consensus-based fixing

## Usage

```bash
# Interactive mode
/code-improve

# Auto mode with target
/code-improve --auto --target-score 95

# Specific path
/code-improve --path src/ --max-iterations 5

# Custom batch size
/code-improve --batch-size 10
```

## Options

- `--target-score N` - Stop when quality >= N (default: 95)
- `--max-iterations N` - Max improvement cycles (default: 10)
- `--batch-size N` - Issues per iteration (default: 5)
- `--auto` - Fully autonomous (no prompts)
- `--path DIR` - Focus on specific directory

## Quality Score

```
Score = 100 - (critical×10 + high×5 + medium×1)
```

**Targets**:
- 95+: Excellent
- 90-94: Good
- 80-89: Acceptable
- < 80: Needs work

## Workflow

Each iteration:

1. **Review Code** - Multi-model scan for issues
2. **Calculate Score** - Track quality metric
3. **Prioritize** - Select top N issues
4. **Generate Fixes** - AI proposes solutions
5. **Apply Fixes** - Implement changes
6. **Verify** - Re-review improved code

Loop until:
- Target score reached
- Max iterations hit
- No issues remain

## Example

```bash
$ /code-improve --auto --target-score 90

═══ Iteration 1/10 ═══
🔍 Reviewing code...
   Score: 65/100
   Issues: 23 (8 critical, 10 high, 5 medium)

🔧 Fixing 5 critical issues...
   ✓ Fixed SQL injection
   ✓ Fixed command injection
   ...

═══ Iteration 2/10 ═══
🔍 Reviewing code...
   Score: 78/100 (+13)
   Issues: 12 (2 critical, 7 high, 3 medium)

🔧 Fixing 5 high issues...
   ...

═══ Iteration 3/10 ═══
🔍 Reviewing code...
   Score: 92/100 (+14)
   Issues: 3 (0 critical, 1 high, 2 medium)

✅ Target score reached!

📝 Creating PR...
   ✓ Branch: improve/quality-1234567890
   ✓ PR: https://github.com/.../pull/331
   
✅ Quality improved 65 → 92 (+27 points)
```

## Convergence

Stops when:
- **Target reached**: Score >= target
- **Perfect**: Score = 100
- **Max iterations**: Hit iteration limit
- **No improvement**: < 2 point gain for 2 iterations

## Auto Mode

```bash
/code-improve --auto --target-score 95 --max-iterations 10
```

Runs completely unattended:
- No prompts
- Continuous improvement
- Creates final PR
- Posts summary

## Integration with CI/CD

```yaml
- name: Quality Improvement
  run: |
    claude /code-improve \
      --auto \
      --target-score 90 \
      --max-iterations 5
```

## Files

- `~/.claude/workflows/code-improve.js`
- `~/.claude/skills/code-improve.md`
- `~/.claude/workflows/shared/` (uses all modules)

## See Also

- `/auto-review-brutal` - One-time review
- `/code-solve` - Resolve specific issues
- `/pr-review` - Review pull requests

---

**Version**: 1.0  
**Created**: 2026-06-03  
**Global**: Works on all projects
