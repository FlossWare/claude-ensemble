# Doc-Improve Skill

**Continuous documentation quality improvement loop using review → resolve → review cycles.**

> **Iteratively improve documentation quality until issues converge to zero or max iterations reached.**

## Quick Start

```bash
/doc-improve                     # Interactive: prompts for options
/doc-improve --max-iterations 5  # Run up to 5 improvement cycles
/doc-improve --auto              # Fully autonomous until no issues remain
/doc-improve --target-score 95   # Improve until quality score ≥ 95%
/doc-improve --path docs/        # Focus on specific directory
```

## What This Skill Does

**Continuous documentation improvement loop:**

1. **Doc-Review** → Find all documentation issues (read-only, multi-AI arbiter)
2. **Prioritize** → Rank issues by severity/impact
3. **Doc-Resolve** → Fix top N issues (multi-AI arbiter)
4. **Verify** → Re-review to check fixes didn't break anything
5. **Repeat** → Loop until stopping condition met

**Documentation issues detected:**
- Missing documentation
- Outdated examples
- Broken links
- Inconsistent formatting
- Grammar/spelling errors
- Unclear explanations
- Missing code samples
- Incomplete API docs
- Accessibility problems
- SEO issues

**Stopping conditions:**
- ✅ No new issues found
- ✅ Quality score target reached
- ✅ Max iterations limit
- ✅ User interruption (Ctrl+C)

## Arguments

- `--max-iterations N` - Maximum improvement cycles (default: 10)
- `--auto` - Fully autonomous mode (no prompts)
- `--target-score N` - Stop when quality score ≥ N% (default: 95)
- `--path DIR` - Focus on specific directory/file
- `--batch-size N` - Fix N issues per iteration (default: 5)
- `--create-prs` - Create PR after each iteration (default: one final PR)
- `--arbiter MODE` - Use `single` or `rotating` arbiter (default: rotating)
- `--comment-ai LEVEL` - AI attribution level: none|basic|detailed|full|verbose
- `--format` - Fix formatting issues (markdown, restructuredtext, etc.)
- `--links` - Check and fix broken links
- `--examples` - Update outdated code examples
- `--grammar` - Fix grammar and spelling
- `--completeness` - Add missing sections/content

## Modes

### Default Mode (Guided)

Prompts for confirmation between iterations:

```bash
/doc-improve
```

**Output:**
```
🔍 Iteration 1: Documentation Review
   Found: 18 issues (3 critical, 8 major, 7 minor)

   Critical:
   - README.md missing installation section
   - API docs completely outdated
   - 5 broken external links

🔧 Fix 3 critical issues? [Y/n]: y

🤖 Resolving issues...
   ✅ Added installation section to README.md
   ✅ Updated API docs (12 methods updated)
   ✅ Fixed 5 broken links

🔍 Iteration 2: Documentation Review
   Found: 12 issues (0 critical, 5 major, 7 minor)
   
Continue? [Y/n]: y
```

### Auto Mode (Autonomous)

Runs until convergence or max iterations:

```bash
/doc-improve --auto --max-iterations 10
```

**Runs completely unattended:**
- Review → Fix → Review → Fix ...
- Creates final PR with all improvements
- Posts summary to issue/PR

### Target Score Mode

Improves until quality threshold met:

```bash
/doc-improve --target-score 90
```

**Quality score calculation:**
```
Score = 100 - (critical×10 + major×5 + minor×1)
```

**Example:**
```
Iteration 1: Score 70% (3 crit, 8 maj, 7 min)
Iteration 2: Score 85% (0 crit, 5 maj, 7 min)
Iteration 3: Score 91% (0 crit, 2 maj, 4 min) ✅ Target reached!
```

## Documentation Issue Types

### Critical Issues (Score -10 each)
- Missing critical documentation (README, installation, getting started)
- Completely outdated API documentation
- Multiple broken critical links
- Security-sensitive documentation errors
- Accessibility blockers

