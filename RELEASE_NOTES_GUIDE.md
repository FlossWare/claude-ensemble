# Release Notes Generation

Automated release notes generation using multi-AI consensus.

## Quick Start

### Interactive Mode (Recommended)

```bash
claude run code-release-notes
```

Prompts for approval before publishing release.

### Autonomous Mode

```bash
claude run code-release-notes --autonomous
```

Or specify a version:

```bash
claude run code-release-notes v2.1.0
claude run code-release-notes --version v2.1.0 --autonomous
```

## How It Works

1. **Detect Platform** — Identifies GitHub or GitLab
2. **Find Last Release** — Gets previous release tag via `git describe`
3. **Analyze Commits** — Collects all commits since last release
4. **Multi-AI Categorization** — 3 models (Opus, Sonnet, Haiku) categorize independently
5. **Consensus** — Arbiter (Opus) merges categorizations by majority vote
6. **Impact Analysis** — Scores changes by importance
7. **Generate Notes** — Creates structured markdown
8. **User Confirmation** (interactive) — Review before publishing
9. **Publish** — Creates git tag and release

## Commit Categories

- **Features** — New functionality
- **Fixes** — Bug fixes
- **Breaking** — Breaking changes (API changes, incompatibilities)
- **Performance** — Performance improvements
- **Documentation** — Doc updates
- **Chore** — Dependencies, build, tooling
- **Notable** — Important changes highlighted

## Output

```markdown
# v2.1.0

## 🚀 Breaking Changes
- Alert systemd path fix

## ✨ Features
- Conversation feedback capture mechanism
- Comprehensive service documentation

## 🐛 Fixes
- Atomic writes for state durability

## 📚 Documentation
- Service guides and tutorials

## 🔧 Chore
- Update dependencies
```

## Files

- `code-release-notes.js` — Interactive workflow (prompts before publishing)
- `code-release-notes-auto.js` — Fully autonomous (no prompts, auto-publishes)
- `code-release-notes.md` — Workflow documentation

## Usage Examples

### Generate notes for manual review

```bash
claude run code-release-notes
# Reviews notes, you approve before publishing
```

### Auto-generate with specific version

```bash
claude run code-release-notes v3.0.0 --autonomous
# Auto-publishes as v3.0.0
```

### Auto-increment patch version

```bash
claude run code-release-notes --autonomous
# Auto-publishes as v[last].[patch+1] (e.g., v2.1.0 → v2.1.1)
```

## How Multi-AI Works

**Workers:** Opus, Sonnet, Haiku independently categorize commits

**Arbiter:** Opus merges results using majority vote:
- If 2+ models agree → use their categorization
- If split → arbiter decides based on context
- Breaking changes: Opus validates to avoid false positives

**Result:** Robust categorization resistant to single-model bias

## Modifying Models

Edit `code-release-notes.js` line 150-156:

```javascript
const WORKERS = [
  'opus', 'sonnet', 'haiku',  // Claude models (always available)
  // 'gemini',                // Add other models as available
  // 'gpt-4',
]
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: claude run code-release-notes --autonomous
```

### GitLab CI Example

```yaml
release:
  script:
    - claude run code-release-notes --autonomous
  only:
    - tags
```

## Troubleshooting

**No commits found:** You're already at the last release tag

**Wrong categorization:** Edit WORKERS to add stronger models or adjust arbiter logic

**Version mismatch:** Specify version explicitly: `code-release-notes v2.0.0`

## For Next Session

This skill is now in the repo at `tools/code-release-notes*.js`.

To generate release notes for any future session:

```bash
cd /path/to/claude-global-skills
claude run code-release-notes --autonomous
```

It will automatically:
- Find all commits since last release
- Categorize them (multi-AI consensus)
- Generate structured release notes
- Tag and publish the release
