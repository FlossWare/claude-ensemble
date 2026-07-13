#!/bin/bash
#
# Rollback PostgreSQL to Redis Migration
#
# Emergency script to revert migration if something goes wrong.
# Restores PostgreSQL queue.store items to 'pending' status.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PG_HOST="aio-01"
PG_PORT="5433"
PG_USER="sfloess"
PG_DB="learning"
REDIS_HOST="aio-01"

echo -e "${RED}================================${NC}"
echo -e "${RED}EMERGENCY ROLLBACK SCRIPT${NC}"
echo -e "${RED}================================${NC}"
echo ""
echo "This will:"
echo "  1. Stop Redis workers"
echo "  2. Flush Redis queues"
echo "  3. Restore PostgreSQL items to 'pending' status"
echo ""
echo -e "${YELLOW}WARNING: This should only be used if migration failed!${NC}"
echo ""
read -p "Are you sure you want to rollback? (type 'yes' to confirm): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Rollback cancelled."
    exit 0
fi

echo ""
echo "Step 1: Stopping Redis workers..."
echo "==============================="

# Stop Redis workers on all fleet nodes
for worker in server-01 server-02 server-03 pi-01 laptop-01; do
    echo "Stopping worker on $worker..."
    ssh claude@$worker "pkill -f 'redis-queue-worker.py' || true" 2>/dev/null || true
done

echo -e "${GREEN}✓ Workers stopped${NC}"
sleep 2

echo ""
echo "Step 2: Flushing Redis queues..."
echo "==============================="

# Count items before flushing
echo "Counting items in Redis queues..."
high_count=$(ssh claude@$REDIS_HOST "redis-cli -h localhost LLEN redis:queue:store:high" 2>/dev/null || echo "0")
medium_count=$(ssh claude@$REDIS_HOST "redis-cli -h localhost LLEN redis:queue:store:medium" 2>/dev/null || echo "0")
low_count=$(ssh claude@$REDIS_HOST "redis-cli -h localhost LLEN redis:queue:store:low" 2>/dev/null || echo "0")
total_count=$((high_count + medium_count + low_count))

echo "  - High priority: $high_count"
echo "  - Medium priority: $medium_count"
echo "  - Low priority: $low_count"
echo "  - Total: $total_count"

if [ "$total_count" -gt 0 ]; then
    echo ""
    read -p "Delete $total_count items from Redis? (yes/no): " confirm_delete
    if [ "$confirm_delete" != "yes" ]; then
        echo "Rollback cancelled at flush step."
        exit 0
    fi

    # Flush queues
    ssh claude@$REDIS_HOST "redis-cli -h localhost DEL redis:queue:store:high redis:queue:store:medium redis:queue:store:low redis:idempotency:store" 2>/dev/null
    echo -e "${GREEN}✓ Redis queues flushed${NC}"
else
    echo "No items in Redis queues (already empty)"
fi

echo ""
echo "Step 3: Restoring PostgreSQL items..."
echo "====================================="

# Check current state
echo "Checking PostgreSQL queue state..."
migrated_count=$(psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -t -c "SELECT COUNT(*) FROM queue.store WHERE status = 'migrated';" 2>/dev/null | tr -d ' ')
pending_count=$(psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -t -c "SELECT COUNT(*) FROM queue.store WHERE status = 'pending';" 2>/dev/null | tr -d ' ')

echo "  - Migrated items: $migrated_count"
echo "  - Pending items: $pending_count"

if [ "$migrated_count" -eq 0 ]; then
    echo "No migrated items found. Nothing to restore."
    echo -e "${GREEN}✓ Rollback complete${NC}"
    exit 0
fi

echo ""
read -p "Restore $migrated_count items to 'pending' status? (yes/no): " confirm_restore
if [ "$confirm_restore" != "yes" ]; then
    echo "Rollback cancelled at restore step."
    exit 0
fi

# Restore items
psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -c "
    UPDATE queue.store
    SET status = 'pending',
        migrated_to_redis = FALSE,
        migrated_at = NULL
    WHERE status = 'migrated';
" 2>&1

restored_count=$(psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -t -c "SELECT COUNT(*) FROM queue.store WHERE status = 'pending';" 2>/dev/null | tr -d ' ')

echo -e "${GREEN}✓ Restored $restored_count items to pending${NC}"

echo ""
echo "Step 4: Verification..."
echo "======================="

# Verify state
final_pending=$(psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -t -c "SELECT COUNT(*) FROM queue.store WHERE status = 'pending';" 2>/dev/null | tr -d ' ')
final_migrated=$(psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DB -t -c "SELECT COUNT(*) FROM queue.store WHERE status = 'migrated';" 2>/dev/null | tr -d ' ')
final_redis=$(ssh claude@$REDIS_HOST "redis-cli -h localhost LLEN redis:queue:store:high" 2>/dev/null || echo "0")
final_redis=$((final_redis + $(ssh claude@$REDIS_HOST "redis-cli -h localhost LLEN redis:queue:store:medium" 2>/dev/null || echo "0")))
final_redis=$((final_redis + $(ssh claude@$REDIS_HOST "redis-cli -h localhost LLEN redis:queue:store:low" 2>/dev/null || echo "0")))

echo "Final state:"
echo "  - PostgreSQL pending: $final_pending"
echo "  - PostgreSQL migrated: $final_migrated"
echo "  - Redis queued: $final_redis"

if [ "$final_migrated" -eq 0 ] && [ "$final_redis" -eq 0 ]; then
    echo ""
    echo -e "${GREEN}================================${NC}"
    echo -e "${GREEN}✓ ROLLBACK SUCCESSFUL${NC}"
    echo -e "${GREEN}================================${NC}"
    echo ""
    echo "PostgreSQL queue restored to pre-migration state."
    echo "You can now restart PostgreSQL-based workers if needed."
else
    echo ""
    echo -e "${YELLOW}⚠ WARNING: Rollback may be incomplete${NC}"
    echo "  - Migrated items remaining: $final_migrated"
    echo "  - Redis items remaining: $final_redis"
    echo ""
    echo "Manual intervention may be required."
fi