### Major Issues (Score -5 each)
- Incomplete API documentation
- Outdated code examples
- Missing important sections
- Broken non-critical links
- Inconsistent formatting across files
- Poor navigation structure

### Minor Issues (Score -1 each)
- Typos and grammar errors
- Minor formatting inconsistencies
- Missing code syntax highlighting
- Suboptimal headings
- Missing alt text on images
- Outdated timestamps

## Examples

### Example 1: Quick README Improvement

```bash
/doc-improve --path README.md --max-iterations 1
```

Focuses on one file, one pass.

### Example 2: Thorough API Docs

```bash
/doc-improve --path docs/api/ --auto --target-score 100
```

Polishes API docs to perfection.

### Example 3: Fix Broken Links

```bash
/doc-improve --links --auto
```

Scans and fixes all broken links across documentation.

### Example 4: Update Examples

```bash
/doc-improve --examples --path docs/tutorials/ --auto
```

Updates code examples to match current API.

### Example 5: Complete Documentation Audit

```bash
/doc-improve --auto --max-iterations 10 \
  --format --links --examples --grammar --completeness
```

Full documentation improvement with all checks enabled.

## Iteration Details

Each iteration runs:

### 1. Review Phase (Read-Only)

```bash
# Checks performed:
- Missing sections analysis
- Link validation (internal + external)
- Code example verification
- Grammar and spelling
- Markdown/RST formatting
- Accessibility audit
- Completeness check
- Consistency analysis

Workers: [GPT-4, Claude, Gemini, Mistral]
Arbiter: Rotating consensus
Output: Prioritized issue list
```

### 2. Triage Phase

```bash
Issues categorized by:
- Severity: critical, major, minor
- Type: content, format, links, examples, grammar
- Impact: blocking, degrading, cosmetic
- Effort: trivial, moderate, complex

Top N selected for fixing (--batch-size)
```

### 3. Resolve Phase (Writes Files)

```bash
# Fixes applied:
- Add missing content
- Update outdated information
- Fix broken links
- Correct grammar/spelling
- Reformat markdown/RST
- Add code examples
- Improve headings
- Fix accessibility issues

Workers: Generate solutions for each issue
Arbiter: Votes on best solution per issue
Validation: Markdown/RST syntax, link check
Apply: Write fixes to files
```

### 4. Verification Phase

```bash
# Re-run doc-review to check:
- Original issues fixed? ✅
- New issues introduced? ❌
- Links still valid? ✅
- Examples still work? ✅

Rollback if fixes broke something!
```

## Safety Features

### Rollback on Regression

If fixes introduce new critical issues:
```bash
⚠️  Iteration 3: Fix introduced broken links!
🔙 Rolling back iteration 3...
✅ Restored to iteration 2 state
```

### Link Validation

All links checked before and after fixes:
```bash
✓ Internal links: 45/45 valid
✓ External links: 38/40 valid
⚠ 2 external links unreachable (may be temporary)
```

### Example Verification

Code examples validated:
```bash
✓ Python examples: 12/12 run successfully
✓ Shell examples: 8/8 exit code 0
⚠ 1 JavaScript example outdated (flagged for review)
```

## Output

### Summary Report

After all iterations:

```markdown
## 📚 Documentation Improvement Summary

**Total Iterations**: 4
**Time Elapsed**: 12m 18s

### Progress

| Iteration | Critical | Major | Minor | Score | Time |
|-----------|----------|-------|-------|-------|------|
| Start     | 3        | 8     | 7     | 70%   | -    |
| 1         | 0        | 5     | 7     | 85%   | 3m   |
| 2         | 0        | 2     | 5     | 91%   | 4m   |
| 3         | 0        | 1     | 2     | 94%   | 3m   |
| 4         | 0        | 0     | 1     | 96%   | 2m   |

### Issues Fixed

**Critical (3):**
- ✅ Added missing installation section to README.md
- ✅ Updated completely outdated API documentation
- ✅ Fixed 5 broken critical links

**Major (8):**
- ✅ Added code examples to 12 tutorial pages
- ✅ Fixed inconsistent markdown formatting across 15 files
- ✅ Updated 8 outdated code samples
...

### Files Changed

- README.md (+45, -12)
- docs/api/methods.md (+156, -89)
- docs/tutorials/*.md (+234, -123)
- docs/guides/quickstart.md (+67, -34)

### Pull Request

Created: #457 "Documentation improvement - 18 issues resolved"
Link: https://github.com/org/repo/pull/457
```

