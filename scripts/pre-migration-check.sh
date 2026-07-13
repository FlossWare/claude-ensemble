#!/bin/bash
#
# Pre-Migration Readiness Check
#
# Verifies system is ready for PostgreSQL to Redis migration.
# Run this before executing migrate-pg-to-redis.py

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PG_HOST="aio-01"
PG_PORT="5433"
PG_USER="sfloess"
PG_DB="learning"
REDIS_HOST="aio-01"

CHECKS_PASSED=0
CHECKS_FAILED=0
WARNINGS=0

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((CHECKS_PASSED++))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((CHECKS_FAILED++))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

echo "================================================"
echo "Pre-Migration Readiness Check"
echo "================================================"
echo ""

# 1. PostgreSQL Connection
echo "1. Checking PostgreSQL connection..."
if psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -c "SELECT 1" > /dev/null 2>&1; then
    check_pass "PostgreSQL connection OK"
else
    check_fail "PostgreSQL connection failed"
fi

# 2. Redis Connection
echo ""
echo "2. Checking Redis connection..."
if ssh claude@$REDIS_HOST "redis-cli -h localhost ping" > /dev/null 2>&1; then
    check_pass "Redis connection OK"
else
    check_fail "Redis connection failed"
fi

# 3. PostgreSQL Queue State
echo ""
echo "3. Checking PostgreSQL queue state..."
pending=$(psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -t -c "SELECT COUNT(*) FROM queue.store WHERE status = 'pending';" 2>/dev/null | tr -d ' ')
processing=$(psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -t -c "SELECT COUNT(*) FROM queue.store WHERE status = 'processing';" 2>/dev/null | tr -d ' ')
completed=$(psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -t -c "SELECT COUNT(*) FROM queue.store WHERE status = 'completed';" 2>/dev/null | tr -d ' ')

echo "   Pending: $pending"
echo "   Processing: $processing"
echo "   Completed: $completed"

if [ "$pending" -gt 0 ]; then
    check_pass "Found $pending items to migrate"
else
    check_warn "No pending items found (nothing to migrate)"
fi

if [ "$processing" -gt 0 ]; then
    check_warn "$processing items currently processing (should drain first)"
fi

# 4. Redis Queue State
echo ""
echo "4. Checking Redis queue state..."
high=$(ssh claude@$REDIS_HOST "redis-cli -h localhost LLEN redis:queue:store:high" 2>/dev/null || echo "0")
medium=$(ssh claude@$REDIS_HOST "redis-cli -h localhost LLEN redis:queue:store:medium" 2>/dev/null || echo "0")
low=$(ssh claude@$REDIS_HOST "redis-cli -h localhost LLEN redis:queue:store:low" 2>/dev/null || echo "0")
total_redis=$((high + medium + low))

echo "   High priority: $high"
echo "   Medium priority: $medium"
echo "   Low priority: $low"

if [ "$total_redis" -eq 0 ]; then
    check_pass "Redis queues are empty"
else
    check_warn "Redis queues not empty ($total_redis items)"
fi

# 5. Redis Memory
echo ""
echo "5. Checking Redis memory..."
used_mb=$(ssh claude@$REDIS_HOST "redis-cli -h localhost info memory | grep used_memory_human | cut -d: -f2 | tr -d '\r'" 2>/dev/null)
echo "   Used memory: $used_mb"

# Estimate needed memory (pending items × 2KB avg)
estimated_mb=$((pending * 2048 / 1024 / 1024))
echo "   Estimated needed: ${estimated_mb}M"

if [ "$estimated_mb" -lt 100 ]; then
    check_pass "Sufficient Redis memory available"
else
    check_warn "Large memory requirement (${estimated_mb}M)"
fi

# 6. Processing Items in Other Queues
echo ""
echo "6. Checking processing items in pipeline..."
chunk_proc=$(psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -t -c "SELECT COUNT(*) FROM queue.chunk WHERE status = 'processing';" 2>/dev/null | tr -d ' ')
embed_proc=$(psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -t -c "SELECT COUNT(*) FROM queue.embed WHERE status = 'processing';" 2>/dev/null | tr -d ' ')
graph_proc=$(psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -t -c "SELECT COUNT(*) FROM queue.graph WHERE status = 'processing';" 2>/dev/null | tr -d ' ')
total_proc=$((chunk_proc + embed_proc + graph_proc))

