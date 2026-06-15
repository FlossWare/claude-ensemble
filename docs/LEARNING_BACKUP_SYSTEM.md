# Learning Data Backup System

Comprehensive multi-tier backup solution for Claude learning data with redundancy across NAS and fleet servers.

## Quick Start

### Install Backup System

```bash
# Install cron jobs
~/bin/setup-learning-backup-cron.sh

# Test backup immediately
~/bin/backup-learning-data.sh

# Verify backups
~/bin/verify-learning-backups.sh
```

### Restore from Backup

```bash
# Restore latest from NAS (default)
~/bin/restore-learning-data.sh

# Restore specific date from NAS
~/bin/restore-learning-data.sh nas 2026-06-13

# Restore from fleet server
~/bin/restore-learning-data.sh server-02

# List all available backups
~/bin/restore-learning-data.sh --list
```

## Architecture

### Multi-Tier Backup Strategy

1. **PRIMARY: NAS** (`/mnt/nas/backups/claude-learning/`)
   - Fast local backups
   - Daily, weekly, monthly snapshots
   - Retention: 7 daily, 4 weekly, 12 monthly

2. **SECONDARY: Fleet Servers** (Round-robin)
   - `server-01:/exports/backups/claude-learning/`
   - `server-02:/exports/backups/claude-learning/`
   - `server-03:/exports/backups/claude-learning/`
   - Distributed redundancy
   - Day-of-month round-robin (Day 1→server-01, Day 2→server-02, etc.)

3. **TERTIARY: AIO Server** (Weekly only)
   - `aio-01:/exports/backups/claude-learning/`
   - Full weekly backup
   - Long-term archive

### Data Backed Up

| Data Type | Location | Size | Criticality |
|-----------|----------|------|-------------|
| Thompson Sampling | `~/.claude/learning/bandit-state.json` | 1KB | Critical |
| Learning Database | `~/.claude/learning/db/learning.db` | 1.3MB | Critical |
| Cost Database | `~/.claude/learning/db/costs.db` | 80KB | High |
| Discoveries | `learning/discoveries.json` | 4.3KB | Critical |
| Session Registry | `learning/session-registry.json` | 1KB | High |
| Session Messages | `learning/session-messages.json` | 3KB | High |
| Execution Logs | `~/.claude/learning/*.jsonl` | 21MB | Medium |
| Learning Files | `~/.claude/learning/*` | 21MB total | Varies |

## Backup Schedule

```
Daily:   2:00 AM - Full backup to NAS + round-robin fleet server
Weekly:  Sunday 2:00 AM - Full backup to NAS + fleet + AIO
Monthly: 1st of month 2:00 AM - Full backup to all targets

Verification: 3:00 AM daily (after backup)
Report:       Monday 8:00 AM weekly (email if configured)
```

## Features

### Backup Features
- **Compression**: Rsync with zlib compression for network transfers
- **Deduplication**: Rsync only transfers changed files
- **Verification**: Post-backup integrity checks
- **Metadata**: JSON metadata with sizes, checksums, file lists
- **Safety**: Creates safety backup before restore
- **Parallel**: Simultaneous backups to multiple targets
- **Atomic**: All-or-nothing restore operations

### Monitoring
- **Real-time logs**: `~/logs/learning-backup.log`
- **Error tracking**: `~/logs/learning-backup-error.log`
- **Email alerts**: On failure (configurable)
- **Verification reports**: Daily integrity checks
- **Systemd journal**: Integration for centralized logging

### Retention Policy
- **Daily**: 7 days (1 week)
- **Weekly**: 4 weeks (1 month)
- **Monthly**: 12 months (1 year)
- **Auto-cleanup**: Old backups automatically removed

## Configuration

### Environment Variables

```bash
# Email notifications
export BACKUP_NOTIFY_EMAIL="your@email.com"

# Send email on success (default: false, only errors)
export BACKUP_EMAIL_SUCCESS=true

# Skip confirmation prompts in restore
export BACKUP_NO_CONFIRM=1
```

### Customization

Edit scripts in `~/bin/`:
- `backup-learning-data.sh` - Main backup logic
- `restore-learning-data.sh` - Restore logic
- `verify-learning-backups.sh` - Verification checks

## Scripts

### backup-learning-data.sh

Main backup orchestrator.

**Usage:**
```bash
~/bin/backup-learning-data.sh
```

**What it does:**
1. Checks NAS mount and fleet connectivity
2. Creates timestamped backup directories
3. Rsyncs data to all targets (parallel)
4. Creates metadata and file manifests
5. Verifies backup integrity
6. Cleans up old backups per retention policy
7. Sends notifications

