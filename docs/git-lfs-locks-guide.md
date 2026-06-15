# Git LFS Locks - Fleet Session Coordination

## ✅ FLEET CONSENSUS DECISION

After multi-AI review (Opus, Sonnet, Haiku, Fable), **unanimous 1st choice** for session coordination:
- **Prevents** conflicts (not just detects)
- Battle-tested (Epic Games, Microsoft)
- Zero infrastructure overhead
- Works offline

## What's Installed (Fleet-Wide)

✅ **All nodes have git-lfs:**
- laptop-01 (Fedora): git-lfs/3.7.1
- aio-01 (Debian): git-lfs/3.6.1  
- server-01 (Debian): git-lfs/3.6.1
- server-02 (Debian): git-lfs/3.6.1
- server-03 (Debian): git-lfs/3.6.1

✅ **Wrapper scripts deployed:**
- `~/.local/bin/claude-lock` - Lock file before editing
- `~/.local/bin/claude-unlock` - Unlock after commit
- `~/.local/bin/claude-locks` - View all locks

## ⚠️ Opt-In Per Repository

**Important:** Git LFS locks are **opt-in per repository**. Existing sessions/workflows are **not affected** unless you enable it.

## How To Enable (Per Repo)

### 1. Initialize Git LFS in Your Repo

```bash
cd /path/to/your/repo

# One-time setup per repo
git lfs install

# Enable lock verification (recommended)
git config lfs.locksverify true
```

**What this does:**
- Adds LFS hooks to `.git/hooks/`
- Creates `.git/lfs/` directory
- **Does NOT affect** existing git operations
- **Does NOT track** any files automatically

### 2. Test It Works

```bash
# Create a test file
echo "test" > test-lock.txt
git add test-lock.txt
git commit -m "test file for lfs locks"

# Try locking
claude-lock test-lock.txt
# Should show: ✓ Locked: test-lock.txt

# View locks
claude-locks
# Should show your lock

# Unlock
claude-unlock test-lock.txt
# Should show: ✓ Unlocked: test-lock.txt
```

## Basic Workflow

### Before Editing a File

```bash
# Lock the file
claude-lock src/auth/login.ts
```

**Output if successful:**
```
✓ Locked: src/auth/login.ts
Remember to unlock after committing: claude-unlock src/auth/login.ts
```

**Output if already locked:**
```
✗ ERROR: File is already locked by john@server-01

Options:
  1. Wait for john@server-01 to finish and unlock
  2. Contact john@server-01 to coordinate
  3. Force unlock (emergency only): git lfs unlock --force src/auth/login.ts
```

### After Committing

```bash
# Edit the file
vim src/auth/login.ts

# Commit your changes
git add src/auth/login.ts
git commit -m "feat: add OAuth support"

# Unlock
claude-unlock src/auth/login.ts
```

### Check Who Has Locks

```bash
claude-locks
```

**Output:**
```
Active file locks in my-project:

  src/auth/login.ts
    Locked by: john@server-01
    Since: 2026-06-13T20:00:00Z

  src/auth/oauth.ts
    Locked by: you@laptop-01
    Since: 2026-06-13T20:05:00Z
```

## Advanced Usage

### Lock Multiple Files

```bash
claude-lock src/auth/login.ts
claude-lock src/auth/oauth.ts
claude-lock src/auth/providers.ts
```

### Force Unlock (Emergency)

If a session crashed with locks held:

```bash
# See who owns the lock
git lfs locks

# Force unlock (use carefully!)
git lfs unlock --force src/auth/login.ts
```

### Pre-Commit Hook (Auto-Lock)

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Auto-lock files being committed

for file in $(git diff --cached --name-only); do
    # Try to lock (fails if already locked by someone else)
    git lfs lock "$file" 2>/dev/null || {
        owner=$(git lfs locks --json | jq -r ".[] | select(.path==\"$file\") | .owner.name")
        if [[ -n "$owner" && "$owner" != "$USER@$(hostname)" ]]; then
            echo "ERROR: $file is locked by $owner"
            echo "Cannot commit files locked by another session"
            exit 1
        fi
    }
done
```

### Post-Commit Hook (Auto-Unlock)

Add to `.git/hooks/post-commit`:

```bash
#!/bin/bash
# Auto-unlock files that were just committed

for file in $(git diff-tree --no-commit-id --name-only -r HEAD); do
    git lfs unlock "$file" 2>/dev/null || true