## Use Cases

### 1. Onboarding Documentation

```bash
# Ensure new contributors have clear docs
/doc-improve --path docs/contributing/ --auto --target-score 100
```

### 2. Release Documentation Update

```bash
# Update docs for new release
/doc-improve --examples --auto --path docs/
```

### 3. Link Rot Prevention

```bash
# Regular link checking
/doc-improve --links --auto
```

### 4. Grammar/Spelling Cleanup

```bash
# Polish existing content
/doc-improve --grammar --auto
```

### 5. Documentation Completeness Audit

```bash
# Find and fill gaps
/doc-improve --completeness --auto --max-iterations 10
```

## Configuration

### Environment Variables

```bash
# Max parallel workers
export DOC_IMPROVE_WORKERS=4

# Default batch size
export DOC_IMPROVE_BATCH_SIZE=5

# Link check timeout
export DOC_IMPROVE_LINK_TIMEOUT=10

# Default formats to check
export DOC_IMPROVE_FORMATS="markdown,rst,asciidoc"
```

### Config File

`.doc-improve.yaml`:
```yaml
max_iterations: 10
target_score: 95
batch_size: 5
arbiter: rotating
create_prs: false
comment_ai: detailed

# Checks to enable
checks:
  format: true
  links: true
  examples: true
  grammar: true
  completeness: true
  accessibility: true

# Stopping conditions
stop_on:
  - no_issues
  - target_reached
  - max_iterations

# Safety
rollback_on_regression: true
verify_examples: true
check_links_after_fix: true
```

## Integration

### With CI/CD

**GitLab CI:**
```yaml
docs_quality:
  script:
    - /doc-improve --auto --max-iterations 3 --links
  only:
    - merge_requests
```

**GitHub Actions:**
```yaml
- name: Documentation Improvement
  run: |
    /doc-improve --auto --target-score 90
```

### With Git Hooks

**Pre-commit:**
```bash
/doc-improve --path $(git diff --cached --name-only '*.md') --max-iterations 1
```

## Advanced Features

### Multi-Format Support

Supports multiple documentation formats:
- Markdown (`.md`)
- reStructuredText (`.rst`)
- AsciiDoc (`.adoc`)
- HTML documentation
- Sphinx projects
- MkDocs projects
- Docusaurus projects

### Smart Link Checking

```bash
# Check internal links only (fast)
/doc-improve --links --internal-only

# Check external links (slower)
/doc-improve --links --external-only

# Retry failed links
/doc-improve --links --retry-failed
```

### Example Testing

```bash
# Verify code examples still work
/doc-improve --examples --test-examples

# Update examples to new API
/doc-improve --examples --update-api
```

## Technical Details

### Architecture

```
┌─────────────────────────────────────┐
│  Doc-Improve Orchestrator           │
│  (Main Loop Controller)             │
└──────────┬──────────────────────────┘
           │
           ├─► Iteration 1
           │   ├─► doc-review (4 workers + arbiter)
           │   ├─► Prioritize & Select
           │   ├─► doc-resolve (4 workers + arbiter)
           │   └─► Verify & Validate
           │
           ├─► Iteration 2
           │   └─► ...
           │
           └─► Convergence Check
               └─► Final Report & PR
```

### State Tracking

Each iteration stores:
- Issue snapshot (before)
- Fixes applied
- Issue snapshot (after)
- Files changed
- Link check results
- Example validation results
- Metrics

## See Also

- `/code-improve` - Code quality improvement loop
- `/doc-review` - One-shot documentation review
- `/doc-resolve` - One-shot documentation fix
- `AI_ATTRIBUTION_DETAILED.md` - Attribution options
