# Doc Solve Skill

**Autonomous documentation issue resolution with multi-AI consensus**

> **Similar to `/code-solve` but for documentation issues**

## Quick Start

```bash
/doc-solve 123                  # Resolve doc issue #123
/doc-solve loop                 # Resolve all open doc issues
/doc-solve --help               # Show detailed help
```

## What This Skill Does

**Autonomous documentation issue resolution:**

1. **Fetch Issue** - Get issue details from GitHub/GitLab
2. **Analyze** - Multiple AI workers propose solutions independently
3. **Judge** - Arbiter selects best solution
4. **Fix** - Apply changes to documentation files
5. **Verify** - Validate fix resolves the issue
6. **Submit** - Create PR with changes
7. **Update** - Comment on issue with resolution

**No manual intervention** - from issue to PR automatically.

## Commands

### Single Issue

```bash
# Resolve specific issue
/doc-solve 123

# With strategy configuration
/doc-solve 123 --consensus=single --execution=parallel      # Fast single arbiter
/doc-solve 123 --consensus=rotating --execution=parallel    # Democratic (default)
/doc-solve 123 --consensus=weighted --execution=cascade     # Adaptive smart

# Show AI attribution
/doc-solve 123 --comment-ai
```

### Loop Mode

```bash
# Resolve all open doc issues
/doc-solve loop

# Continuous resolution
/doc-solve loop single
```

## Arbiter Modes

### Rotating Arbiter (Default)

**Democratic consensus:**
- Multiple AI workers propose solutions
- Each AI judges other solutions
- Majority vote selects best approach
- More thorough, less biased

**Use when:**
- Quality is priority
- Complex documentation issues
- Multiple valid approaches

### Single Arbiter

**Faster resolution:**
- Multiple AI workers propose solutions
- Single arbiter AI judges all
- Faster but potentially biased

**Use when:**
- Speed is priority
- Simple documentation fixes
- Clear single solution

## Issue Resolution Process

### Step 1: Fetch Issue

```
📋 Fetching issue #123...
  Title: "Broken links in installation guide"
  Labels: documentation, bug
  Priority: high
```

### Step 2: Worker Analysis

```
🔍 Analyzing with 6 AI workers...

Worker 1 (codellama:13b):
  Approach: Find and replace all broken links
  Confidence: 0.85

Worker 2 (mistral:7b):
  Approach: Update links and add link checker
  Confidence: 0.90

Worker 3 (gemini-pro):
  Approach: Fix links, archive old URLs
  Confidence: 0.88
  
[... 3 more workers]
```

### Step 3: Arbiter Judgment

```
⚖️  Arbiter voting...

Worker 2 solution selected:
  Votes: 4/6 workers agree
  Confidence: 0.90
  Approach: Update links and add link checker
```

### Step 4: Apply Fix

```
✏️  Applying changes...
  Modified: docs/installation.md
    - Updated 5 broken links
    - Added link validation script
```

### Step 5: Verification

```
✅ Verifying fix...
  Link checker: All links valid ✓
  Markdown syntax: Valid ✓
  Examples tested: Pass ✓
```

### Step 6: Create PR

```
🔀 Creating pull request...
  Branch: doc-fix/issue-123
  PR #456: "Fix: Update broken links in installation guide"
  
  Changes:
  - docs/installation.md (5 links updated)
  - scripts/check-links.sh (new file)
```

### Step 7: Update Issue

```
💬 Commenting on issue #123...
  
  "Fixed by PR #456
  
  Changes:
  - Updated 5 broken links
  - Added automated link checker
  
  Verification:
  - All links now valid
  - Markdown syntax correct
  - Examples tested
  
  Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

## Examples

### Example 1: Fix Broken Links

```bash
/doc-solve 123
```

**Issue #123:** "Broken links in README"

**Resolution:**
- Find all broken links
- Update to current URLs
- Add link validation to CI
- Create PR

---

### Example 2: Fix Missing Examples

```bash
/doc-solve 124 single
```

**Issue #124:** "API documentation missing examples"

**Resolution:**
- Add code examples for each API method
- Include expected outputs
- Add usage notes
- Create PR

---

### Example 3: Fix Outdated Content

```bash
/doc-solve 125 rotating --comment-ai
```

**Issue #125:** "Installation guide outdated"

**Resolution:**
- Update version numbers
- Add new installation methods
- Update screenshots
- Verify all steps work
- Create PR with AI attribution

---

### Example 4: Resolve All Issues

```bash
/doc-solve loop
```

**Process:**
1. Fetch all open doc issues
2. Resolve each automatically
3. Create PRs for each
4. Continue until no issues remain

---

## Integration with Other Skills

### Review → Solve → Improve Workflow

```bash
# 1. Review documentation
/doc-review docs/

# 2. Review creates issues automatically
# Issues: #123, #124, #125

# 3. Solve all issues
/doc-solve loop

# 4. Improve to target score
/doc-improve docs/ --target-score 95
```

### CI/CD Integration

```yaml
# .gitlab-ci.yml
doc-quality:
  script:
    - /doc-review --json > review.json
    - CRITICAL=$(jq '.critical' review.json)
    - if [ "$CRITICAL" -gt 0 ]; then
        /doc-solve loop;
      fi
