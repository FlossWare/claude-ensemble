# Git LFS Locks - Quick Reference

## ⚠️ IMPORTANT: Requires Git Remote

Git LFS locks **require a remote server** (GitHub, GitLab, Bitbucket) that supports LFS.

**Works with:**
- GitHub repositories (public or private)
- GitLab repositories
- Bitbucket repositories
- Self-hosted Git servers with LFS support

**Does NOT work with:**
- Local-only repositories (no remote)
- Remotes without LFS support

---

## One-Time Setup (Per Repo)

```bash
cd /path/to/repo
git lfs install
git config lfs.locksverify true
```

---

## Daily Commands

### Lock Before Editing
```bash
claude-lock src/auth/login.ts
```

### Unlock After Commit
```bash
claude-unlock src/auth/login.ts
```

### View All Locks
```bash
claude-locks
```

---

## Common Scenarios

### Someone Else Has Lock
```
✗ ERROR: File is already locked by john@server-01

Options:
  1. Wait for john@server-01 to finish
  2. Contact john@server-01
  3. Emergency: git lfs unlock --force <file>
```

### Session Crashed With Lock
```bash
# View stale locks
git lfs locks

# Force unlock
git lfs unlock --force src/auth/login.ts
```

### Forgot to Unlock
```bash
# See your locks
git lfs locks

# Unlock all yours
git lfs locks --json | jq -r '.[] | .path' | \
  xargs -I{} claude-unlock {}
```

---

## Workflow Example

```bash
# 1. Check what's locked
claude-locks

# 2. Lock your files
claude-lock src/auth/login.ts
claude-lock src/auth/oauth.ts

# 3. Edit files
vim src/auth/login.ts
vim src/auth/oauth.ts

# 4. Commit
git add src/auth/*.ts
git commit -m "feat: add OAuth"

# 5. Unlock
claude-unlock src/auth/login.ts
claude-unlock src/auth/oauth.ts

# 6. Push
git push
```

---

## Emergency Commands

```bash
# View raw locks
git lfs locks

# Force unlock (use carefully!)
git lfs unlock --force <file>

# Unlock all stale locks (>6 hours)
git lfs locks --json | \
  jq -r --arg cutoff "$(date -d '6 hours ago' -Iseconds)" \
  '.[] | select(.locked_at < $cutoff) | .path' | \
  xargs -I{} git lfs unlock --force {}
```

---

## Troubleshooting

| Error | Solution |
|-------|----------|
| "missing protocol" | No remote configured. Add remote or use different approach. |
| "git: 'lfs' is not a git command" | Run `git lfs install` first |
| "not in a git repository" | `cd` to a git repo |
| "Lock already exists" | Someone else editing. Coordinate or force unlock. |

---

## Full Docs

See: `~/.claude/docs/git-lfs-locks-guide.md`
