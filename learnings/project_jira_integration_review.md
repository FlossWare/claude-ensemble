---
name: project-jira-integration-review
description: "JIRA integration code review findings: security issues (token exposure), reliability issues (fragile parsing), code quality issues"
metadata: 
  node_type: memory
  type: project
  date: 2026-05-18
  originSessionId: 8c2c0c92-e4f2-459b-8fd6-8aabd685e77a
---

# JIRA Integration Code Review

**Reviewed:** 2026-05-18

## Architecture

The JIRA integration automates ticket updates through the CI/CD pipeline:

1. **extract_jira** - Extracts CPSEARCH-[0-9]+ tickets from git commits since last deployment
2. **add_jira_version** - Adds release version to extracted tickets
3. **update_*_jira_status** - Updates ticket status as deployment progresses (QA → Stage → Prod)
4. **comment_*_on_jira** - Adds automated test verification comments at each environment

**Scripts location:** `ci/scripts/`
- `addVersionToJira.sh` - Adds version label and version field to tickets
- `updateJiraStatus.sh` - Transitions tickets through workflow states
- `commentOnJiras.sh` - Posts comments about environment verification
- `getJiras.sh` - Unused script (not called in CI/CD)

## Critical Issues Found

### Security

**Token exposure in process list:**
- All scripts pass `$JIRA_AUTH_TOKEN` as CLI argument to curl
- Visible in `ps aux` output while running
- **Fix:** Pass token via environment variable or read from file

**No input validation:**
- Scripts don't validate required parameters ($1, $2, $3)
- Missing parameter could cause unintended API calls or cryptic errors
- **Fix:** Add validation at start of each script

### Reliability

**Fragile JSON parsing:**
```bash
# Current (all 3 scripts):
current_status=$(echo "$response" | grep -o '"name":"[^"]*"' | head -1 | sed 's/"name":"//;s/"//')

# Should use jq:
current_status=$(echo "$response" | jq -r '.fields.status.name')
```
- grep/sed breaks on JSON formatting changes
- jq is already available (used in getJiras.sh)
- **Fix:** Use jq consistently across all scripts

**No retry logic:**
- API failures cause silent failures in some cases
- `|| true` in addVersionToJira.sh:46-52 masks all errors
- **Fix:** Add retry with exponential backoff for transient failures

**Duplicate code:**
- Status-checking logic duplicated in 3 scripts (addVersionToJira.sh, updateJiraStatus.sh, commentOnJiras.sh)
- **Fix:** Extract to shared function in `ci/scripts/lib/jira-common.sh`

**Missing error context:**
- Error messages don't include API response for debugging
- Example: "ERROR: Could not fetch status for $jira. Skipping..."
- **Fix:** Log actual API response on errors

### Code Quality

**Typos:**
- getJiras.sh lines 9, 12: "Dubug" → "Debug"

**Unused script:**
- `getJiras.sh` not referenced anywhere in `.gitlab-ci.yml`
- **Decision needed:** Remove or integrate

**Inconsistent quoting:**
- Mixed quote styles for same curl headers
- Example: `--header 'Authorization: Bearer '$1''` vs `--header "Authorization: Bearer $1"`

**Variable naming:**
- addVersionToJira.sh: `VERSION_NAME="$3"` declared but never used (uses `$3` directly)

**Hardcoded regex:**
- `.gitlab-ci.yml` line 411: `grep -oE 'CPSEARCH-[0-9]+'`
- Should be configurable if project key changes

**Redundant dependencies:**
```yaml
comment_qa_on_jira:
  needs:
   - update_qa_jira_status
   - extract_jira  # Redundant - already dependency of update_qa_jira_status
```

**Silent failures:**
- `allow_failure: true` on `extract_jira` means extraction failures go unnoticed
- Should log/notify on failure

## Recommended Fixes

### Immediate (High Priority)
1. Use jq for all JSON parsing (replace grep/sed)
2. Add input validation to all scripts
3. Fix typos in getJiras.sh
4. Log API responses on errors for debugging

### Security (High Priority)
5. Pass JIRA token via environment instead of CLI argument
6. Consider GitLab secrets for token rotation

### Code Quality (Medium Priority)
7. Extract shared status-check function to `ci/scripts/lib/jira-common.sh`
8. Add retry logic with exponential backoff for API calls
9. Remove unused getJiras.sh or integrate if needed
10. Standardize quote styles and variable usage

## Status

**Review completed:** 2026-05-18  
**Fixes implemented:** None yet  
**Next action:** User to decide which fixes to prioritize

**Why this matters:** The JIRA integration runs on every release deployment. Security issues (token exposure) and reliability issues (fragile parsing, no retries) could cause failed deployments or missed ticket updates.
