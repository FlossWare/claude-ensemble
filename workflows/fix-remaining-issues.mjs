export const meta = {
  name: 'fix-remaining-issues',
  description: 'Fix 6 remaining system issues in parallel',
  phases: [
    { title: 'Critical', detail: 'Backups + log rotation + NFS security' },
    { title: 'Medium', detail: 'OrientDB + Flask API + consciousness archive' },
    { title: 'Verify', detail: 'Confirm all fixes applied' }
  ]
}

/**
 * Parallel System Fixes Workflow
 *
 * Tackles 6 remaining issues from system review using orchestrator:
 * 1. Verify PostgreSQL backups (CRITICAL)
 * 2. Add log rotation (HIGH)
 * 3. Tighten NFS security (HIGH)
 * 4. OrientDB reality check (MEDIUM)
 * 5. Flask API reality check (MEDIUM)
 * 6. Archive consciousness systems (MEDIUM)
 *
 * Estimated time: 20-30 minutes with 6 parallel agents
 */
export default async function({ phase, parallel, agent, log }) {

  phase('Critical')
  log('Launching 3 critical fixes in parallel')

  const criticalFixes = await parallel([
    // Fix 1: Verify PostgreSQL backups
    async () => await agent(
      `CRITICAL: Verify PostgreSQL backups work

      On aio-01:
      1. Create backup: sudo -u postgres pg_dump -p 5433 learning | gzip > /mnt/nas/backup-test-$(date +%Y%m%d-%H%M).sql.gz
      2. Check size: ls -lh /mnt/nas/backup-test-*.sql.gz
      3. Create test database: sudo -u postgres createdb -p 5433 learning_test
      4. Restore: gunzip -c /mnt/nas/backup-test-*.sql.gz | sudo -u postgres psql -p 5433 learning_test
      5. Verify: sudo -u postgres psql -p 5433 learning_test -c "SELECT COUNT(*) FROM learning.strategy_performance"
      6. Cleanup: sudo -u postgres dropdb -p 5433 learning_test
      7. Document in docs/RECOVERY.md

      Return: { task: "backups", status: "success|error", backup_size_gb: <number>, verified: true|false }`,
      {
        label: 'fix-backups',
        phase: 'Critical',
        schema: {
          type: 'object',
          properties: {
            task: { type: 'string' },
            status: { type: 'string' },
            backup_size_gb: { type: 'number' },
            verified: { type: 'boolean' }
          }
        }
      }
    ),

    // Fix 2: Add log rotation
    async () => await agent(
      `Add log rotation on aio-01

      Create /etc/logrotate.d/learning-api:
      /var/log/learning-api.log {
          daily
          rotate 7
          compress
          delaycompress
          missingok
          notifempty
          create 0640 root root
      }

      Also add for:
      - /home/claude/api-access.log
      - /home/claude/api-error.log

      Test: logrotate -f /etc/logrotate.d/learning-api

      Return: { task: "log_rotation", status: "success", files_configured: <count> }`,
      {
        label: 'fix-logrotate',
        phase: 'Critical',
        schema: {
          type: 'object',
          properties: {
            task: { type: 'string' },
            status: { type: 'string' },
            files_configured: { type: 'number' }
          }
        }
      }
    ),

    // Fix 3: Tighten NFS security
    async () => await agent(
      `Tighten NFS security on aio-01

      Current (INSECURE): /exports <world>(sync,...,no_root_squash)
      New (SECURE): /exports 192.168.1.0/24(sync,...,root_squash)

      Steps:
      1. Backup: cp /etc/exports /etc/exports.backup
      2. Update /etc/exports:
         /exports 192.168.1.0/24(sync,wdelay,hide,no_subtree_check,sec=sys,rw,secure,root_squash,no_all_squash)
      3. Reload: exportfs -ra
      4. Test from worker: ssh server-01 'touch /mnt/aio-01/claude-orchestrator/test-file' (should work)
      5. Test root blocked: ssh root@server-01 'touch /mnt/aio-01/claude-orchestrator/test-root' (should fail)

      Return: { task: "nfs_security", status: "success", root_squash_enabled: true }`,
      {
        label: 'fix-nfs',
        phase: 'Critical',
        schema: {
          type: 'object',
          properties: {
            task: { type: 'string' },
            status: { type: 'string' },
            root_squash_enabled: { type: 'boolean' }
          }
        }
      }
    )
  ])

  phase('Medium')
  log('Launching 3 medium-priority tasks in parallel')

  const mediumFixes = await parallel([
    // Fix 4: OrientDB reality check
    async () => await agent(
      `Reality check: Is OrientDB being used?

      Query OrientDB on aio-01:
      1. Node count: curl -u root:root http://aio-01:2480/query/orchestrator/sql -d "SELECT COUNT(*) FROM V"
      2. Edge count: curl -u root:root http://aio-01:2480/query/orchestrator/sql -d "SELECT COUNT(*) FROM E"
      3. Last modified: docker logs <orientdb-container> | tail -20
      4. Memory usage: docker stats <orientdb-container> --no-stream

      Decision:
      - If nodes/edges = 0 or very low AND last activity >30 days: RECOMMEND DELETE (saves 2GB RAM)
      - Otherwise: RECOMMEND KEEP

      Return: { task: "orientdb_check", nodes: <count>, edges: <count>, recommendation: "keep|delete", memory_mb: <number> }`,
      {
        label: 'check-orientdb',
        phase: 'Medium',
        schema: {
          type: 'object',
          properties: {
            task: { type: 'string' },
            nodes: { type: 'number' },
            edges: { type: 'number' },
            recommendation: { type: 'string' },
            memory_mb: { type: 'number' }
          }
        }
      }
    ),

    // Fix 5: Flask API reality check
    async () => await agent(
      `Reality check: Is Flask API (port 5000) being used?

      On aio-01:
      1. Check last access: tail -100 /home/claude/api-access.log | grep -E "GET|POST" | tail -20
      2. Check endpoints: curl http://aio-01:5000/ | head -50
      3. Check process: ps aux | grep gunicorn | grep 5000
      4. Check age: stat -c %Y /home/claude/api-access.log

      Decision:
      - If no access in >30 days: RECOMMEND DELETE
      - If active but endpoints duplicated in FastAPI (8006): RECOMMEND MIGRATE
      - Otherwise: RECOMMEND KEEP

      Return: { task: "flask_check", last_access_days_ago: <number>, endpoints: <count>, recommendation: "keep|migrate|delete" }`,
      {
        label: 'check-flask',
        phase: 'Medium',
        schema: {
          type: 'object',
          properties: {
            task: { type: 'string' },
            last_access_days_ago: { type: 'number' },
            endpoints: { type: 'number' },
            recommendation: { type: 'string' }
          }
        }
      }
    ),

    // Fix 6: Archive consciousness systems
    async () => await agent(
      `Archive consciousness systems experiments

      On laptop-01 (where code resides):
      1. Create directory: mkdir -p ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/experiments/consciousness-2026-06
      2. Count files: ls ~/.claude/self/*.py | wc -l
      3. Move files: mv ~/.claude/self/*.py ~/Development/.../experiments/consciousness-2026-06/
      4. Create README:
         ---
         # Consciousness Systems Experiments (June 2026)

         Learning experiments exploring consciousness theories:
         - IIT Φ calculation
         - Active Inference
         - HOT Meta-Representation
         - Global Workspace Theory
         - Free Energy Principle

         **Status:** ARCHIVED - Learning experiments, not operational components
         **Date:** June 2026
         **Outcome:** Learned about consciousness theories, not used in production
         ---
      5. Verify main tree clean: ls ~/.claude/self/*.py (should be empty or minimal)

      Return: { task: "archive_consciousness", files_moved: <count>, status: "success" }`,
      {
        label: 'archive-consciousness',
        phase: 'Medium',
        schema: {
          type: 'object',
          properties: {
            task: { type: 'string' },
            files_moved: { type: 'number' },
            status: { type: 'string' }
          }
        }
      }
    )
  ])

  phase('Verify')
  log('Verifying all fixes applied')

  const allFixes = [...criticalFixes, ...mediumFixes].filter(Boolean)
  const successful = allFixes.filter(f => f.status === 'success')
  const failed = allFixes.filter(f => f.status === 'error')

  log(`Completed: ${successful.length}/6 fixes`)
  if (failed.length > 0) {
    log(`⚠️ Failed: ${failed.map(f => f.task).join(', ')}`)
  }

  // Summary
  const summary = {
    backups: criticalFixes[0],
    log_rotation: criticalFixes[1],
    nfs_security: criticalFixes[2],
    orientdb: mediumFixes[0],
    flask_api: mediumFixes[1],
    consciousness_archive: mediumFixes[2]
  }

  log('\n=== SUMMARY ===')
  log(`✅ Backups verified: ${summary.backups?.verified ? 'YES' : 'NO'}`)
  log(`✅ Log rotation configured: ${summary.log_rotation?.files_configured || 0} files`)
  log(`✅ NFS secured: ${summary.nfs_security?.root_squash_enabled ? 'YES' : 'NO'}`)
  log(`📊 OrientDB: ${summary.orientdb?.nodes || 0} nodes, ${summary.orientdb?.edges || 0} edges → ${summary.orientdb?.recommendation}`)
  log(`📊 Flask API: ${summary.flask_api?.recommendation}`)
  log(`📦 Consciousness files archived: ${summary.consciousness_archive?.files_moved || 0}`)

  return {
    completed: successful.length,
    failed: failed.length,
    summary
  }
}
