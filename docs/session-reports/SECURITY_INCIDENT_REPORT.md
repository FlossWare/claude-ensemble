# 🚨 SECURITY INCIDENT REPORT
**Date:** 2026-06-16 00:20 UTC  
**Severity:** HIGH  
**Status:** DETECTED - AWAITING REMEDIATION

---

## Issue

API keys were accidentally committed to GitLab repository:
- **Repository:** `~/.claude/repos/claude-global-skills`
- **Branch:** main
- **Commits:** 988a464, 9793b16

---

## Exposed Keys

### Confirmed Exposed in Git History

1. **GROQ_API_KEY**
   - Value: `[REDACTED - key rotated]`
   - File: `memory/reference_groq_integration.md` (commit 988a464)

2. **OPENROUTER_API_KEY**
   - Value: `[REDACTED - key rotated]`
   - File: `FREE-API-SETUP.md` (commit 988a464)

### Potentially Exposed

3. **memory/.secrets.md** (if committed)
   - May contain: JIRA_API_TOKEN, CEREBRAS_API_KEY, CLOUDFLARE_API_KEY, etc.

---

## Timeline

- **2026-06-15 16:07** - Keys committed in commit 988a464
- **2026-06-16 00:18** - Keys detected during environment restore
- **2026-06-16 00:19** - Files removed from working tree
- **2026-06-16 00:19** - .gitignore updated to prevent future exposure
- **2026-06-16 00:20** - Security commit a5974d0 created

---

## Current Status

✅ **Mitigations Applied:**
- Files removed from working tree
- .gitignore updated with comprehensive rules
- Documentation moved to home directory (~/) instead of git repo

❌ **Still At Risk:**
- Keys exist in git history (commits 988a464, 9793b16)
- If repo was pushed to remote, keys are exposed publicly
- Keys are still valid and can be used by anyone with repo access

---

## Remediation Options

### Option 1: Rotate All Exposed Keys (RECOMMENDED)

**Pros:**
- Safest option
- No risk of data loss
- Preserves git history for legitimate files

**Cons:**
- Requires getting new API keys from providers

**Steps:**
1. Rotate Groq API key: https://console.groq.com/keys
2. Rotate OpenRouter API key: https://openrouter.ai/keys
3. Check if Jira/other keys were exposed, rotate if needed
4. Update ~/.bashrc with new keys
5. Update backup files with new keys

### Option 2: Rewrite Git History (DESTRUCTIVE)

**Pros:**
- Removes keys from all git history
- No need to rotate keys

**Cons:**
- **VERY DANGEROUS** - can destroy work
- Requires force-push (breaks others' clones)
- May lose legitimate commits

**Tools:**
- `git filter-repo` (recommended)
- `BFG Repo-Cleaner`

**NOT RECOMMENDED** unless you're 100% certain no one else has cloned the repo.

---

## Immediate Actions Required

### 1. Check if Repo Was Pushed

```bash
cd ~/.claude/repos/claude-global-skills
git remote -v
git log --branches --not --remotes  # Unpushed commits
```

**If remote exists and was pushed:** Keys are PUBLIC - MUST rotate immediately.  
**If no remote or not pushed:** Keys are only local - can choose either option.

### 2. Rotate Keys (SAFEST)

```bash
# Visit these URLs and generate new keys:
# - Groq: https://console.groq.com/keys
# - OpenRouter: https://openrouter.ai/keys
# - Jira: https://id.atlassian.com/manage-profile/security/api-tokens

# Update ~/.bashrc
vim ~/.bashrc
# Replace old keys with new ones

# Verify
source ~/.bashrc
echo $GROQ_API_KEY
```

### 3. Verify .gitignore Is Working

```bash
cd ~/.claude/repos/claude-global-skills

# Try to stage a test file with "API_KEY"
echo "test GROQ_API_KEY=fake" > test-secret.md
git add test-secret.md 2>&1 | grep -i "ignored"
# Should see: "The following paths are ignored by one of your .gitignore files"

rm test-secret.md
```

---

## Prevention Going Forward

### ✅ Implemented

1. `.gitignore` rules added:
   - `*API_KEY*`, `*TOKEN*`, `*SECRET*`
   - `*.env`, `.env.*`
   - `*secrets*`, `.secrets.md`
   - `INTEGRATIONS_INVENTORY.md`
   - Backup/restore scripts

2. Documentation moved to home directory:
   - `~/INTEGRATIONS_INVENTORY.md` (not in git)
   - `~/DISASTER_RECOVERY_GUIDE.md` (not in git)
   - `~/.claude/projects/-home-sfloess/memory/.secrets.md` (not in git)

### 🔄 TODO

- [ ] Rotate exposed API keys
- [ ] Check git remote status
- [ ] Verify no other keys in git history
- [ ] Add pre-commit hook to scan for keys
- [ ] Document key rotation in memory

---

## Verification Commands

```bash
# Check what's in git history
cd ~/.claude/repos/claude-global-skills
git log --all --full-history --source --all -- '*secret*' '*API*'

# Search for keys in history
git log -p --all | grep -E "gsk_|sk-or-v1|ATATT3x"

# Check if pushed to remote
git log origin/main..main 2>&1

# Verify .gitignore works
git status --ignored
```

---

## Related Files

- Git repository: `~/.claude/repos/claude-global-skills`
- Secure storage: `~/.claude/projects/-home-sfloess/memory/.secrets.md` (600 perms, not in git)
- Environment: `~/.bashrc` (contains current keys)
- Backups: `/mnt/nas/claude-backups/LATEST/config/bashrc`

---

**RECOMMENDATION:** Rotate all exposed API keys immediately. This is the safest option and takes <10 minutes.
