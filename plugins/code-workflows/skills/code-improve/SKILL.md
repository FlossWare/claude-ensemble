---
name: code-improve
description: This skill should be used when the user asks to "improve code quality", "iterative improvement", "refactor code", "enhance code", or discusses continuously improving code until quality goals are met.
version: 1.0.0
---

# Code Improve - Iterative Quality Improvement

Iteratively improve code quality with multi-AI consensus until quality goals are met.

## Features

- **Iterative Loop** - Keeps improving until quality threshold met
- **Multi-Model Review** - Multiple AIs suggest improvements each iteration
- **Quality Tracking** - Measures quality score improvement
- **Automatic Refinement** - Applies best improvements automatically

## Usage

```bash
/code-improve [PATH] [OPTIONS]
```

## Options

- `PATH` - Target directory or file (default: current directory)
- `--threshold=N` - Stop when quality score >= N (default: 90)
- `--max-iterations=N` - Maximum iterations (default: 10)
- `--workers=N` - Number of AI workers (default: 3)

## How It Works

1. **Initial Review** - Multi-AI review identifies improvements
2. **Apply Best** - Apply highest-confidence improvements
3. **Re-Review** - Check new quality score
4. **Iterate** - Repeat until threshold met or max iterations
5. **Report** - Final quality metrics

---

**Version**: 1.0  
**Created**: 2026-06-03
