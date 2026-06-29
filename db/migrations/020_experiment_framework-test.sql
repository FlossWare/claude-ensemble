-- Test: 020_experiment_framework
-- Validates the experiment tracking schema created by 020_experiment_framework.sql
-- Run: psql -U sfloess -d learning -f db/migrations/020_experiment_framework-test.sql
--
-- Strategy: insert test data, verify constraints, query patterns, then clean up.
-- All operations are wrapped in a transaction that rolls back so the test is side-effect free.

BEGIN;

-- ============================================================
-- 1. Verify schema and tables exist
-- ============================================================
DO $$
BEGIN
    -- Schema exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'experiments') THEN
        RAISE EXCEPTION 'FAIL: experiments schema does not exist';
    END IF;
    RAISE NOTICE 'PASS: experiments schema exists';

    -- Registry table exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables
                   WHERE table_schema = 'experiments' AND table_name = 'registry') THEN
        RAISE EXCEPTION 'FAIL: experiments.registry table does not exist';
    END IF;
    RAISE NOTICE 'PASS: experiments.registry table exists';

    -- Runs table exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables
                   WHERE table_schema = 'experiments' AND table_name = 'runs') THEN
        RAISE EXCEPTION 'FAIL: experiments.runs table does not exist';
    END IF;
    RAISE NOTICE 'PASS: experiments.runs table exists';
END $$;

-- ============================================================
-- 2. Verify registry columns
-- ============================================================
DO $$
DECLARE
    col_count INTEGER;
BEGIN
    SELECT count(*) INTO col_count
    FROM information_schema.columns
    WHERE table_schema = 'experiments' AND table_name = 'registry'
      AND column_name IN ('id', 'name', 'hypothesis', 'metric',
                          'success_criteria', 'status', 'created_at', 'updated_at');

    IF col_count <> 8 THEN
        RAISE EXCEPTION 'FAIL: experiments.registry missing columns (found %/8)', col_count;
    END IF;
    RAISE NOTICE 'PASS: experiments.registry has all 8 expected columns';
END $$;

-- ============================================================
-- 3. Verify runs columns
-- ============================================================
DO $$
DECLARE
    col_count INTEGER;
BEGIN
    SELECT count(*) INTO col_count
    FROM information_schema.columns
    WHERE table_schema = 'experiments' AND table_name = 'runs'
      AND column_name IN ('id', 'experiment_id', 'baseline_config',
                          'treatment_config', 'result', 'verdict', 'run_date');

    IF col_count <> 7 THEN
        RAISE EXCEPTION 'FAIL: experiments.runs missing columns (found %/7)', col_count;
    END IF;
    RAISE NOTICE 'PASS: experiments.runs has all 7 expected columns';
END $$;

-- ============================================================
-- 4. Verify indexes exist
-- ============================================================
DO $$
DECLARE
    idx_name TEXT;
    expected_indexes TEXT[] := ARRAY[
        'idx_registry_status',
        'idx_registry_name',
        'idx_registry_created_at',
        'idx_runs_experiment_id',
        'idx_runs_verdict',
        'idx_runs_run_date',
        'idx_runs_experiment_date'
    ];
BEGIN
    FOREACH idx_name IN ARRAY expected_indexes LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_indexes
                       WHERE schemaname = 'experiments' AND indexname = idx_name) THEN
            RAISE EXCEPTION 'FAIL: index % does not exist', idx_name;
        END IF;
    END LOOP;
    RAISE NOTICE 'PASS: all 7 indexes exist';
END $$;

-- ============================================================
-- 5. Insert test data into registry
-- ============================================================
-- Use a savepoint so constraint-violation tests can continue
SAVEPOINT before_inserts;

INSERT INTO experiments.registry (name, hypothesis, metric, success_criteria, status)
VALUES
    ('test-latency-reduction',
     'Switching to connection pooling reduces p95 latency by >20%',
     'p95_latency_ms',
     'p95 < 80ms (baseline 100ms)',
     'active'),
    ('test-cache-hit-rate',
     'Adding a local cache increases hit rate above 90%',
     'cache_hit_rate',
     'hit_rate > 0.90',
     'draft');

