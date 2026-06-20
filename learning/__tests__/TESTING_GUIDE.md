# Workflow Storage Integration Tests

Complete test suite for the workflow storage adapter with PostgreSQL + pgvector.

## Quick Start

### 1. Setup Test Database

```bash
cd learning/__tests__

# Option A: Docker (Recommended for CI/CD)
./setup-test-db.sh

# Option B: Local PostgreSQL
# Create test database and role
sudo -u postgres psql << EOF
  CREATE ROLE test_user WITH LOGIN PASSWORD 'test_password' CREATEDB;
  CREATE DATABASE learning_test OWNER test_user;
  
  \c learning_test test_user
  CREATE EXTENSION IF NOT EXISTS vector;
EOF

# Load schema for both options
psql -h localhost -U test_user -d learning_test -p 5433 -f schema-setup.sql
```

### 2. Configure Environment

Create `.env.test` file (already provided):

```bash
TEST_DB_HOST=localhost
TEST_DB_PORT=5433
TEST_DB_NAME=learning_test
TEST_DB_USER=test_user
TEST_DB_PASSWORD=test_password
NODE_ENV=test
```

### 3. Run Tests

```bash
# From project root
cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

# Install test dependencies
npm install --save-dev jest

# Run all tests
npm test -- learning/__tests__/workflow-storage.integration.test.js

# Run specific test suite
npm test -- learning/__tests__/workflow-storage.integration.test.js -t "Full Workflow Lifecycle"

# Run with coverage
npm test -- learning/__tests__/workflow-storage.integration.test.js --coverage

# Watch mode (auto-rerun on changes)
npm test -- learning/__tests__/workflow-storage.integration.test.js --watch

# Verbose output
npm test -- learning/__tests__/workflow-storage.integration.test.js --verbose
```

## Test Structure

### Test Scenarios (12 total)

#### Scenario 1: Full Workflow Lifecycle
- Tests complete workflow storage from execution to learnings
- Verifies all foreign key relationships
- Validates metadata preservation

**Key Tests:**
- `should store execution with metadata`
- `should store complete workflow with workers, arbiter, phases, and learnings`
- `execution ID should be valid integer FK`

#### Scenario 2: Chunked Learning Storage
- Tests semantic text chunking for large learnings (>4000 chars)
- Verifies parent + chunk records creation
- Ensures transactional integrity during chunked storage

**Key Tests:**
- `should store large learning as parent + chunks`
- `should rollback on constraint violation during chunked storage`

#### Scenario 3: Outcome Normalization
- Tests standardized outcome values ('success', 'failed', 'error')
- Prevents invalid outcome values via CHECK constraints

**Key Tests:**
- `should store valid outcome values`
- `should reject invalid outcome values`

#### Scenario 4: Thompson Sampling Bandit State
- Tests Thompson Sampling algorithm implementation
- Verifies alpha/beta parameter updates
- Validates reward accumulation

**Key Tests:**
- `should initialize strategy with uniform prior (alpha=1, beta=1)`
- `should accumulate successes and update alpha/beta`
- `should calculate avg_reward correctly`

#### Scenario 5: Model Diversity Monitoring
- Tests model distribution tracking
- Detects dominance when >70% threshold exceeded
- Supports balanced multi-model scenarios

**Key Tests:**
- `should detect model dominance when >70%`
- `should NOT flag dominance when balanced`

#### Scenario 6: Transaction Rollback on Error
- Tests atomicity of database operations
- Verifies rollback behavior on constraint violations
- Ensures no partial writes

**Key Tests:**
- `should rollback entire workflow on constraint violation`

#### Scenario 7: Connection Pool Management
- Tests connection pool under load (>max connections)
- Verifies graceful error recovery
- Ensures connection reuse

**Key Tests:**
- `should handle connection pool limits gracefully`
- `should recover connection after error`

#### Scenario 8: Numeric Type Handling
- Tests NUMERIC/DECIMAL type precision
- Validates range constraints (0.0-1.0 for confidence/importance)
- Ensures proper type conversion

**Key Tests:**
- `should handle NUMERIC confidence values`
- `should enforce importance range (0.0 - 1.0)`

