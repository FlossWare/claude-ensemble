# PostgreSQL Backup and Recovery

**Last Verified:** 2026-07-08
**Database:** `learning` on aio-01:5433
**Backup Location:** `/mnt/nas/backups/postgres-learning/` (NFS mount to nas:/mnt/md0/exports)

## Backup Information

**Current Backup:**
- File: `backup-20260708-193335.sql.gz`
- Size: 153 MB (160,694,272 bytes)
- Format: gzip-compressed SQL dump
- Database Size: 1.08 GB (1,080 MB uncompressed)
- Compression Ratio: 7.1:1
- Tables: 131 tables across 5 schemas (public, costs, learning, monitoring, workflow)

**Key Statistics (as of backup):**
- Total rows: ~240,000+
- Largest tables:
  - `learning.conversation_learnings`: 22,471 rows
  - `learning.session_chunks`: 46,744 rows
  - `workflow.confidence_calibration`: 39,386 rows
  - `public.api_failures`: 101,038 rows
  - `monitoring.execution_summary`: 2,026 rows

## Backup Procedure

### Manual Backup

```bash
# Create backup (run on aio-01)
sudo -u postgres pg_dump -p 5433 learning | \
  sudo tee /mnt/nas/backups/postgres-learning/backup-$(date +%Y%m%d-%H%M%S).sql | \
  gzip > /dev/null

# OR: Single-step compressed backup
sudo -u postgres pg_dump -p 5433 learning | \
  gzip | sudo tee /mnt/nas/backups/postgres-learning/backup-$(date +%Y%m%d-%H%M%S).sql.gz > /dev/null
```

### Automated Backup (Recommended)

Create cron job on aio-01:

```bash
# Edit crontab for postgres user
sudo crontab -e -u postgres

# Add daily backup at 2 AM
0 2 * * * pg_dump -p 5433 learning | gzip > /mnt/nas/backups/postgres-learning/backup-$(date +\%Y\%m\%d-\%H\%M\%S).sql.gz 2>&1 | logger -t postgres-backup
```

**Retention Policy:**
- Keep daily backups for 30 days
- Keep weekly backups for 90 days
- Keep monthly backups for 1 year

Cleanup script:

```bash
# Remove backups older than 30 days
find /mnt/nas/backups/postgres-learning/ -name "backup-*.sql.gz" -mtime +30 -delete
```

## Recovery Procedure

### Full Database Restore

**WARNING:** This will DESTROY the existing database and replace it with the backup.

```bash
# Step 1: Terminate all connections to the database
sudo -u postgres psql -p 5433 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'learning' AND pid <> pg_backend_pid();"

# Step 2: Drop the existing database
sudo -u postgres dropdb -p 5433 learning

# Step 3: Create a fresh database
sudo -u postgres createdb -p 5433 learning

# Step 4: Restore from backup
sudo zcat /mnt/nas/backups/postgres-learning/backup-YYYYMMDD-HHMMSS.sql.gz | \
  sudo -u postgres psql -p 5433 learning

# Step 5: Verify restore
sudo -u postgres psql -p 5433 -d learning -c "\dt"
sudo -u postgres psql -p 5433 -d learning -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema IN ('public', 'costs', 'learning', 'monitoring', 'workflow');"
```

### Test Restore (Non-Destructive)

Recommended to test restore procedure regularly:

```bash
# Create test database
sudo -u postgres createdb -p 5433 learning_test

# Restore backup to test database
sudo zcat /mnt/nas/backups/postgres-learning/backup-YYYYMMDD-HHMMSS.sql.gz | \
  sudo -u postgres psql -p 5433 learning_test

# Verify table count
sudo -u postgres psql -p 5433 -d learning_test -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema IN ('public', 'costs', 'learning', 'monitoring', 'workflow');"

# Expected result: 131 tables

# Verify key data
sudo -u postgres psql -p 5433 -d learning_test -c "SELECT schemaname, relname, n_live_tup FROM pg_stat_user_tables WHERE n_live_tup > 1000 ORDER BY n_live_tup DESC LIMIT 10;"

# Clean up test database
sudo -u postgres dropdb -p 5433 learning_test
```

### Partial Recovery (Table-Level)

To restore a single table without affecting the entire database:

```bash
# Extract specific table from backup
sudo zcat /mnt/nas/backups/postgres-learning/backup-YYYYMMDD-HHMMSS.sql.gz | \
  grep -A 10000 "CREATE TABLE learning.experiences" > /tmp/experiences.sql

# Restore to temporary database
sudo -u postgres createdb -p 5433 temp_recovery
sudo -u postgres psql -p 5433 temp_recovery < /tmp/experiences.sql

# Copy data to production (if needed)
sudo -u postgres pg_dump -p 5433 -t learning.experiences temp_recovery | \
  sudo -u postgres psql -p 5433 learning

# Clean up
sudo -u postgres dropdb -p 5433 temp_recovery
rm /tmp/experiences.sql
```

## Point-in-Time Recovery (PITR)

**Current Status:** NOT CONFIGURED

To enable PITR (continuous archiving):

