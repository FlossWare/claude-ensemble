# Quick Reference: Workflow Storage Tests

## Setup (One Time)

```bash
cd learning/__tests__
./setup-test-db.sh                    # Start Docker container
psql -h localhost -p 5433 \           # Load schema
  -U test_user -d learning_test \
  -f schema-setup.sql
```

## Run Tests

```bash
# All tests
npm test -- learning/__tests__/workflow-storage.integration.test.js

# Specific scenario
npm test -- workflow-storage.integration.test.js -t "Full Workflow Lifecycle"

# With output
npm test -- workflow-storage.integration.test.js --verbose

# Watch mode
npm test -- workflow-storage.integration.test.js --watch
```

## Test Scenarios (12 total, 33 tests)

| # | Scenario | Tests | Key Validation |
|---|----------|-------|-----------------|
| 1 | Full Workflow Lifecycle | 3 | Execution, workers, arbiter, phases, learnings |
| 2 | Chunked Learning Storage | 2 | Large text (>4000 chars), parent + chunks |
| 3 | Outcome Normalization | 2 | Valid outcomes, constraint enforcement |
| 4 | Thompson Sampling | 3 | Bandit state, alpha/beta, reward accumulation |
| 5 | Model Diversity | 2 | Dominance detection (>70%), balance check |
| 6 | Transaction Rollback | 1 | Atomicity on constraint violations |
| 7 | Connection Pool | 2 | >max connections, error recovery |
| 8 | Numeric Types | 2 | Precision, range constraints (0.0-1.0) |
| 9 | JSON Metadata | 2 | JSONB storage, nested queries |
| 10 | Performance | 2 | Insert 100 in <10s, query 100 in <1s |
| 11 | Unique Constraints | 2 | workflow_id, strategy uniqueness |
| 12 | Cascade Delete | 1 | Foreign key CASCADE cleanup |

## Database Connection

```
Host:     localhost
Port:     5433
Database: learning_test
User:     test_user
Password: test_password
```

## Key Files

| File | Purpose |
|------|---------|
| workflow-storage.integration.test.js | Main test file (850+ lines) |
| schema-setup.sql | Database schema (350+ lines) |
| setup-test-db.sh | Docker setup (executable) |
| .env.test | Configuration |
| TESTING_GUIDE.md | Full documentation |

## Cleanup

```bash
# Remove Docker container
docker rm -f workflow-storage-test-db

# Or truncate all tables in psql
TRUNCATE TABLE workflow.feedback CASCADE;
TRUNCATE TABLE workflow.learnings CASCADE;
TRUNCATE TABLE workflow.arbiter_decisions CASCADE;
TRUNCATE TABLE workflow.worker_results CASCADE;
TRUNCATE TABLE workflow.phases CASCADE;
TRUNCATE TABLE workflow.executions CASCADE;
TRUNCATE TABLE learning.strategy_performance CASCADE;
TRUNCATE TABLE monitoring.execution_summary CASCADE;
TRUNCATE TABLE costs.entries CASCADE;
```

## See Also

- TESTING_GUIDE.md - Full documentation
- TEST_SUMMARY.md - Detailed overview