done
```

## What Gets Affected

### ✅ No Impact On:

- Existing git operations (clone, pull, push, commit, etc.)
- Repositories without LFS initialized
- Files that aren't locked
- Read-only operations (grep, search, browse)
- Other sessions' workflows

### ⚠️ Changes:

- **With locks enabled:** Must unlock before others can edit
- **Lock verification on:** Push fails if you changed a locked file you don't own

## Troubleshooting

### "git: 'lfs' is not a git command"

**Solution:** Run `git lfs install` in your repo first

### "Failed to call git: exit status 128"

**Solution:** You're not in a git repository. `cd` to a repo first.

### "Lock already exists"

**Solution:** Someone else is editing that file. Options:
1. Work on different files
2. Coordinate with lock owner
3. Emergency: `git lfs unlock --force <file>` (ask first!)

### "Unable to push"

**Error:** "push has file locks"

**Solution:** Unlock files before pushing:
```bash
# See your locks
git lfs locks

# Unlock each file
claude-unlock <file>

# Or unlock all yours
git lfs locks --json | jq -r '.[] | .path' | xargs -I{} git lfs unlock {}
```

## Automated Cleanup

Stale locks (from crashed sessions) can be cleaned up automatically.

### Create Cleanup Script

```bash
cat > ~/.local/bin/claude-clean-stale-locks << 'EOF'
#!/bin/bash
# Clean up locks older than 6 hours

cd /path/to/your/repo

git lfs locks --json | \
  jq -r --arg cutoff "$(date -d '6 hours ago' -Iseconds)" \
  '.[] | select(.locked_at < $cutoff) | .path' | \
  while read -r file; do
    echo "Cleaning stale lock: $file"
    git lfs unlock --force "$file"
  done
EOF

chmod +x ~/.local/bin/claude-clean-stale-locks
```

### Add to Cron (Optional)

```bash
# Run every 6 hours
(crontab -l 2>/dev/null; echo "0 */6 * * * ~/.local/bin/claude-clean-stale-locks") | crontab -
```

## Integration with Claude Sessions

### Manual Lock/Unlock

Before editing:
```bash
claude-lock src/file.ts
# Edit file
# Commit
claude-unlock src/file.ts
```

### Semi-Automatic (Recommended)

Add to your workflow in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "pre-edit": "claude-lock $FILE",
    "post-commit": "claude-unlock $FILE"
  }
}
```

### Fully Automatic (Advanced)

Use pre-commit/post-commit hooks (see Advanced Usage above).

## Best Practices

1. **Lock before editing** - Get in habit: `claude-lock <file>` before opening editor
2. **Unlock after committing** - Don't hold locks longer than needed
3. **Check locks first** - Run `claude-locks` to see what's locked
4. **Communicate conflicts** - If file is locked, coordinate with owner
5. **Force unlock sparingly** - Only in emergencies (crashed sessions)
6. **Enable per-project** - Not every repo needs locks, enable where conflicts are likely

## When NOT to Use

- **Solo work** - If you're the only one editing a repo, locks add overhead
- **Read-only repos** - No editing = no conflicts
- **Non-git workflows** - LFS locks are git-specific
- **Very frequent commits** - Lock/unlock churn might be annoying

## FAQ

**Q: Do I need to enable this in every repo?**  
A: No, it's opt-in. Enable in repos where multiple sessions might conflict.

**Q: What if I forget to unlock?**  
A: Others can see you own the lock and ask you. Automated cleanup runs every 6 hours (if configured).

**Q: Can I lock directories?**  
A: No, only files. Lock multiple files individually if needed.

**Q: Does this work offline?**  
A: Partially. You can lock/unlock locally, but coordination requires network (push/pull locks to/from remote).

**Q: What if the LFS server is down?**  
A: You can work locally, but lock coordination won't happen. Same as network outage.

**Q: How do I disable it?**  
A: Just don't use `claude-lock`. LFS install doesn't affect normal git operations.

## Summary

✅ **Deployed fleet-wide, opt-in per repo**  
✅ **Zero impact on existing workflows**  
✅ **Fleet consensus: Best solution for preventing edit conflicts**

**Next steps:**
1. Choose a repo where conflicts are likely
2. Run `git lfs install` in that repo
3. Try locking a file with `claude-lock <file>`
4. Edit, commit, unlock
5. Enable in more repos as needed
