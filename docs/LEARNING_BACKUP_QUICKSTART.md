# Learning Data Backup System - Quick Start

Rapid deployment guide for the multi-tier learning data backup system.

## 30-Second Setup

```bash
# 1. Install cron jobs
~/bin/setup-learning-backup-cron.sh

# 2. Test backup (runs immediately)
~/bin/backup-learning-data.sh

# 3. Verify it worked
~/bin/verify-learning-backups.sh
```

Done! Backups will now run daily at 2 AM.

## 5-Minute Configuration

### Optional: Email Notifications

```bash
# Add to ~/.bashrc or ~/.bash_profile
export BACKUP_NOTIFY_EMAIL="your@email.com"
export BACKUP_EMAIL_SUCCESS=false  # Only email on errors

# Reload
source ~/.bashrc
```

### Optional: Custom Backup Locations

Edit `~/.config/claude-backup/backup.conf`:

```bash
# Change NAS location (if needed)
NAS_BACKUP_ROOT="/mnt/nas/your-custom-path"

# Change fleet servers (if different)
FLEET_SERVERS=("your-server-01" "your-server-02")

# Adjust retention
DAILY_RETENTION=14  # Keep 14 days instead of 7
```

## Essential Commands

| Task | Command |
|------|---------|
| **Backup now** | `~/bin/backup-learning-data.sh` |
| **Restore latest** | `~/bin/restore-learning-data.sh` |
| **Verify backups** | `~/bin/verify-learning-backups.sh` |
| **List backups** | `~/bin/restore-learning-data.sh --list` |
| **Check logs** | `tail -f ~/logs/learning-backup.log` |

## Common Scenarios

### I need to restore everything

```bash
# Restore from NAS (fastest)
~/bin/restore-learning-data.sh nas latest
```

### I need to restore a specific date

```bash
# First, list available backups
~/bin/restore-learning-data.sh --list

# Then restore
~/bin/restore-learning-data.sh nas 2026-06-13
```

### NAS is down, restore from fleet

```bash
~/bin/restore-learning-data.sh server-01 latest
```

### I want to check backup health

```bash
~/bin/verify-learning-backups.sh
```

## What Gets Backed Up?

### Critical Data (Total ~21MB)
- Thompson Sampling state (`bandit-state.json`) - 1KB
- Learning database (`db/learning.db`) - 1.3MB
- Cost database (`db/costs.db`) - 80KB
- Discoveries (`discoveries.json`) - 4.3KB
- Session data (`session-registry.json`, `session-messages.json`) - 4KB
- All learning logs (`*.jsonl`) - 21MB

### Backup Locations
- **PRIMARY**: `/mnt/nas/chromadb-backups/learning-data/`
- **SECONDARY**: `server-01/02/03:/exports/backups/claude-learning/`
- **TERTIARY**: `aio-01:/exports/backups/claude-learning/` (weekly)

## Backup Schedule

| When | What | Where |
|------|------|-------|
| **Daily 2 AM** | Full backup | NAS + round-robin fleet server |
| **Sunday 2 AM** | Weekly full | NAS + all fleet + AIO |
| **1st of month** | Monthly full | All targets |
| **Daily 3 AM** | Verification | All backups |

## Retention

- **Daily**: 7 backups (1 week)
- **Weekly**: 4 backups (1 month)
- **Monthly**: 12 backups (1 year)

Old backups auto-delete after retention period.

## Monitoring

### Check Logs

```bash
# Main backup log
tail -f ~/logs/learning-backup.log

# Errors only
tail -f ~/logs/learning-backup-error.log

# Verification log
tail -f ~/logs/learning-backup-verify.log

# Search for problems
grep -i error ~/logs/learning-backup*.log
```

### Verify Health

```bash
# Full verification report
~/bin/verify-learning-backups.sh

# Quick check - last backup time
ls -lth /mnt/nas/chromadb-backups/learning-data/daily/ | head -5
```

## Troubleshooting

### Backup Failed

```bash
# Check what failed
cat ~/logs/learning-backup-error.log

# Verify NAS is mounted
mountpoint /mnt/nas

# Verify fleet SSH
ssh server-01 "echo OK"

# Try manual backup
~/bin/backup-learning-data.sh
```

