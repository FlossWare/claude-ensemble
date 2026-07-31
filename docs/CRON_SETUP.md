# Cron Setup for Red Hat Compliance Alerts

**IMPORTANT: This cron job MUST run on `aio-01` (the controller/orchestrator), NOT on local machines!**

---

## Setup on aio-01

### 1. SSH to aio-01

```bash
ssh aio-01
```

### 2. Add cron entry

```bash
crontab -e
```

Add this line:

```cron
# Red Hat compliance alerts - check every 6 hours
0 */6 * * * /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/bin/alert-redhat-violations.sh >> /var/log/redhat-compliance.log 2>&1
```

**Schedule:** Runs at 00:00, 06:00, 12:00, 18:00 daily

### 3. Verify cron entry

```bash
crontab -l | grep alert-redhat-violations
```

Should show:
```
0 */6 * * * /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/bin/alert-redhat-violations.sh >> /var/log/redhat-compliance.log 2>&1
```

### 4. Test manually

```bash
/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/bin/alert-redhat-violations.sh
```

Expected output:
```
Running Red Hat compliance check...
✓ No violations detected
```

---

## Configuration

### Email Alerts

Set the email recipient (defaults to sfloess@redhat.com):

```bash
export REDHAT_COMPLIANCE_ALERT_EMAIL="your-email@redhat.com"
```

Add to `.bashrc` or `.profile` on aio-01 to persist.

### Email Requirements

- ✅ Postfix configured on aio-01 (already done)
- ✅ Script uses `mail` command
- ✅ Alerts send to configured email on violations

---

## What the Cron Job Does

Every 6 hours:

1. **Checks PostgreSQL** `monitoring.model_usage` table
2. **Scans last 6 hours** for Red Hat tasks (`redhat_*` task types)
3. **Detects violations** where non-Anthropic models were used
4. **Sends email alert** if violations found
5. **Logs to syslog** for audit trail
6. **Saves report** to `/home/claude/reports/redhat-compliance-YYYYMMDD-HHMMSS.txt`

---

## Manual Checks

Check last 24 hours:
```bash
node /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/tools/check-redhat-compliance.cjs 24
```

Check last 7 days:
```bash
node /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/tools/check-redhat-compliance.cjs 168
```

---

## Monitoring

### Check cron logs

```bash
# On aio-01
tail -f /var/log/redhat-compliance.log
```

### Check syslog for violations

```bash
grep redhat-compliance /var/log/messages
```

### View saved reports

```bash
ls -lht /home/claude/reports/redhat-compliance-*.txt | head -5
```

---

## Troubleshooting

### Cron not running

1. Check crontab: `crontab -l | grep alert-redhat`
2. Check cron service: `systemctl status crond`
3. Check logs: `/var/log/cron`

### Email not sending

1. Test postfix: `echo "test" | mail -s "Test" your-email@redhat.com`
2. Check mail logs: `/var/log/maillog`
3. Verify email env var is set

### No violations detected but should be

1. Check REST API connection: `curl -s http://aio-01:5000/health`
2. Check model usage data:
   ```bash
   curl -s http://aio-01:5000/db/query \
     -H 'Content-Type: application/json' \
     -d '{"sql": "SELECT COUNT(*) FROM monitoring.model_usage"}'
   ```
3. Check task types:
   ```bash
   curl -s http://aio-01:5000/db/query \
     -H 'Content-Type: application/json' \
     -d '{"sql": "SELECT DISTINCT task_type FROM monitoring.model_usage WHERE task_type LIKE '\''redhat_%'\''"}'
   ```

---

## Security

- ✅ PostgreSQL credentials in environment (not hardcoded)
- ✅ SQL queries parameterized (injection-safe)
- ✅ Reports saved to `/home/claude/reports/` (persistent storage)
- ✅ Syslog audit trail (immutable)

---

## Next Steps

After setting up on aio-01:

1. ✅ Add cron entry
2. ✅ Test manual run
3. ✅ Wait for first scheduled run (next :00 hour)
4. ✅ Verify email received (if violations exist)
5. ✅ Check logs to confirm execution

**Status: Ready for deployment on aio-01**