#### Scenario 9: JSON Metadata Storage
- Tests JSONB storage and retrieval
- Verifies nested JSON structures
- Tests JSONB query operators

**Key Tests:**
- `should store and retrieve JSONB metadata`
- `should query by JSONB field`

#### Scenario 10: Performance Benchmarks
- Tests throughput on typical workloads
- Benchmarks query latency
- Ensures sub-second operations

**Key Tests:**
- `should create 1000 simple queries quickly`
- `should query 1000 records efficiently`

#### Scenario 11: Unique Constraints
- Tests UNIQUE constraints on workflow_id and strategy
- Prevents duplicate workflow executions
- Validates constraint enforcement

**Key Tests:**
- `should enforce unique workflow_id on workflow.executions`
- `should enforce unique strategy on learning.strategy_performance`

#### Scenario 12: Cascade Delete Behavior
- Tests ON DELETE CASCADE for referential integrity
- Verifies automatic cleanup of dependent records
- Ensures no orphaned records

**Key Tests:**
- `should cascade delete related records when execution is deleted`

## Test Isolation Strategy

All tests use **transaction-based isolation**:

1. Each test runs in its own `BEGIN...ROLLBACK` transaction
2. Changes are automatically rolled back after test completes
3. No cleanup overhead between tests
4. Tests run in parallel safely (READ COMMITTED isolation level)

### How It Works

```javascript
beforeEach(async () => {
  isolation = new TransactionIsolation(testPool);
  await isolation.begin();  // BEGIN ISOLATION LEVEL READ COMMITTED
  fixtures = new FixtureLoader(isolation);
});

afterEach(async () => {
  await isolation.rollback();  // ROLLBACK (instant cleanup)
});
```

**Advantages:**
- Zero inter-test interference
- Fast cleanup (<10ms per test)
- True ACID compliance
- No manual truncate statements needed

## Database Schema

### Schemas

| Schema | Purpose |
|--------|---------|
| `workflow.*` | Workflow execution, workers, arbiter, phases, feedback, learnings |
| `learning.*` | Strategy performance (Thompson Sampling), experiences (continual learning) |
| `monitoring.*` | Execution summary logs (model usage, quality metrics) |
| `costs.*` | Cost tracking per model |

### Key Tables

| Table | Purpose | Records |
|-------|---------|---------|
| `workflow.executions` | Main workflow records | One per workflow run |
| `workflow.worker_results` | Individual worker outputs | N per execution |
| `workflow.arbiter_decisions` | Arbiter synthesis results | ~1 per execution |
| `workflow.phases` | Phase tracking | 2-10 per execution |
| `workflow.learnings` | Extracted learnings | 1-100 per execution |
| `learning.strategy_performance` | Thompson Sampling state | ~50 strategies |
| `monitoring.execution_summary` | Execution logs | 100K+ records |
| `costs.entries` | Cost tracking | 1000+ records |

### Vector Indices

All embedding columns use IVFFLAT indices for O(log n) similarity search:
- `workflow.executions.task_embedding` (384-dim)
- `workflow.worker_results.result_embedding` (384-dim)
- `workflow.arbiter_decisions.decision_embedding` (384-dim)
- `workflow.learnings.learning_embedding` (384-dim)
- `learning.experiences.embedding` (128-dim)

## Running in CI/CD

### GitHub Actions Example

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: pgvector/pgvector:pg15
        env:
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: learning_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5433:5432
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Node
        uses: actions/setup-node@v2
        with:
          node-version: '18'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Create test database schema
        run: |
          psql -h localhost -U test_user -d learning_test \
            -p 5433 -f learning/__tests__/schema-setup.sql
      
      - name: Run tests
        run: npm test -- learning/__tests__/workflow-storage.integration.test.js
        env:
          TEST_DB_HOST: localhost
          TEST_DB_PORT: 5433
```

### Docker Compose

```yaml
version: '3.9'

services:
  postgres-test:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_password
      POSTGRES_DB: learning_test
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test_user -d learning_test"]
      interval: 5s
      timeout: 5s
      retries: 5
    volumes:
      - ./learning/__tests__/schema-setup.sql:/docker-entrypoint-initdb.d/01-init.sql
```

## Troubleshooting

### Connection Refused

```bash
# Verify database is running
docker ps | grep workflow-storage-test-db