### Restore Failed

```bash
# Check restore log
tail ~/logs/learning-restore.log

# Verify backup exists
~/bin/restore-learning-data.sh --list

# Try different source
~/bin/restore-learning-data.sh server-02 latest
```

### No Backups Found

```bash
# Run backup immediately
~/bin/backup-learning-data.sh

# Check backup location
ls -la /mnt/nas/chromadb-backups/learning-data/

# Verify cron is running
crontab -l | grep backup-learning
```

## Safety Features

### Restore Safety Backup

Every restore automatically creates a safety backup:

```
~/.claude/learning-backup-TIMESTAMP/
```

If restore goes wrong, the restore script shows you the rollback commands.

### Verification

Every backup is automatically verified for:
- Critical files present
- Reasonable size
- Metadata consistency
- File counts match

Failed verifications are logged and emailed (if configured).

## Performance

**Typical backup time**: 5-30 seconds
- NAS: ~5-10s (local, fast)
- Fleet: ~15-30s (network)
- AIO: ~20-40s (network)

**Disk usage**: ~21MB per snapshot
- Daily: 7 × 21MB = 147MB
- Weekly: 4 × 21MB = 84MB
- Monthly: 12 × 21MB = 252MB
- **Total per target**: ~483MB

**Multi-target total**: ~2.4GB across all servers

## Advanced Usage

### Force Specific Backup Type

```bash
# The script auto-detects daily/weekly/monthly based on date
# Weekly happens on Sunday, monthly on 1st of month
# Otherwise it's daily

# To test weekly backup manually, temporarily change date check
# or run on a Sunday
```

### Custom Retention

Edit `~/.config/claude-backup/backup.conf`:

```bash
DAILY_RETENTION=14   # 2 weeks
WEEKLY_RETENTION=8   # 2 months  
MONTHLY_RETENTION=24 # 2 years
```

### Disable Specific Targets

Comment out in `backup.conf`:

```bash
# FLEET_SERVERS=("server-01" "server-02" "server-03")
FLEET_SERVERS=()  # Disable fleet backups
```

### Non-Interactive Restore

```bash
# Skip confirmation prompt
BACKUP_NO_CONFIRM=1 ~/bin/restore-learning-data.sh nas latest
```

## Integration

### Grafana Dashboard

See `GRAFANA_SETUP.md` for monitoring integration.

### Pre/Post Hooks

Add to `backup.conf`:

```bash
# Run before backup
PRE_BACKUP_HOOK="/path/to/script.sh"

# Run after backup
POST_BACKUP_HOOK="/path/to/script.sh"
```

### CI/CD

```yaml
# In your CI pipeline
- name: Backup Learning Data
  run: ~/bin/backup-learning-data.sh
  
- name: Verify Backup
  run: ~/bin/verify-learning-backups.sh
```

## Next Steps

- Read full documentation: `LEARNING_BACKUP_SYSTEM.md`
- Configure email notifications
- Test restore procedure
- Set up monitoring dashboard
- Review logs weekly

## Support Checklist

If you have issues:

1. ✓ Check logs: `~/logs/learning-backup*.log`
2. ✓ Run verification: `~/bin/verify-learning-backups.sh`
3. ✓ Test NAS mount: `mountpoint /mnt/nas`
4. ✓ Test SSH: `ssh server-01 "echo OK"`
5. ✓ Check cron: `crontab -l | grep backup`
6. ✓ Check disk space: `df -h /mnt/nas`

---

**Quick Reference Card**

```
BACKUP:  ~/bin/backup-learning-data.sh
RESTORE: ~/bin/restore-learning-data.sh [source] [date]
VERIFY:  ~/bin/verify-learning-backups.sh
LIST:    ~/bin/restore-learning-data.sh --list
LOGS:    ~/logs/learning-backup*.log
CONFIG:  ~/.config/claude-backup/backup.conf
CRON:    crontab -l | grep backup-learning
```

---

**Last Updated:** 2026-06-14
**Version:** 1.0.0