**Exit codes:**
- `0` = Success
- `1` = Partial or complete failure

### restore-learning-data.sh

Restore learning data from any backup location.

**Usage:**
```bash
# Interactive restore (prompts for confirmation)
~/bin/restore-learning-data.sh [SOURCE] [DATE]

# Non-interactive restore
BACKUP_NO_CONFIRM=1 ~/bin/restore-learning-data.sh nas latest
```

**Parameters:**
- `SOURCE`: `nas`, `server-01`, `server-02`, `server-03`, `aio-01`
- `DATE`: `YYYY-MM-DD` or `latest` (default)

**What it does:**
1. Finds requested backup
2. Shows backup metadata
3. Prompts for confirmation (unless `BACKUP_NO_CONFIRM=1`)
4. Creates safety backup of current data
5. Restores system and project learning data
6. Verifies restored files
7. Reports success/failure and rollback instructions

**Examples:**
```bash
# Restore latest from NAS
~/bin/restore-learning-data.sh

# Restore specific date
~/bin/restore-learning-data.sh nas 2026-06-13

# Restore from fleet server
~/bin/restore-learning-data.sh server-02 latest

# List all backups
~/bin/restore-learning-data.sh --list
```

### verify-learning-backups.sh

Comprehensive backup verification and health check.

**Usage:**
```bash
~/bin/verify-learning-backups.sh
```

**Checks performed:**
- ✓ NAS mount status
- ✓ Fleet server SSH connectivity
- ✓ Backup existence on all targets
- ✓ Backup age (alerts if > 26 hours)
- ✓ Critical file presence
- ✓ Backup size (alerts if < 1MB)
- ✓ File count consistency
- ✓ Retention policy compliance
- ✓ Disk space usage (warns at 80%)

**Output:**
- Color-coded status (green=pass, yellow=warning, red=fail)
- Summary statistics
- Actionable alerts

**Exit codes:**
- `0` = All checks passed
- `1` = Some issues detected
- `2` = Critical failures

## Monitoring & Alerts

### Log Files

```bash
# View backup logs
tail -f ~/logs/learning-backup.log

# View error logs
tail -f ~/logs/learning-backup-error.log

# View verification logs
tail -f ~/logs/learning-backup-verify.log

# Search for failures
grep ERROR ~/logs/learning-backup*.log
```

### Manual Verification

```bash
# Run verification check
~/bin/verify-learning-backups.sh

# Check specific backup
ls -lh /mnt/nas/backups/claude-learning/daily/
ls -lh /mnt/nas/backups/claude-learning/daily/2026-06-14/

# View backup metadata
cat /mnt/nas/backups/claude-learning/daily/2026-06-14/metadata/backup-info.json | jq .

# Compare backup to source
diff -r ~/.claude/learning/ /mnt/nas/backups/claude-learning/daily/latest/system/
```

### Email Notifications

Set up email notifications:

```bash
# In ~/.bashrc or ~/.profile
export BACKUP_NOTIFY_EMAIL="your@email.com"
export BACKUP_EMAIL_SUCCESS=false  # Only email on errors

# Test email
echo "Test" | mail -s "Backup Test" $BACKUP_NOTIFY_EMAIL
```

## Disaster Recovery

### Scenario 1: Complete Data Loss

```bash
# Restore from NAS (fastest)
~/bin/restore-learning-data.sh nas latest

# Verify restoration
~/bin/verify-learning-backups.sh
```

### Scenario 2: NAS Failure

```bash
# Restore from fleet server
~/bin/restore-learning-data.sh server-01 latest

# Or from AIO (weekly backups only)
~/bin/restore-learning-data.sh aio-01 latest
```

### Scenario 3: Corrupted Data

```bash
# List available backups
~/bin/restore-learning-data.sh --list

# Restore specific known-good date
~/bin/restore-learning-data.sh nas 2026-06-10
```

### Scenario 4: Partial Data Loss

```bash
# Manual selective restore
rsync -avh /mnt/nas/backups/claude-learning/daily/latest/system/bandit-state.json \
  ~/.claude/learning/bandit-state.json

# Restore just databases
rsync -avh /mnt/nas/backups/claude-learning/daily/latest/system/db/ \
  ~/.claude/learning/db/
```

## Rollback After Restore

Every restore creates a safety backup. To rollback:

```bash
# Restore script outputs rollback commands, e.g.:
cp -a ~/.claude/learning-backup-20260614-083045/system/* ~/.claude/learning/
cp -a ~/.claude/learning-backup-20260614-083045/project/* ~/Development/.../learning/
```