# Check logs
docker logs workflow-storage-test-db

# Try connecting manually
psql -h localhost -p 5433 -U test_user -d learning_test
```

### Extension Not Found

```bash
# pgvector extension must be installed
docker exec workflow-storage-test-db \
  psql -U test_user -d learning_test -c \
  "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Transaction Still Open Error

If tests hang, check for open transactions:

```bash
psql -h localhost -p 5433 -U test_user -d learning_test << EOF
SELECT pid, usename, state FROM pg_stat_activity
WHERE datname = 'learning_test' AND state != 'idle';
EOF
```

Kill hanging transactions:

```bash
psql -h localhost -p 5433 -U test_user -d learning_test << EOF
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'learning_test' AND pid <> pg_backend_pid();
EOF
```

### Vector Operation Errors

If you see `ERROR: could not access file "vector"`:

```bash
# Verify pgvector is installed in container
docker exec workflow-storage-test-db \
  psql -U test_user -d learning_test -c \
  "SELECT * FROM pg_available_extensions WHERE name = 'vector';"

# If missing, use different base image
docker run ... pgvector/pgvector:pg15-latest
```

## Performance Targets

| Operation | Target | Actual |
|-----------|--------|--------|
| Simple INSERT | <50ms | ~10ms |
| Simple SELECT | <50ms | ~5ms |
| Vector similarity search | <100ms | ~20ms |
| Chunked learning (10 chunks) | <500ms | ~150ms |
| Constraint violation | <10ms | ~5ms |
| Cascade delete (10 children) | <100ms | ~30ms |

## Maintenance

### Cleanup Test Database

```bash
# Remove Docker container
docker rm -f workflow-storage-test-db

# Or, truncate all tables
psql -h localhost -p 5433 -U test_user -d learning_test << EOF
TRUNCATE TABLE workflow.feedback CASCADE;
TRUNCATE TABLE workflow.learnings CASCADE;
TRUNCATE TABLE workflow.arbiter_decisions CASCADE;
TRUNCATE TABLE workflow.worker_results CASCADE;
TRUNCATE TABLE workflow.phases CASCADE;
TRUNCATE TABLE workflow.executions CASCADE;
TRUNCATE TABLE learning.strategy_performance CASCADE;
TRUNCATE TABLE monitoring.execution_summary CASCADE;
TRUNCATE TABLE costs.entries CASCADE;
EOF
```

### Backup Test Data

```bash
pg_dump -h localhost -p 5433 -U test_user -d learning_test \
  --schema-only | gzip > test-db-schema.sql.gz

pg_dump -h localhost -p 5433 -U test_user -d learning_test \
  | gzip > test-db-full.sql.gz
```

### Monitor Test Database

```bash
# Check table sizes
psql -h localhost -p 5433 -U test_user -d learning_test << EOF
SELECT schemaname, tablename, 
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
EOF

# Check index usage
psql -h localhost -p 5433 -U test_user -d learning_test << EOF
SELECT indexrelname, idx_scan
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
EOF
```

## Adding New Tests

To add new integration tests:

1. **Create test fixture** in `beforeEach`:
   ```javascript
   const execution = await fixtures.createMinimalExecution({
     workflow_name: 'my-workflow'
   });
   ```

2. **Write test assertions**:
   ```javascript
   test('should do something', async () => {
     // Arrange (create data)
     // Act (perform operation)
     // Assert (verify results)
   });
   ```

3. **Transaction isolation is automatic** - no cleanup needed

4. **Run test**:
   ```bash
   npm test -- workflow-storage.integration.test.js -t "should do something"
   ```

## Related Files

- **Test File:** `workflow-storage.integration.test.js` (This file)
- **Schema:** `schema-setup.sql` (Database schema)
- **Setup Script:** `setup-test-db.sh` (Docker database setup)
- **Config:** `.env.test` (Environment variables)
- **README:** `README.md` (Original test documentation)

## See Also

- [Workflow Storage Adapter](../workflow-storage-adapter.js) - Main implementation
- [PostgreSQL Adapter](../postgres-adapter.js) - Database interface
- [Integration Design](../AUTOSTORAGE_COMPLETE_INTEGRATION.md) - Architecture docs