DO $$
DECLARE
    cnt INTEGER;
BEGIN
    SELECT count(*) INTO cnt FROM experiments.registry
    WHERE name LIKE 'test-%';
    IF cnt <> 2 THEN
        RAISE EXCEPTION 'FAIL: expected 2 test experiments, found %', cnt;
    END IF;
    RAISE NOTICE 'PASS: inserted 2 test experiments';
END $$;

-- ============================================================
-- 6. Verify default values
-- ============================================================
DO $$
DECLARE
    rec RECORD;
BEGIN
    SELECT status, created_at, updated_at INTO rec
    FROM experiments.registry WHERE name = 'test-cache-hit-rate';

    IF rec.status <> 'draft' THEN
        RAISE EXCEPTION 'FAIL: default status should be draft, got %', rec.status;
    END IF;
    IF rec.created_at IS NULL THEN
        RAISE EXCEPTION 'FAIL: created_at should default to now()';
    END IF;
    IF rec.updated_at IS NULL THEN
        RAISE EXCEPTION 'FAIL: updated_at should default to now()';
    END IF;
    RAISE NOTICE 'PASS: default values (status=draft, timestamps set)';
END $$;

-- ============================================================
-- 7. Verify status CHECK constraint
-- ============================================================
DO $$
BEGIN
    BEGIN
        INSERT INTO experiments.registry (name, hypothesis, metric, success_criteria, status)
        VALUES ('test-bad-status', 'h', 'm', 'c', 'INVALID_STATUS');
        RAISE EXCEPTION 'FAIL: should have rejected invalid status';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'PASS: status CHECK constraint rejects invalid values';
    END;
END $$;

-- ============================================================
-- 8. Verify unique name constraint
-- ============================================================
DO $$
BEGIN
    BEGIN
        INSERT INTO experiments.registry (name, hypothesis, metric, success_criteria)
        VALUES ('test-latency-reduction', 'dup', 'dup', 'dup');
        RAISE EXCEPTION 'FAIL: should have rejected duplicate name';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'PASS: unique name constraint enforced';
    END;
END $$;

-- ============================================================
-- 9. Insert test runs
-- ============================================================
INSERT INTO experiments.runs (experiment_id, baseline_config, treatment_config, result, verdict)
SELECT id,
       '{"pool_size": 1}'::jsonb,
       '{"pool_size": 10}'::jsonb,
       '{"p95_latency_ms": 72, "samples": 1000}'::jsonb,
       'confirmed'
FROM experiments.registry WHERE name = 'test-latency-reduction';

INSERT INTO experiments.runs (experiment_id, baseline_config, treatment_config, result, verdict)
SELECT id,
       '{"pool_size": 1}'::jsonb,
       '{"pool_size": 5}'::jsonb,
       '{"p95_latency_ms": 95, "samples": 500}'::jsonb,
       'inconclusive'
FROM experiments.registry WHERE name = 'test-latency-reduction';

-- Run with NULL verdict (pending)
INSERT INTO experiments.runs (experiment_id, baseline_config, treatment_config)
SELECT id, '{"cache": false}'::jsonb, '{"cache": true}'::jsonb
FROM experiments.registry WHERE name = 'test-cache-hit-rate';

DO $$
DECLARE
    cnt INTEGER;
BEGIN
    SELECT count(*) INTO cnt FROM experiments.runs
    WHERE experiment_id IN (SELECT id FROM experiments.registry WHERE name LIKE 'test-%');
    IF cnt <> 3 THEN
        RAISE EXCEPTION 'FAIL: expected 3 test runs, found %', cnt;
    END IF;
    RAISE NOTICE 'PASS: inserted 3 test runs (2 with verdict, 1 pending)';
END $$;