## Performance

### Backup Times (Typical)

| Target | Transfer Time | Verification | Total |
|--------|--------------|--------------|-------|
| NAS (local) | 5-10s | 2s | ~12s |
| Fleet server | 15-30s | 3s | ~35s |
| AIO server | 20-40s | 3s | ~45s |

**Note:** First backup is slower (full transfer). Subsequent backups use rsync delta transfers (only changed files).

### Disk Space Usage

```
Per backup snapshot: ~21MB (current data size)
NAS total (7+4+12 = 23 snapshots): ~483MB
Fleet per server (23 snapshots): ~483MB
Total across all targets: ~2.4GB
```

## Testing

### Test Backup

```bash
# Dry run backup (rsync --dry-run mode)
# Edit script temporarily to add --dry-run to rsync commands

# Full test backup
~/bin/backup-learning-data.sh

# Verify backup worked
~/bin/verify-learning-backups.sh
```

### Test Restore

```bash
# Create test backup first
~/bin/backup-learning-data.sh

# Test restore to temporary location
# (Modify restore script or manually rsync to /tmp/test-restore)

# Test actual restore (creates safety backup)
~/bin/restore-learning-data.sh nas latest

# Rollback test restore
# Use the safety backup path output by restore script
```

## Troubleshooting

### NAS Not Mounted

```bash
# Check mount
mountpoint /mnt/nas

# Remount
sudo mount -a

# Check /etc/fstab entry
grep nas /etc/fstab
```

### SSH Connection Failed

```bash
# Test SSH
ssh server-01 "echo OK"

# Check SSH keys
ssh-add -l

# Add key if needed
ssh-copy-id server-01
```

### Backup Too Old

```bash
# Check cron is running
systemctl status cron

# Check crontab
crontab -l | grep backup-learning

# Check logs
tail -100 ~/logs/learning-backup.log
```

### Verification Failed

```bash
# Run detailed verification
~/bin/verify-learning-backups.sh

# Check specific backup
ls -la /mnt/nas/backups/claude-learning/daily/latest/

# Force new backup
~/bin/backup-learning-data.sh
```

### Disk Space Issues

```bash
# Check disk space on all targets
df -h /mnt/nas
ssh server-01 "df -h /exports/backups"

# Manual cleanup (adjust retention if needed)
# Old backups are automatically cleaned up per retention policy
```

## Integration

### Monitoring Dashboards

Integrate with Grafana (see `GRAFANA_SETUP.md`):

```bash
# Export metrics
~/bin/verify-learning-backups.sh > /tmp/backup-metrics.txt

# Parse and send to Prometheus/Grafana
# (Custom exporter needed)
```

### CI/CD Integration

```yaml
# Pre-deployment backup
- name: Backup Learning Data
  run: ~/bin/backup-learning-data.sh

# Post-deployment verification
- name: Verify Backups
  run: ~/bin/verify-learning-backups.sh
```

## Security

### Backup Security
- Backups stored on trusted NFS mounts
- SSH key-based authentication (no passwords)
- File permissions preserved (rsync -a)
- No encryption (local trusted network)

### Access Control
- Backups readable by user only (default)
- SSH access limited to fleet servers
- Cron runs as user (not root)

## Maintenance

### Weekly Tasks
- Review verification reports (automated Monday emails)
- Check log files for errors
- Verify disk space on backup targets

### Monthly Tasks
- Test restore procedure
- Review retention policy
- Update documentation

### Quarterly Tasks
- Test disaster recovery scenario
- Review and update backup targets
- Performance optimization

## Future Enhancements

Planned improvements:
- [ ] Incremental backups with hardlinks (space savings)
- [ ] Encryption for off-site backups
- [ ] S3/cloud backup tier
- [ ] Real-time replication (not just daily)
- [ ] Automated restore testing
- [ ] Prometheus metrics exporter
- [ ] Web dashboard for backup status
- [ ] Slack/Discord notifications

## Related Documentation

- `GRAFANA_SETUP.md` - Monitoring integration
- `FLEET_ORCHESTRATOR.md` - Fleet architecture
- `NAS_SYSTEM_SUMMARY.md` - NAS configuration
- `LEARNING_METRICS_DESIGN.md` - Learning system metrics

## Support

For issues or questions:
1. Check logs: `~/logs/learning-backup*.log`
2. Run verification: `~/bin/verify-learning-backups.sh`
3. Review this documentation
4. Check git history for changes

---

**Last Updated:** 2026-06-14
**Version:** 1.0.0
**Author:** Claude + Scot Floess