```bash
# 1. Edit postgresql.conf on aio-01
sudo vim /var/lib/pgsql/15/data/postgresql.conf

# Add/modify:
wal_level = replica
archive_mode = on
archive_command = 'cp %p /mnt/nas/backups/postgres-learning/wal_archive/%f'
max_wal_senders = 3
wal_keep_size = 1GB

# 2. Create WAL archive directory
sudo mkdir -p /mnt/nas/backups/postgres-learning/wal_archive
sudo chown postgres:postgres /mnt/nas/backups/postgres-learning/wal_archive

# 3. Restart PostgreSQL
sudo systemctl restart postgresql-15

# 4. Create base backup
sudo -u postgres pg_basebackup -p 5433 -D /mnt/nas/backups/postgres-learning/base_backup -Fp -Xs -P
```

## Backup Verification Checklist

Run monthly to ensure backups are valid:

- [ ] Create test database: `sudo -u postgres createdb -p 5433 learning_test`
- [ ] Restore latest backup: `sudo zcat backup-latest.sql.gz | sudo -u postgres psql -p 5433 learning_test`
- [ ] Verify table count: Should be 131 tables
- [ ] Verify row counts: Compare key tables (conversation_learnings, session_chunks, api_failures)
- [ ] Test random queries: `SELECT * FROM learning.experiences LIMIT 10;`
- [ ] Check schema integrity: `\d learning.experiences`
- [ ] Verify extensions: `\dx` (should include pgvector)
- [ ] Clean up: `sudo -u postgres dropdb -p 5433 learning_test`
- [ ] Document results in this file

**Last Verification:** 2026-07-08 - PASSED
- Tables: 131 ✓
- Row counts: Match production ✓
- Extensions: pgvector present ✓
- Schema integrity: All constraints present ✓

## Disaster Recovery Scenarios

### Scenario 1: Accidental Table Drop

```bash
# If you accidentally dropped a table:
# 1. Immediately create a new backup of current state (if any data is salvageable)
sudo -u postgres pg_dump -p 5433 learning | gzip > /tmp/emergency-backup.sql.gz

# 2. Restore just the dropped table from latest backup
sudo zcat /mnt/nas/backups/postgres-learning/backup-YYYYMMDD-HHMMSS.sql.gz | \
  grep -A 10000 "CREATE TABLE schema.table_name" > /tmp/restore_table.sql

# 3. Apply to production
sudo -u postgres psql -p 5433 learning < /tmp/restore_table.sql
```

### Scenario 2: Data Corruption

```bash
# If data corruption detected:
# 1. Identify affected tables
sudo -u postgres psql -p 5433 -d learning -c "SELECT * FROM pg_stat_database WHERE datname = 'learning';"

# 2. Full restore from most recent clean backup
# (Follow "Full Database Restore" procedure above)
```

### Scenario 3: Server Failure

```bash
# If aio-01 fails and database is lost:
# 1. Install PostgreSQL 15 on replacement server
sudo dnf install -y postgresql15-server postgresql15-contrib

# 2. Initialize database
sudo postgresql-setup --initdb

# 3. Configure PostgreSQL (port 5433, pgvector extension)
sudo vim /var/lib/pgsql/15/data/postgresql.conf
# port = 5433

sudo systemctl enable postgresql-15 --now

# 4. Install pgvector extension
sudo dnf install -y postgresql15-devel
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# 5. Create database and restore
sudo -u postgres createdb -p 5433 learning
sudo -u postgres psql -p 5433 -d learning -c "CREATE EXTENSION vector;"
sudo zcat /mnt/nas/backups/postgres-learning/backup-YYYYMMDD-HHMMSS.sql.gz | \
  sudo -u postgres psql -p 5433 learning
```

## NAS Availability

**NAS Details:**
- Host: nas (192.168.1.100)
- Export: /mnt/md0/exports
- Mount: /mnt/nas on aio-01
- Protocol: NFS
- Available Space: 528 GB (as of 2026-07-08)
- Total Size: 3.6 TB

**If NAS is unavailable:**

```bash
# Backup to local disk temporarily
sudo -u postgres pg_dump -p 5433 learning | \
  gzip > /var/lib/pgsql/backups/backup-$(date +%Y%m%d-%H%M%S).sql.gz

# Copy to NAS when available
sudo cp /var/lib/pgsql/backups/*.sql.gz /mnt/nas/backups/postgres-learning/
```

## Monitoring

**Check backup age:**

```bash
# Alert if backup is older than 24 hours
find /mnt/nas/backups/postgres-learning/ -name "backup-*.sql.gz" -mtime -1 | wc -l
# Should return 1 or more
```

**Add to monitoring system:**

```bash
# Add to cron for daily backup verification
0 8 * * * [ $(find /mnt/nas/backups/postgres-learning/ -name "backup-*.sql.gz" -mtime -1 | wc -l) -gt 0 ] || echo "ALERT: PostgreSQL backup is stale" | mail -s "Backup Alert" admin@example.com
```

## Contact Information

**Database Administrator:** claude user on aio-01
**Backup Location Owner:** root on aio-01
**NAS Administrator:** root on nas (192.168.1.100)

## Appendix: Backup Size Trends

| Date | Database Size | Backup Size | Compression Ratio | Tables | Notes |
|------|---------------|-------------|-------------------|--------|-------|
| 2026-07-08 | 1.08 GB | 153 MB | 7.1:1 | 131 | Initial verification |

Update this table monthly to track growth trends.