-- ============================================================
-- 10. Verify verdict CHECK constraint
-- ============================================================
DO $$
BEGIN
    BEGIN
        INSERT INTO experiments.runs (experiment_id, baseline_config, treatment_config, verdict)
        SELECT id, '{}'::jsonb, '{}'::jsonb, 'WRONG'
        FROM experiments.registry WHERE name = 'test-latency-reduction';
        RAISE EXCEPTION 'FAIL: should have rejected invalid verdict';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'PASS: verdict CHECK constraint rejects invalid values';
    END;
END $$;

-- ============================================================
-- 11. Verify foreign key constraint (CASCADE delete)
-- ============================================================
DO $$
DECLARE
    exp_id INTEGER;
    run_count_before INTEGER;
    run_count_after INTEGER;
BEGIN
    SELECT id INTO exp_id FROM experiments.registry WHERE name = 'test-latency-reduction';
    SELECT count(*) INTO run_count_before FROM experiments.runs WHERE experiment_id = exp_id;

    DELETE FROM experiments.registry WHERE id = exp_id;

    SELECT count(*) INTO run_count_after FROM experiments.runs WHERE experiment_id = exp_id;

    IF run_count_before < 1 THEN
        RAISE EXCEPTION 'FAIL: should have had runs before delete';
    END IF;
    IF run_count_after <> 0 THEN
        RAISE EXCEPTION 'FAIL: CASCADE delete did not remove child runs (% remain)', run_count_after;
    END IF;
    RAISE NOTICE 'PASS: CASCADE delete removes child runs (% -> %)', run_count_before, run_count_after;
END $$;

-- ============================================================
-- 12. Verify updated_at trigger
-- ============================================================
DO $$
DECLARE
    ts_created TIMESTAMPTZ;
    ts_updated TIMESTAMPTZ;
BEGIN
    -- Record created_at (set at INSERT time via now() = transaction start)
    SELECT created_at INTO ts_created
    FROM experiments.registry WHERE name = 'test-cache-hit-rate';

    -- Wait so clock_timestamp() in trigger will differ from transaction-start now()
    PERFORM pg_sleep(0.05);

    UPDATE experiments.registry
    SET status = 'active'
    WHERE name = 'test-cache-hit-rate';

    SELECT updated_at INTO ts_updated
    FROM experiments.registry WHERE name = 'test-cache-hit-rate';

    -- The trigger uses clock_timestamp() which advances even within a transaction,
    -- so updated_at should be strictly greater than the transaction-start created_at.
    IF ts_updated <= ts_created THEN
        RAISE EXCEPTION 'FAIL: updated_at trigger did not fire (created=% updated=%)', ts_created, ts_updated;
    END IF;
    RAISE NOTICE 'PASS: updated_at trigger fires on UPDATE (created=% updated=%)', ts_created, ts_updated;
END $$;

-- ============================================================
-- 13. Verify JSONB query patterns work
-- ============================================================
DO $$
DECLARE
    cnt INTEGER;
BEGIN
    -- Query runs by JSONB field
    SELECT count(*) INTO cnt
    FROM experiments.runs
    WHERE (result->>'p95_latency_ms')::numeric < 100;

    -- Just verify the query does not error; count is not critical
    RAISE NOTICE 'PASS: JSONB query patterns work (% rows matched result filter)', cnt;
END $$;

-- ============================================================
-- 14. Verify join query pattern (registry + runs)
-- ============================================================
DO $$
DECLARE
    cnt INTEGER;
BEGIN
    SELECT count(*) INTO cnt
    FROM experiments.registry r
    JOIN experiments.runs rn ON rn.experiment_id = r.id
    WHERE r.status = 'active';

    RAISE NOTICE 'PASS: JOIN query between registry and runs works (% rows)', cnt;
END $$;

-- ============================================================
-- Summary
-- ============================================================
DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'ALL TESTS PASSED';
    RAISE NOTICE '========================================';
END $$;

-- Roll back all test data to leave database clean
ROLLBACK;