echo "   Chunk: $chunk_proc"
echo "   Embed: $embed_proc"
echo "   Graph: $graph_proc"
echo "   Total: $total_proc"

if [ "$total_proc" -eq 0 ]; then
    check_pass "No items processing in pipeline"
else
    check_warn "$total_proc items still processing (should drain or mark as dead_letter)"
fi

# 7. Auto-Scraper Status
echo ""
echo "7. Checking auto-scraper status..."
if curl -s http://aio-01:5000/fleet/auto-deploy/status > /dev/null 2>&1; then
    status=$(curl -s http://aio-01:5000/fleet/auto-deploy/status | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    if [ "$status" == "stopped" ]; then
        check_pass "Auto-scraper stopped"
    else
        check_warn "Auto-scraper is running (should stop before migration)"
    fi
else
    check_warn "Cannot check auto-scraper status (API unreachable)"
fi

# 8. Backup Files
echo ""
echo "8. Checking for recent backups..."
recent_backup=$(ssh claude@$REDIS_HOST "ls -t /tmp/store_queue_backup_*.csv 2>/dev/null | head -1" || echo "")
if [ -n "$recent_backup" ]; then
    backup_age=$(ssh claude@$REDIS_HOST "stat -c %Y '$recent_backup' 2>/dev/null" || echo "0")
    now=$(date +%s)
    age_hours=$(( (now - backup_age) / 3600 ))

    if [ "$age_hours" -lt 24 ]; then
        check_pass "Recent backup found ($recent_backup, ${age_hours}h old)"
    else
        check_warn "Backup is old (${age_hours}h), consider creating new backup"
    fi
else
    check_warn "No backup found, run backup before migration"
fi

# 9. Migration Script Exists
echo ""
echo "9. Checking migration scripts..."
if [ -f "scripts/migrate-pg-to-redis.py" ]; then
    check_pass "Migration script found"
else
    check_fail "Migration script missing"
fi

if [ -f "scripts/rollback-migration.sh" ]; then
    check_pass "Rollback script found"
else
    check_fail "Rollback script missing"
fi

# 10. Python Dependencies
echo ""
echo "10. Checking Python dependencies..."
if python3 -c "import psycopg2; import redis; import json" 2>/dev/null; then
    check_pass "Python dependencies installed"
else
    check_fail "Missing Python dependencies (psycopg2, redis)"
fi

# 11. Worker Availability
echo ""
echo "11. Checking worker nodes..."
worker_count=0
for worker in server-01 server-02 server-03 pi-01 laptop-01; do
    if ssh -o ConnectTimeout=2 claude@$worker "exit" 2>/dev/null; then
        worker_count=$((worker_count + 1))
    fi
done

echo "   Available workers: $worker_count/5"
if [ "$worker_count" -ge 3 ]; then
    check_pass "Sufficient workers available ($worker_count/5)"
else
    check_warn "Few workers available ($worker_count/5)"
fi

# Summary
echo ""
echo "================================================"
echo "Summary"
echo "================================================"
echo -e "Checks passed: ${GREEN}$CHECKS_PASSED${NC}"
echo -e "Checks failed: ${RED}$CHECKS_FAILED${NC}"
echo -e "Warnings: ${YELLOW}$WARNINGS${NC}"
echo ""

if [ "$CHECKS_FAILED" -eq 0 ]; then
    if [ "$WARNINGS" -eq 0 ]; then
        echo -e "${GREEN}✓ System ready for migration!${NC}"
        echo ""
        echo "Next steps:"
        echo "  1. Review migration plan: docs/POSTGRESQL_TO_REDIS_MIGRATION_STRATEGY.md"
        echo "  2. Preview migration: python3 scripts/migrate-pg-to-redis.py --dry-run"
        echo "  3. Execute migration: python3 scripts/migrate-pg-to-redis.py"
        exit 0
    else
        echo -e "${YELLOW}⚠ System ready with warnings${NC}"
        echo ""
        echo "Address warnings before migration:"
        echo "  - Stop auto-scraper: curl -X POST http://aio-01:5000/fleet/auto-deploy/stop"
        echo "  - Wait for processing items to complete"
        echo "  - Create backup if needed"
        echo "  - Clear Redis queues if not empty"
        exit 0
    fi
else
    echo -e "${RED}✗ System NOT ready for migration${NC}"
    echo ""
    echo "Fix failed checks before proceeding."
    exit 1
fi