```

## Options

### Arbiter Options

```bash
--consensus=rotating --execution=parallel   # Democratic (default)
--consensus=single --execution=parallel     # Single arbiter (faster)
--consensus=weighted --execution=cascade    # Adaptive smart
```

### Comment Options

```bash
--comment-ai            # Show which AI models found/fixed issues
                        # (Default: OFF - no AI attribution)
```

### Loop Options

```bash
loop                    # Resolve all open doc issues
--continuous            # Keep running continuously
```

## Environment Variables

```bash
# Required (one of)
export GITHUB_TOKEN="ghp_..."
export GITLAB_TOKEN="glpat_..."

# Optional cloud AI services
export GEMINI_API_KEY="..."
export ANTHROPIC_API_KEY="..."
export OPENAI_API_KEY="..."
```

## Worker Models

Default AI models for solving:

1. **codellama:13b** (local via Ollama)
2. **mistral:7b** (local via Ollama)
3. **gemini-pro** (cloud, if GEMINI_API_KEY set)
4. **claude-3** (cloud, if ANTHROPIC_API_KEY set)
5. **gpt-4** (cloud, if OPENAI_API_KEY set)
6. **command-r** (cloud, if COHERE_API_KEY set)

## Issue Types Handled

### Content Issues
- Missing sections
- Incomplete information
- Outdated content
- Incorrect information

### Technical Issues
- Broken links
- Invalid code examples
- Wrong commands
- Missing prerequisites

### Writing Issues
- Grammar errors
- Spelling mistakes
- Unclear explanations
- Inconsistent style

### Format Issues
- Markdown syntax errors
- Broken tables
- Malformed lists
- Missing headings

## PR Creation

### Automatic Branch Naming

```
doc-fix/issue-123
doc-fix/broken-links
doc-fix/missing-examples
```

### Automatic Commit Messages

```
fix(docs): Update broken links in installation guide

Resolves #123

- Updated 5 broken links to current URLs
- Added automated link validation script
- Verified all links accessible

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Automatic PR Description

```markdown
## Summary
Fixes #123 - Broken links in installation guide

## Changes
- docs/installation.md - Updated 5 broken links
- scripts/check-links.sh - Added link validation

## Verification
- ✅ All links now valid (tested)
- ✅ Markdown syntax correct
- ✅ Added to CI pipeline

## AI-Assisted
This PR was created with assistance from Universal AI's doc-solve skill:
- Worker models: codellama:13b, mistral:7b, gemini-pro
- Arbiter: Rotating democratic consensus
- Confidence: 0.90

🤖 Generated with [Universal AI](https://gitlab.cee.redhat.com/sfloess/universal-ai)
```

## Verification Steps

Before creating PR, verifies:

1. **Markdown Syntax** - Valid markdown
2. **Links** - All links accessible
3. **Code Examples** - Syntax valid
4. **Commands** - Commands work
5. **Structure** - Headings, TOC correct
6. **Formatting** - Consistent style

## Comparison with Other Skills

| Skill | Purpose | Input | Output |
|-------|---------|-------|--------|
| `/doc-review` | Find issues | Documentation files | Issue reports |
| `/doc-solve` | Fix issues | Issue numbers | PRs with fixes |
| `/doc-improve` | Iterative improvement | Documentation files | Improved docs |

**Workflow:**
1. `/doc-review` creates issues
2. `/doc-solve` resolves issues  
3. `/doc-improve` polishes quality

## Limitations

### Cannot Handle

❌ **Subjective decisions** - "Is this section needed?"
❌ **Context-heavy rewrites** - Major structural changes
❌ **Domain expertise** - Highly technical domain knowledge
❌ **Image generation** - Creating new diagrams/screenshots

### Can Handle

✅ **Objective fixes** - Broken links, typos, syntax
✅ **Standard improvements** - Examples, clarity, completeness
✅ **Format fixes** - Markdown, structure, style
✅ **Validation** - Links, commands, syntax

## Error Handling

### Issue Not Found

```
❌ Issue #999 not found
   Check issue number and permissions
```

### Ambiguous Solution

```
⚠️  No consensus reached
   Workers split 3-3 on approach
   
   Manual resolution required
   See issue #123 for details
```

### Verification Failed

```
❌ Verification failed
   - Link checker: 2 links still broken
   
   Partial fix created, manual review needed
   See branch: doc-fix/issue-123-partial
```

## Best Practices

### When to Use `/doc-solve`

✅ **Clear, objective issues** - Broken links, typos, missing examples
✅ **Standard improvements** - Adding examples, fixing format
✅ **Batch processing** - Multiple similar issues
✅ **Automation** - CI/CD pipelines

### When to Fix Manually

🛑 **Subjective rewrites** - Major restructuring decisions
🛑 **Domain-specific** - Requires deep domain knowledge  
🛑 **Strategic changes** - Documentation strategy shifts
🛑 **Creative content** - New explanations, analogies

## See Also

- `/doc-review` - Find documentation issues
- `/doc-improve` - Iterative documentation improvement
- `/code-solve` - Code issue resolution (same pattern)
- `doc-solve.sh` - Implementation script
