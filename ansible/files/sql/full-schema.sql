--
-- PostgreSQL database dump
--

\restrict loX8UIKKQU7dMak5804wozJnglwlJGjhNleUqat3bVWUCtA4J4J9hud5vRt61Dm

-- Dumped from database version 17.9 (Debian 17.9-0+deb13u1)
-- Dumped by pg_dump version 17.9 (Debian 17.9-0+deb13u1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: admin; Type: SCHEMA; Schema: -; Owner: claude
--

CREATE SCHEMA admin;


ALTER SCHEMA admin OWNER TO claude;

--
-- Name: auth; Type: SCHEMA; Schema: -; Owner: sfloess
--

CREATE SCHEMA auth;


ALTER SCHEMA auth OWNER TO sfloess;

--
-- Name: auto_storage; Type: SCHEMA; Schema: -; Owner: claude
--

CREATE SCHEMA auto_storage;


ALTER SCHEMA auto_storage OWNER TO claude;

--
-- Name: config; Type: SCHEMA; Schema: -; Owner: claude
--

CREATE SCHEMA config;


ALTER SCHEMA config OWNER TO claude;

--
-- Name: costs; Type: SCHEMA; Schema: -; Owner: sfloess
--

CREATE SCHEMA costs;


ALTER SCHEMA costs OWNER TO sfloess;

--
-- Name: dedup; Type: SCHEMA; Schema: -; Owner: claude
--

CREATE SCHEMA dedup;


ALTER SCHEMA dedup OWNER TO claude;

--
-- Name: documents; Type: SCHEMA; Schema: -; Owner: sfloess
--

CREATE SCHEMA documents;


ALTER SCHEMA documents OWNER TO sfloess;

--
-- Name: evaluation; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA evaluation;


ALTER SCHEMA evaluation OWNER TO postgres;

--
-- Name: SCHEMA evaluation; Type: COMMENT; Schema: -; Owner: postgres
--

COMMENT ON SCHEMA evaluation IS 'Evaluation and benchmarking schema for multi-AI model assessment';


--
-- Name: experiments; Type: SCHEMA; Schema: -; Owner: sfloess
--

CREATE SCHEMA experiments;


ALTER SCHEMA experiments OWNER TO sfloess;

--
-- Name: fleet; Type: SCHEMA; Schema: -; Owner: claude
--

CREATE SCHEMA fleet;


ALTER SCHEMA fleet OWNER TO claude;

--
-- Name: ga; Type: SCHEMA; Schema: -; Owner: claude
--

CREATE SCHEMA ga;


ALTER SCHEMA ga OWNER TO claude;

--
-- Name: inventory; Type: SCHEMA; Schema: -; Owner: claude
--

CREATE SCHEMA inventory;


ALTER SCHEMA inventory OWNER TO claude;

--
-- Name: knowledge; Type: SCHEMA; Schema: -; Owner: sfloess
--

CREATE SCHEMA knowledge;


ALTER SCHEMA knowledge OWNER TO sfloess;

--
-- Name: learning; Type: SCHEMA; Schema: -; Owner: sfloess
--

CREATE SCHEMA learning;


ALTER SCHEMA learning OWNER TO sfloess;

--
-- Name: monitoring; Type: SCHEMA; Schema: -; Owner: sfloess
--

CREATE SCHEMA monitoring;


ALTER SCHEMA monitoring OWNER TO sfloess;

--
-- Name: orchestration; Type: SCHEMA; Schema: -; Owner: sfloess
--

CREATE SCHEMA orchestration;


ALTER SCHEMA orchestration OWNER TO sfloess;

--
-- Name: orchestrator; Type: SCHEMA; Schema: -; Owner: sfloess
--

CREATE SCHEMA orchestrator;


ALTER SCHEMA orchestrator OWNER TO sfloess;

--
-- Name: processing; Type: SCHEMA; Schema: -; Owner: claude
--

CREATE SCHEMA processing;


ALTER SCHEMA processing OWNER TO claude;

--
-- Name: queue; Type: SCHEMA; Schema: -; Owner: claude
--

CREATE SCHEMA queue;


ALTER SCHEMA queue OWNER TO claude;

--
-- Name: reasoning; Type: SCHEMA; Schema: -; Owner: claude
--

CREATE SCHEMA reasoning;


ALTER SCHEMA reasoning OWNER TO claude;

--
-- Name: scraping; Type: SCHEMA; Schema: -; Owner: sfloess
--

CREATE SCHEMA scraping;


ALTER SCHEMA scraping OWNER TO sfloess;

--
-- Name: search; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA search;


ALTER SCHEMA search OWNER TO postgres;

--
-- Name: storage; Type: SCHEMA; Schema: -; Owner: claude
--

CREATE SCHEMA storage;


ALTER SCHEMA storage OWNER TO claude;

--
-- Name: workflow; Type: SCHEMA; Schema: -; Owner: sfloess
--

CREATE SCHEMA workflow;


ALTER SCHEMA workflow OWNER TO sfloess;

--
-- Name: workflows; Type: SCHEMA; Schema: -; Owner: sfloess
--

CREATE SCHEMA workflows;


ALTER SCHEMA workflows OWNER TO sfloess;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


--
-- Name: find_similar_chunks(public.vector, double precision, integer); Type: FUNCTION; Schema: documents; Owner: sfloess
--

CREATE FUNCTION documents.find_similar_chunks(query_embedding public.vector, similarity_threshold double precision DEFAULT 0.7, max_results integer DEFAULT 10) RETURNS TABLE(chunk_id uuid, document_id uuid, content text, similarity double precision, metadata jsonb)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM (
        SELECT
            c.id AS chunk_id,
            c.document_id,
            c.content,
            (1 - (c.embedding <=> query_embedding))::double precision AS similarity,
            c.metadata
        FROM documents.chunks c
        ORDER BY c.embedding <=> query_embedding
        LIMIT max_results * 2
    ) subquery
    WHERE subquery.similarity >= similarity_threshold
    ORDER BY subquery.similarity DESC
    LIMIT max_results;
END;
$$;


ALTER FUNCTION documents.find_similar_chunks(query_embedding public.vector, similarity_threshold double precision, max_results integer) OWNER TO sfloess;

--
-- Name: update_updated_at(); Type: FUNCTION; Schema: documents; Owner: sfloess
--

CREATE FUNCTION documents.update_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION documents.update_updated_at() OWNER TO sfloess;

--
-- Name: calculate_overall_score(double precision, double precision, double precision, double precision, double precision); Type: FUNCTION; Schema: evaluation; Owner: sfloess
--

CREATE FUNCTION evaluation.calculate_overall_score(correctness double precision, robustness double precision, generalization double precision, bias_resistance double precision, reproducibility double precision) RETURNS double precision
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN ROUND(
        (correctness * 0.35 + robustness * 0.20 + generalization * 0.20 + bias_resistance * 0.15 + reproducibility * 0.10)::NUMERIC,
        3
    )::FLOAT;
END;
$$;


ALTER FUNCTION evaluation.calculate_overall_score(correctness double precision, robustness double precision, generalization double precision, bias_resistance double precision, reproducibility double precision) OWNER TO sfloess;

--
-- Name: refresh_materialized_views(); Type: FUNCTION; Schema: evaluation; Owner: sfloess
--

CREATE FUNCTION evaluation.refresh_materialized_views() RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY evaluation.benchmark_stats;
    REFRESH MATERIALIZED VIEW CONCURRENTLY evaluation.model_performance;
    REFRESH MATERIALIZED VIEW CONCURRENTLY evaluation.task_model_performance;
END;
$$;


ALTER FUNCTION evaluation.refresh_materialized_views() OWNER TO sfloess;

--
-- Name: update_result_overall_score(); Type: FUNCTION; Schema: evaluation; Owner: sfloess
--

CREATE FUNCTION evaluation.update_result_overall_score() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.overall_score := evaluation.calculate_overall_score(
        NEW.correctness_score,
        NEW.robustness_score,
        NEW.generalization_score,
        NEW.bias_resistance_score,
        NEW.reproducibility_score
    );
    RETURN NEW;
END;
$$;


ALTER FUNCTION evaluation.update_result_overall_score() OWNER TO sfloess;

--
-- Name: update_registry_timestamp(); Type: FUNCTION; Schema: experiments; Owner: sfloess
--

CREATE FUNCTION experiments.update_registry_timestamp() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = clock_timestamp();
    RETURN NEW;
END;
$$;


ALTER FUNCTION experiments.update_registry_timestamp() OWNER TO sfloess;

--
-- Name: capability_confidence(integer); Type: FUNCTION; Schema: monitoring; Owner: sfloess
--

CREATE FUNCTION monitoring.capability_confidence(executions integer) RETURNS numeric
    LANGUAGE plpgsql IMMUTABLE
    AS $$
BEGIN
  RETURN 1.0 / (1.0 + EXP(-0.05 * (executions - 50)));
END;
$$;


ALTER FUNCTION monitoring.capability_confidence(executions integer) OWNER TO sfloess;

--
-- Name: FUNCTION capability_confidence(executions integer); Type: COMMENT; Schema: monitoring; Owner: sfloess
--

COMMENT ON FUNCTION monitoring.capability_confidence(executions integer) IS 'Calculate confidence score (0-1) from execution count using sigmoid function';


--
-- Name: get_capability_with_confidence(text, text); Type: FUNCTION; Schema: monitoring; Owner: sfloess
--

CREATE FUNCTION monitoring.get_capability_with_confidence(p_model text, p_task_type text) RETURNS TABLE(score numeric, confidence numeric, executions integer, source text)
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
  RETURN QUERY
  SELECT
    capability_score AS score,
    monitoring.capability_confidence(model_capabilities.executions) AS confidence,
    model_capabilities.executions,
    'database'::TEXT AS source
  FROM monitoring.model_capabilities
  WHERE model = p_model AND task_type = p_task_type;
END;
$$;


ALTER FUNCTION monitoring.get_capability_with_confidence(p_model text, p_task_type text) OWNER TO sfloess;

--
-- Name: FUNCTION get_capability_with_confidence(p_model text, p_task_type text); Type: COMMENT; Schema: monitoring; Owner: sfloess
--

COMMENT ON FUNCTION monitoring.get_capability_with_confidence(p_model text, p_task_type text) IS 'Get capability score with confidence interval for a model/task combination';


--
-- Name: refresh_model_capabilities_top(); Type: FUNCTION; Schema: monitoring; Owner: sfloess
--

CREATE FUNCTION monitoring.refresh_model_capabilities_top() RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY monitoring.model_capabilities_top;
END;
$$;


ALTER FUNCTION monitoring.refresh_model_capabilities_top() OWNER TO sfloess;

--
-- Name: trigger_refresh_capabilities_top(); Type: FUNCTION; Schema: monitoring; Owner: sfloess
--

CREATE FUNCTION monitoring.trigger_refresh_capabilities_top() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  -- Refresh asynchronously (don't block inserts)
  PERFORM monitoring.refresh_model_capabilities_top();
  RETURN NULL;
END;
$$;


ALTER FUNCTION monitoring.trigger_refresh_capabilities_top() OWNER TO sfloess;

--
-- Name: cleanup_expired(); Type: FUNCTION; Schema: orchestrator; Owner: sfloess
--

CREATE FUNCTION orchestrator.cleanup_expired() RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  -- Expire old sessions
  UPDATE orchestrator.sessions SET status = 'dead', expires_at = NOW()
  WHERE last_heartbeat < NOW() - INTERVAL '2 minutes' AND status = 'active';

  -- Delete expired messages
  DELETE FROM orchestrator.messages WHERE expires_at < NOW();

  -- Delete expired file locks
  DELETE FROM orchestrator.file_locks WHERE expires_at < NOW();

  -- Delete old completed work
  DELETE FROM orchestrator.work_queue WHERE status = 'completed' AND expires_at < NOW();

  -- Note: VACUUM must be run separately via cron/external job, not in function
END;
$$;


ALTER FUNCTION orchestrator.cleanup_expired() OWNER TO sfloess;

--
-- Name: claim_work(text, text, integer); Type: FUNCTION; Schema: processing; Owner: sfloess
--

CREATE FUNCTION processing.claim_work(p_worker_id text, p_queue_type text, p_batch_size integer DEFAULT 1) RETURNS TABLE(work_id bigint, source_file_id integer, chunk_id bigint, metadata jsonb)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    UPDATE processing.work_queue
    SET claimed_at = NOW(),
        claimed_by = p_worker_id
    WHERE id IN (
        SELECT id
        FROM processing.work_queue
        WHERE queue_type = p_queue_type
        AND claimed_at IS NULL
        AND failed_at IS NULL
        AND (retry_count < max_retries OR max_retries IS NULL)
        ORDER BY priority DESC, created_at ASC
        LIMIT p_batch_size
        FOR UPDATE SKIP LOCKED
    )
    RETURNING id, work_queue.source_file_id, work_queue.chunk_id, work_queue.metadata;
END;
$$;


ALTER FUNCTION processing.claim_work(p_worker_id text, p_queue_type text, p_batch_size integer) OWNER TO sfloess;

--
-- Name: complete_work(bigint, integer); Type: FUNCTION; Schema: processing; Owner: sfloess
--

CREATE FUNCTION processing.complete_work(p_work_id bigint, p_duration_ms integer DEFAULT NULL::integer) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    UPDATE processing.work_queue
    SET completed_at = NOW(),
        processing_duration_ms = p_duration_ms
    WHERE id = p_work_id;
END;
$$;


ALTER FUNCTION processing.complete_work(p_work_id bigint, p_duration_ms integer) OWNER TO sfloess;

--
-- Name: fail_work(bigint, text); Type: FUNCTION; Schema: processing; Owner: sfloess
--

CREATE FUNCTION processing.fail_work(p_work_id bigint, p_error_message text) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_retry_count INTEGER;
    v_max_retries INTEGER;
BEGIN
    UPDATE processing.work_queue
    SET retry_count = retry_count + 1,
        claimed_at = NULL,
        claimed_by = NULL,
        error_message = p_error_message
    WHERE id = p_work_id
    RETURNING retry_count, max_retries INTO v_retry_count, v_max_retries;

    -- Mark as permanently failed if max retries exceeded
    IF v_retry_count >= v_max_retries THEN
        UPDATE processing.work_queue
        SET failed_at = NOW()
        WHERE id = p_work_id;
    END IF;
END;
$$;


ALTER FUNCTION processing.fail_work(p_work_id bigint, p_error_message text) OWNER TO sfloess;

--
-- Name: get_pipeline_stats(); Type: FUNCTION; Schema: processing; Owner: sfloess
--

CREATE FUNCTION processing.get_pipeline_stats() RETURNS TABLE(stage text, pending bigint, processing bigint, completed bigint, failed bigint, rate_per_sec numeric, eta_hours numeric)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    WITH recent_completions AS (
        SELECT
            queue_type,
            COUNT(*) as completed_last_hour
        FROM processing.work_queue
        WHERE completed_at > NOW() - INTERVAL '1 hour'
        GROUP BY queue_type
    )
    SELECT
        q.queue_type::TEXT as stage,
        COUNT(*) FILTER (WHERE q.claimed_at IS NULL AND q.failed_at IS NULL) as pending,
        COUNT(*) FILTER (WHERE q.claimed_at IS NOT NULL AND q.completed_at IS NULL) as processing,
        COUNT(*) FILTER (WHERE q.completed_at IS NOT NULL) as completed,
        COUNT(*) FILTER (WHERE q.failed_at IS NOT NULL) as failed,
        COALESCE(rc.completed_last_hour / 3600.0, 0)::NUMERIC as rate_per_sec,
        CASE
            WHEN COALESCE(rc.completed_last_hour, 0) > 0 THEN
                (COUNT(*) FILTER (WHERE q.claimed_at IS NULL AND q.failed_at IS NULL)::NUMERIC /
                 (rc.completed_last_hour / 3600.0)) / 3600.0
            ELSE NULL
        END as eta_hours
    FROM processing.work_queue q
    LEFT JOIN recent_completions rc ON q.queue_type = rc.queue_type
    GROUP BY q.queue_type, rc.completed_last_hour;
END;
$$;


ALTER FUNCTION processing.get_pipeline_stats() OWNER TO sfloess;

--
-- Name: reclaim_stale_work(integer); Type: FUNCTION; Schema: processing; Owner: sfloess
--

CREATE FUNCTION processing.reclaim_stale_work(p_timeout_minutes integer DEFAULT 15) RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_reclaimed INTEGER;
BEGIN
    -- Bug 2 Fix: Check workers.last_heartbeat before reclaiming
    UPDATE processing.work_queue wq
    SET claimed_at = NULL,
        claimed_by = NULL,
        retry_count = retry_count + 1
    WHERE wq.claimed_at < NOW() - (p_timeout_minutes || ' minutes')::INTERVAL
    AND wq.completed_at IS NULL
    AND wq.failed_at IS NULL
    AND NOT EXISTS (
        SELECT 1 FROM processing.workers w
        WHERE w.worker_id = wq.claimed_by
        AND w.last_heartbeat > NOW() - (p_timeout_minutes || ' minutes')::INTERVAL
        AND w.status = 'active'
    );

    GET DIAGNOSTICS v_reclaimed = ROW_COUNT;
    RETURN v_reclaimed;
END;
$$;


ALTER FUNCTION processing.reclaim_stale_work(p_timeout_minutes integer) OWNER TO sfloess;

--
-- Name: worker_heartbeat(text, bigint); Type: FUNCTION; Schema: processing; Owner: sfloess
--

CREATE FUNCTION processing.worker_heartbeat(p_worker_id text, p_current_task_id bigint DEFAULT NULL::bigint) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    UPDATE processing.workers
    SET last_heartbeat = NOW(),
        current_task_id = p_current_task_id
    WHERE worker_id = p_worker_id;
END;
$$;


ALTER FUNCTION processing.worker_heartbeat(p_worker_id text, p_current_task_id bigint) OWNER TO sfloess;

--
-- Name: cleanup_request_history(); Type: FUNCTION; Schema: public; Owner: sfloess
--

CREATE FUNCTION public.cleanup_request_history() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_delete_count INTEGER;
    v_retry_count INTEGER := 0;
    v_max_retries INTEGER := 3;
    v_row_count INTEGER;
    v_lock_acquired BOOLEAN;
BEGIN
    -- CRITICAL FIX: Acquire advisory lock FIRST, before any checks or deletes
    -- This ensures we NEVER delete rows while monitor is reading
    -- Lock key: hashtext('request_history_read') - shared with continual-learning-monitor.js
    SELECT pg_try_advisory_lock(hashtext('request_history_read')) INTO v_lock_acquired;

    IF NOT v_lock_acquired THEN
        -- Monitor is reading, skip cleanup to avoid race condition
        RAISE NOTICE 'cleanup_request_history: skipping cleanup (monitor is reading)';
        RETURN NEW;
    END IF;

    BEGIN
        -- Circuit breaker: Check current row count before attempting cleanup
        -- NOW safe because we hold the lock
        SELECT COUNT(*) INTO v_row_count
        FROM learning.request_history;

        -- Only cleanup if we're actually over the threshold (1000 rows)
        IF v_row_count <= 1000 THEN
            -- Release lock before returning
            PERFORM pg_advisory_unlock(hashtext('request_history_read'));
            RETURN NEW;
        END IF;

        -- Retry loop with exponential backoff protection
        LOOP
            BEGIN
                -- Delete excess rows beyond 1000 limit
                DELETE FROM learning.request_history
                WHERE id IN (
                    SELECT id FROM learning.request_history
                    ORDER BY timestamp DESC
                    OFFSET 1000
                );

                -- Get number of rows deleted
                GET DIAGNOSTICS v_delete_count = ROW_COUNT;

                -- Exit loop on success
                EXIT;

            EXCEPTION
                WHEN OTHERS THEN
                    v_retry_count := v_retry_count + 1;

                    -- Circuit breaker: Stop after max retries to prevent infinite loop
                    IF v_retry_count >= v_max_retries THEN
                        -- Log the failure but don't block the INSERT
                        RAISE WARNING 'cleanup_request_history failed after % retries: %', v_max_retries, SQLERRM;
                        EXIT;
                    END IF;

                    -- Brief pause before retry (PostgreSQL pg_sleep requires seconds)
                    PERFORM pg_sleep(0.1 * v_retry_count);  -- 100ms, 200ms, 300ms
            END;
        END LOOP;

    EXCEPTION
        WHEN OTHERS THEN
            -- Release lock even on error
            PERFORM pg_advisory_unlock(hashtext('request_history_read'));
            RAISE;
    END;

    -- Release advisory lock
    PERFORM pg_advisory_unlock(hashtext('request_history_read'));

    RETURN NEW;
END;
$$;


ALTER FUNCTION public.cleanup_request_history() OWNER TO sfloess;

--
-- Name: get_eligible_models(); Type: FUNCTION; Schema: public; Owner: sfloess
--

CREATE FUNCTION public.get_eligible_models() RETURNS TABLE(eligible_models text[], excluded_models text[], forced_models text[], quota_enforced boolean)
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_window_size INTEGER := 20; -- from CONFIG.WINDOW_SIZE
    v_total_count INTEGER;
    v_eligible TEXT[] := '{}';
    v_excluded TEXT[] := '{}';
    v_forced TEXT[] := '{}';
    v_quota_enforced BOOLEAN := FALSE;
    rec RECORD;
BEGIN
    -- Get total count of recent requests
    SELECT COUNT(*) INTO v_total_count
    FROM (
        SELECT model
        FROM learning.request_history
        ORDER BY timestamp DESC
        LIMIT v_window_size
    ) recent;

    -- If no history, return all enabled models
    IF v_total_count = 0 THEN
        SELECT ARRAY_AGG(model) INTO v_eligible
        FROM learning.model_quotas
        WHERE enabled = TRUE;

        RETURN QUERY SELECT v_eligible, v_excluded, v_forced, v_quota_enforced;
        RETURN;
    END IF;

    -- Check each model against quotas
    FOR rec IN
        SELECT
            mq.model,
            COALESCE(mc.request_count, 0) AS request_count,
            (COALESCE(mc.request_count, 0)::REAL / v_total_count::REAL * 100.0) AS usage_pct,
            mq.floor_pct,
            mq.ceiling_pct,
            mq.enabled
        FROM learning.model_quotas mq
        LEFT JOIN (
            SELECT model, COUNT(*) AS request_count
            FROM (
                -- FIXED: Removed DISTINCT to avoid ORDER BY error
                SELECT model
                FROM learning.request_history
                ORDER BY timestamp DESC
                LIMIT v_window_size
            ) recent_requests
            GROUP BY model
        ) mc ON mq.model = mc.model
        WHERE mq.enabled = TRUE
    LOOP
        -- Ceiling check: Exclude if > ceiling_pct
        IF rec.usage_pct > rec.ceiling_pct THEN
            v_excluded := array_append(v_excluded, rec.model);
            v_quota_enforced := TRUE;
            CONTINUE;
        END IF;

        -- Floor check: Force include if < floor_pct
        IF rec.usage_pct < rec.floor_pct THEN
            v_forced := array_append(v_forced, rec.model);
            v_quota_enforced := TRUE;
        END IF;

        -- Add to eligible pool
        v_eligible := array_append(v_eligible, rec.model);
    END LOOP;

    RETURN QUERY SELECT v_eligible, v_excluded, v_forced, v_quota_enforced;
END;
$$;


ALTER FUNCTION public.get_eligible_models() OWNER TO sfloess;

--
-- Name: upsert_chunk_with_dedup(text, character varying, jsonb); Type: FUNCTION; Schema: public; Owner: sfloess
--

CREATE FUNCTION public.upsert_chunk_with_dedup(p_chunk_text text, p_content_hash character varying, p_metadata jsonb) RETURNS TABLE(id integer, access_count integer, is_new boolean)
    LANGUAGE plpgsql
    AS $$
BEGIN
  RETURN QUERY
  INSERT INTO learning.research_chunks (chunk_text, content_hash, metadata, access_count, last_accessed)
  VALUES (p_chunk_text, p_content_hash, p_metadata, 1, NOW())
  ON CONFLICT (content_hash) DO UPDATE SET
    access_count = learning.research_chunks.access_count + 1,
    last_accessed = NOW()
  RETURNING learning.research_chunks.id, 
            learning.research_chunks.access_count,
            (learning.research_chunks.access_count = 1) as is_new;
END;
$$;


ALTER FUNCTION public.upsert_chunk_with_dedup(p_chunk_text text, p_content_hash character varying, p_metadata jsonb) OWNER TO sfloess;

--
-- Name: upsert_chunk_with_dedup(text, integer, text, character varying); Type: FUNCTION; Schema: public; Owner: sfloess
--

CREATE FUNCTION public.upsert_chunk_with_dedup(p_doc_id text, p_chunk_index integer, p_chunk_text text, p_content_hash character varying) RETURNS TABLE(id integer, access_count integer, is_new boolean)
    LANGUAGE plpgsql
    AS $$
BEGIN
  RETURN QUERY
  INSERT INTO learning.research_chunks (doc_id, chunk_index, chunk_text, content_hash, access_count, last_accessed)
  VALUES (p_doc_id, p_chunk_index, p_chunk_text, p_content_hash, 1, NOW())
  ON CONFLICT (content_hash) WHERE content_hash IS NOT NULL DO UPDATE SET
    access_count = learning.research_chunks.access_count + 1,
    last_accessed = NOW()
  RETURNING learning.research_chunks.id, 
            learning.research_chunks.access_count,
            (learning.research_chunks.access_count = 1) as is_new;
END;
$$;


ALTER FUNCTION public.upsert_chunk_with_dedup(p_doc_id text, p_chunk_index integer, p_chunk_text text, p_content_hash character varying) OWNER TO sfloess;

--
-- Name: add_task(integer, character varying, jsonb); Type: FUNCTION; Schema: queue; Owner: claude
--

CREATE FUNCTION queue.add_task(p_priority integer, p_type character varying, p_payload jsonb) RETURNS integer
    LANGUAGE plpgsql
    AS $$
            DECLARE
                task_id INT;
            BEGIN
                INSERT INTO queue.tasks (priority, task_type, payload)
                VALUES (p_priority, p_type, p_payload)
                RETURNING id INTO task_id;
                RETURN task_id;
            END;
            $$;


ALTER FUNCTION queue.add_task(p_priority integer, p_type character varying, p_payload jsonb) OWNER TO claude;

--
-- Name: claim_next_task(character varying); Type: FUNCTION; Schema: queue; Owner: claude
--

CREATE FUNCTION queue.claim_next_task(p_worker_id character varying) RETURNS TABLE(task_id integer, task_priority integer, task_type character varying, task_payload jsonb, task_created_at timestamp with time zone)
    LANGUAGE plpgsql
    AS $$
            BEGIN
                RETURN QUERY
                WITH claimed AS (
                    UPDATE queue.tasks
                    SET status = 'in_progress',
                        worker_id = p_worker_id,
                        claimed_at = NOW()
                    WHERE queue.tasks.id IN (
                        SELECT t.id
                        FROM queue.tasks t
                        WHERE t.status = 'pending'
                        ORDER BY t.priority DESC, t.created_at ASC
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                    )
                    RETURNING *
                )
                SELECT c.id, c.priority, c.task_type, c.payload, c.created_at
                FROM claimed c;
            END;
            $$;


ALTER FUNCTION queue.claim_next_task(p_worker_id character varying) OWNER TO claude;

--
-- Name: complete_task(integer, text); Type: FUNCTION; Schema: queue; Owner: claude
--

CREATE FUNCTION queue.complete_task(p_task_id integer, p_error text DEFAULT NULL::text) RETURNS void
    LANGUAGE plpgsql
    AS $$
            BEGIN
                IF p_error IS NULL THEN
                    UPDATE queue.tasks
                    SET status = 'completed',
                        completed_at = NOW()
                    WHERE id = p_task_id;
                ELSE
                    UPDATE queue.tasks
                    SET status = 'failed',
                        completed_at = NOW(),
                        error_message = p_error
                    WHERE id = p_task_id;
                END IF;
            END;
            $$;


ALTER FUNCTION queue.complete_task(p_task_id integer, p_error text) OWNER TO claude;

--
-- Name: on_task_complete(); Type: FUNCTION; Schema: queue; Owner: claude
--

CREATE FUNCTION queue.on_task_complete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  -- Only trigger when task moves to 'completed' status
  IF NEW.status = 'completed' AND OLD.status = 'in_progress' THEN
    
    -- Add 2 new tasks of the same type with higher priority
    INSERT INTO queue.tasks (priority, task_type, payload)
    VALUES 
      (NEW.priority, NEW.task_type, 
       jsonb_set(NEW.payload, '{category}', to_jsonb(NEW.payload->>'category' || '_copy1'))),
      (NEW.priority, NEW.task_type,
       jsonb_set(NEW.payload, '{category}', to_jsonb(NEW.payload->>'category' || '_copy2')));
    
  END IF;
  
  RETURN NEW;
END;
$$;


ALTER FUNCTION queue.on_task_complete() OWNER TO claude;

--
-- Name: find_relevant_learnings(public.vector, character varying, numeric, integer); Type: FUNCTION; Schema: workflows; Owner: sfloess
--

CREATE FUNCTION workflows.find_relevant_learnings(query_embedding public.vector, workflow_filter character varying DEFAULT NULL::character varying, similarity_threshold numeric DEFAULT 0.7, max_results integer DEFAULT 10) RETURNS TABLE(learning_id uuid, workflow_name character varying, learning_type character varying, title character varying, description text, similarity numeric, impact_score numeric, verified boolean)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        l.learning_id,
        l.workflow_name,
        l.learning_type,
        l.title,
        l.description,
        1 - (l.embedding <=> query_embedding) as similarity,
        l.impact_score,
        l.verified
    FROM workflows.learnings l
    WHERE (workflow_filter IS NULL OR l.workflow_name = workflow_filter)
        AND 1 - (l.embedding <=> query_embedding) >= similarity_threshold
    ORDER BY l.embedding <=> query_embedding
    LIMIT max_results;
END;
$$;


ALTER FUNCTION workflows.find_relevant_learnings(query_embedding public.vector, workflow_filter character varying, similarity_threshold numeric, max_results integer) OWNER TO sfloess;

--
-- Name: find_similar_executions(public.vector, numeric, integer); Type: FUNCTION; Schema: workflows; Owner: sfloess
--

CREATE FUNCTION workflows.find_similar_executions(query_embedding public.vector, similarity_threshold numeric DEFAULT 0.7, max_results integer DEFAULT 10) RETURNS TABLE(execution_id uuid, workflow_name character varying, similarity numeric, input_prompt text, output_result text, final_confidence numeric, completed_at timestamp with time zone)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.execution_id,
        e.workflow_name,
        1 - (ee.input_embedding <=> query_embedding) as similarity,
        e.input_prompt,
        e.output_result,
        e.final_confidence,
        e.completed_at
    FROM workflows.execution_embeddings ee
    JOIN workflows.executions e ON ee.execution_id = e.execution_id
    WHERE 1 - (ee.input_embedding <=> query_embedding) >= similarity_threshold
        AND e.status = 'completed'
    ORDER BY ee.input_embedding <=> query_embedding
    LIMIT max_results;
END;
$$;


ALTER FUNCTION workflows.find_similar_executions(query_embedding public.vector, similarity_threshold numeric, max_results integer) OWNER TO sfloess;

--
-- Name: get_best_combination(character varying, integer); Type: FUNCTION; Schema: workflows; Owner: sfloess
--

CREATE FUNCTION workflows.get_best_combination(p_workflow_name character varying, min_executions integer DEFAULT 3) RETURNS TABLE(worker_models character varying[], arbiter_model character varying, avg_quality numeric, success_rate numeric, avg_cost_usd numeric)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        mc.worker_models,
        mc.arbiter_model,
        mc.avg_quality,
        mc.success_rate,
        mc.avg_cost_usd
    FROM workflows.model_combinations mc
    WHERE mc.workflow_name = p_workflow_name
        AND mc.num_executions >= min_executions
    ORDER BY mc.avg_quality DESC, mc.success_rate DESC, mc.avg_cost_usd ASC
    LIMIT 1;
END;
$$;


ALTER FUNCTION workflows.get_best_combination(p_workflow_name character varying, min_executions integer) OWNER TO sfloess;

--
-- Name: refresh_views(); Type: FUNCTION; Schema: workflows; Owner: sfloess
--

CREATE FUNCTION workflows.refresh_views() RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY workflows.summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY workflows.model_performance;
END;
$$;


ALTER FUNCTION workflows.refresh_views() OWNER TO sfloess;

--
-- Name: update_arbiter_duration(); Type: FUNCTION; Schema: workflows; Owner: sfloess
--

CREATE FUNCTION workflows.update_arbiter_duration() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.completed_at IS NOT NULL THEN
        NEW.duration_ms := EXTRACT(EPOCH FROM (NEW.completed_at - NEW.started_at)) * 1000;
    END IF;
    RETURN NEW;
END;
$$;


ALTER FUNCTION workflows.update_arbiter_duration() OWNER TO sfloess;

--
-- Name: update_execution_summary(); Type: FUNCTION; Schema: workflows; Owner: sfloess
--

CREATE FUNCTION workflows.update_execution_summary() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.status IN ('completed', 'failed') AND OLD.status NOT IN ('completed', 'failed') THEN
        -- Calculate duration
        NEW.duration_ms := EXTRACT(EPOCH FROM (NEW.completed_at - NEW.started_at)) * 1000;

        -- Update worker counts
        SELECT
            COUNT(*),
            COUNT(*) FILTER (WHERE status = 'completed'),
            COUNT(*) FILTER (WHERE status = 'failed')
        INTO NEW.total_workers, NEW.successful_workers, NEW.failed_workers
        FROM workflows.worker_results
        WHERE execution_id = NEW.execution_id;
    END IF;

    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION workflows.update_execution_summary() OWNER TO sfloess;

--
-- Name: update_phase_duration(); Type: FUNCTION; Schema: workflows; Owner: sfloess
--

CREATE FUNCTION workflows.update_phase_duration() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.status IN ('completed', 'failed', 'skipped') AND NEW.completed_at IS NOT NULL THEN
        NEW.duration_ms := EXTRACT(EPOCH FROM (NEW.completed_at - NEW.started_at)) * 1000;
    END IF;
    RETURN NEW;
END;
$$;


ALTER FUNCTION workflows.update_phase_duration() OWNER TO sfloess;

--
-- Name: update_worker_duration(); Type: FUNCTION; Schema: workflows; Owner: sfloess
--

CREATE FUNCTION workflows.update_worker_duration() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.status IN ('completed', 'failed', 'timeout') AND NEW.completed_at IS NOT NULL THEN
        NEW.duration_ms := EXTRACT(EPOCH FROM (NEW.completed_at - NEW.started_at)) * 1000;
    END IF;
    RETURN NEW;
END;
$$;


ALTER FUNCTION workflows.update_worker_duration() OWNER TO sfloess;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: background_tasks; Type: TABLE; Schema: admin; Owner: claude
--

CREATE TABLE admin.background_tasks (
    job_id uuid DEFAULT gen_random_uuid() NOT NULL,
    task_type character varying(50) NOT NULL,
    status character varying(20) NOT NULL,
    started_at timestamp without time zone DEFAULT now(),
    completed_at timestamp without time zone,
    error_message text,
    result_summary text
);


ALTER TABLE admin.background_tasks OWNER TO claude;

--
-- Name: config; Type: TABLE; Schema: admin; Owner: sfloess
--

CREATE TABLE admin.config (
    key text NOT NULL,
    value text NOT NULL,
    description text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE admin.config OWNER TO sfloess;

--
-- Name: api_keys; Type: TABLE; Schema: auth; Owner: sfloess
--

CREATE TABLE auth.api_keys (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    key_prefix character varying(8) NOT NULL,
    key_hash text NOT NULL,
    scopes text[] DEFAULT '{}'::text[] NOT NULL,
    rate_limit_per_minute integer DEFAULT 100 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_used_at timestamp with time zone,
    expires_at timestamp with time zone,
    metadata jsonb DEFAULT '{}'::jsonb
);


ALTER TABLE auth.api_keys OWNER TO sfloess;

--
-- Name: secrets; Type: TABLE; Schema: auth; Owner: sfloess
--

CREATE TABLE auth.secrets (
    key text NOT NULL,
    value text NOT NULL,
    description text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE auth.secrets OWNER TO sfloess;

--
-- Name: api_calls; Type: TABLE; Schema: auto_storage; Owner: claude
--

CREATE TABLE auto_storage.api_calls (
    id integer NOT NULL,
    worker_id character varying(255),
    model character varying(255),
    provider character varying(100),
    conversation_chunk text,
    chunk_index integer DEFAULT 0,
    prompt_tokens integer,
    completion_tokens integer,
    cost_usd numeric(10,6),
    latency_ms integer,
    created_at timestamp without time zone DEFAULT now(),
    request_method character varying(10) DEFAULT 'POST'::character varying,
    error_message text,
    request_timestamp timestamp without time zone
);


ALTER TABLE auto_storage.api_calls OWNER TO claude;

--
-- Name: api_calls_id_seq; Type: SEQUENCE; Schema: auto_storage; Owner: claude
--

CREATE SEQUENCE auto_storage.api_calls_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE auto_storage.api_calls_id_seq OWNER TO claude;

--
-- Name: api_calls_id_seq; Type: SEQUENCE OWNED BY; Schema: auto_storage; Owner: claude
--

ALTER SEQUENCE auto_storage.api_calls_id_seq OWNED BY auto_storage.api_calls.id;


--
-- Name: api_keys; Type: TABLE; Schema: config; Owner: claude
--

CREATE TABLE config.api_keys (
    id integer NOT NULL,
    service text NOT NULL,
    key_name text NOT NULL,
    purpose text,
    tags jsonb DEFAULT '[]'::jsonb,
    encrypted_key text NOT NULL,
    encryption_method text DEFAULT 'base64'::text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_used timestamp with time zone,
    is_active boolean DEFAULT true,
    notes text
);


ALTER TABLE config.api_keys OWNER TO claude;

--
-- Name: api_keys_id_seq; Type: SEQUENCE; Schema: config; Owner: claude
--

CREATE SEQUENCE config.api_keys_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE config.api_keys_id_seq OWNER TO claude;

--
-- Name: api_keys_id_seq; Type: SEQUENCE OWNED BY; Schema: config; Owner: claude
--

ALTER SEQUENCE config.api_keys_id_seq OWNED BY config.api_keys.id;


--
-- Name: key_usage_log; Type: TABLE; Schema: config; Owner: claude
--

CREATE TABLE config.key_usage_log (
    id integer NOT NULL,
    key_id integer,
    task_type text,
    workflow text,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL,
    tokens_used integer,
    cost_usd numeric(10,6)
);


ALTER TABLE config.key_usage_log OWNER TO claude;

--
-- Name: key_usage_log_id_seq; Type: SEQUENCE; Schema: config; Owner: claude
--

CREATE SEQUENCE config.key_usage_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE config.key_usage_log_id_seq OWNER TO claude;

--
-- Name: key_usage_log_id_seq; Type: SEQUENCE OWNED BY; Schema: config; Owner: claude
--

ALTER SEQUENCE config.key_usage_log_id_seq OWNED BY config.key_usage_log.id;


--
-- Name: key_usage_stats; Type: VIEW; Schema: config; Owner: claude
--

CREATE VIEW config.key_usage_stats AS
 SELECT ak.key_name,
    ak.service,
    ak.purpose,
    count(kul.id) AS total_uses,
    sum(kul.tokens_used) AS total_tokens,
    sum(kul.cost_usd) AS total_cost,
    max(kul."timestamp") AS last_used
   FROM (config.api_keys ak
     LEFT JOIN config.key_usage_log kul ON ((ak.id = kul.key_id)))
  WHERE (ak.is_active = true)
  GROUP BY ak.id, ak.key_name, ak.service, ak.purpose
  ORDER BY (count(kul.id)) DESC;


ALTER VIEW config.key_usage_stats OWNER TO claude;

--
-- Name: entries; Type: TABLE; Schema: costs; Owner: sfloess
--

CREATE TABLE costs.entries (
    id integer NOT NULL,
    "timestamp" timestamp with time zone,
    model text,
    input_tokens integer,
    output_tokens integer,
    total_cost real
);


ALTER TABLE costs.entries OWNER TO sfloess;

--
-- Name: entries_id_seq; Type: SEQUENCE; Schema: costs; Owner: sfloess
--

CREATE SEQUENCE costs.entries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE costs.entries_id_seq OWNER TO sfloess;

--
-- Name: entries_id_seq; Type: SEQUENCE OWNED BY; Schema: costs; Owner: sfloess
--

ALTER SEQUENCE costs.entries_id_seq OWNED BY costs.entries.id;


--
-- Name: content_hashes; Type: TABLE; Schema: dedup; Owner: claude
--

CREATE TABLE dedup.content_hashes (
    hash character varying(64) NOT NULL,
    first_seen_id character varying(255) NOT NULL,
    content_preview text,
    content_length integer,
    seen_count integer DEFAULT 1,
    first_seen_at timestamp without time zone DEFAULT now(),
    last_seen_at timestamp without time zone DEFAULT now()
);


ALTER TABLE dedup.content_hashes OWNER TO claude;

--
-- Name: similar_pairs; Type: TABLE; Schema: dedup; Owner: claude
--

CREATE TABLE dedup.similar_pairs (
    id integer NOT NULL,
    hash1 character varying(64) NOT NULL,
    hash2 character varying(64) NOT NULL,
    similarity_score double precision NOT NULL,
    detected_at timestamp without time zone DEFAULT now()
);


ALTER TABLE dedup.similar_pairs OWNER TO claude;

--
-- Name: similar_pairs_id_seq; Type: SEQUENCE; Schema: dedup; Owner: claude
--

CREATE SEQUENCE dedup.similar_pairs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE dedup.similar_pairs_id_seq OWNER TO claude;

--
-- Name: similar_pairs_id_seq; Type: SEQUENCE OWNED BY; Schema: dedup; Owner: claude
--

ALTER SEQUENCE dedup.similar_pairs_id_seq OWNED BY dedup.similar_pairs.id;


--
-- Name: chunks; Type: TABLE; Schema: documents; Owner: sfloess
--

CREATE TABLE documents.chunks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    document_id uuid NOT NULL,
    chunk_index integer NOT NULL,
    content text NOT NULL,
    content_hash character varying(64) NOT NULL,
    embedding public.vector(768),
    page_number integer,
    bounding_box jsonb,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE documents.chunks OWNER TO sfloess;

--
-- Name: documents; Type: TABLE; Schema: documents; Owner: sfloess
--

CREATE TABLE documents.documents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    file_hash character varying(64) NOT NULL,
    file_name text NOT NULL,
    file_type character varying(50) NOT NULL,
    file_size_bytes bigint NOT NULL,
    mime_type character varying(100),
    source character varying(100),
    tags text[] DEFAULT '{}'::text[],
    metadata jsonb DEFAULT '{}'::jsonb,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    processing_started_at timestamp with time zone,
    processing_completed_at timestamp with time zone,
    error_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    content text,
    CONSTRAINT valid_completed_status CHECK ((((status)::text <> 'completed'::text) OR (processing_completed_at IS NOT NULL)))
);


ALTER TABLE documents.documents OWNER TO sfloess;

--
-- Name: processing_log; Type: TABLE; Schema: documents; Owner: sfloess
--

CREATE TABLE documents.processing_log (
    id bigint NOT NULL,
    document_id uuid NOT NULL,
    stage character varying(50) NOT NULL,
    status character varying(20) NOT NULL,
    duration_ms integer,
    error_message text,
    chunks_created integer,
    embeddings_generated integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE documents.processing_log OWNER TO sfloess;

--
-- Name: processing_log_id_seq; Type: SEQUENCE; Schema: documents; Owner: sfloess
--

CREATE SEQUENCE documents.processing_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE documents.processing_log_id_seq OWNER TO sfloess;

--
-- Name: processing_log_id_seq; Type: SEQUENCE OWNED BY; Schema: documents; Owner: sfloess
--

ALTER SEQUENCE documents.processing_log_id_seq OWNED BY documents.processing_log.id;


--
-- Name: benchmarks; Type: TABLE; Schema: evaluation; Owner: sfloess
--

CREATE TABLE evaluation.benchmarks (
    id integer NOT NULL,
    task_type character varying(50) NOT NULL,
    question text NOT NULL,
    ground_truth jsonb NOT NULL,
    difficulty character varying(20) NOT NULL,
    category character varying(100),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT benchmarks_difficulty_check CHECK (((difficulty)::text = ANY (ARRAY[('easy'::character varying)::text, ('medium'::character varying)::text, ('hard'::character varying)::text])))
);


ALTER TABLE evaluation.benchmarks OWNER TO sfloess;

--
-- Name: TABLE benchmarks; Type: COMMENT; Schema: evaluation; Owner: sfloess
--

COMMENT ON TABLE evaluation.benchmarks IS 'Benchmark questions with ground truth answers across 7 task types (1000 total)';


--
-- Name: benchmarks_id_seq; Type: SEQUENCE; Schema: evaluation; Owner: sfloess
--

CREATE SEQUENCE evaluation.benchmarks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE evaluation.benchmarks_id_seq OWNER TO sfloess;

--
-- Name: benchmarks_id_seq; Type: SEQUENCE OWNED BY; Schema: evaluation; Owner: sfloess
--

ALTER SEQUENCE evaluation.benchmarks_id_seq OWNED BY evaluation.benchmarks.id;


--
-- Name: results; Type: TABLE; Schema: evaluation; Owner: sfloess
--

CREATE TABLE evaluation.results (
    id integer NOT NULL,
    benchmark_id integer NOT NULL,
    model character varying(100) NOT NULL,
    worker_id character varying(100),
    answer text NOT NULL,
    confidence double precision,
    correctness_score double precision,
    robustness_score double precision,
    generalization_score double precision,
    bias_resistance_score double precision,
    reproducibility_score double precision,
    overall_score double precision,
    evaluation_notes jsonb,
    input_tokens integer,
    output_tokens integer,
    cost_usd numeric(10,6),
    execution_time_ms integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT results_bias_resistance_score_check CHECK (((bias_resistance_score >= (0.0)::double precision) AND (bias_resistance_score <= (1.0)::double precision))),
    CONSTRAINT results_confidence_check CHECK (((confidence >= (0.0)::double precision) AND (confidence <= (1.0)::double precision))),
    CONSTRAINT results_correctness_score_check CHECK (((correctness_score >= (0.0)::double precision) AND (correctness_score <= (1.0)::double precision))),
    CONSTRAINT results_generalization_score_check CHECK (((generalization_score >= (0.0)::double precision) AND (generalization_score <= (1.0)::double precision))),
    CONSTRAINT results_reproducibility_score_check CHECK (((reproducibility_score >= (0.0)::double precision) AND (reproducibility_score <= (1.0)::double precision))),
    CONSTRAINT results_robustness_score_check CHECK (((robustness_score >= (0.0)::double precision) AND (robustness_score <= (1.0)::double precision)))
);


ALTER TABLE evaluation.results OWNER TO sfloess;

--
-- Name: TABLE results; Type: COMMENT; Schema: evaluation; Owner: sfloess
--

COMMENT ON TABLE evaluation.results IS 'Evaluation results from models attempting benchmark questions';


--
-- Name: COLUMN results.correctness_score; Type: COMMENT; Schema: evaluation; Owner: sfloess
--

COMMENT ON COLUMN evaluation.results.correctness_score IS 'Score 0-1 for answer correctness (35% weight)';


--
-- Name: COLUMN results.robustness_score; Type: COMMENT; Schema: evaluation; Owner: sfloess
--

COMMENT ON COLUMN evaluation.results.robustness_score IS 'Score 0-1 for answer robustness (20% weight)';


--
-- Name: COLUMN results.generalization_score; Type: COMMENT; Schema: evaluation; Owner: sfloess
--

COMMENT ON COLUMN evaluation.results.generalization_score IS 'Score 0-1 for answer generalization (20% weight)';


--
-- Name: COLUMN results.bias_resistance_score; Type: COMMENT; Schema: evaluation; Owner: sfloess
--

COMMENT ON COLUMN evaluation.results.bias_resistance_score IS 'Score 0-1 for resistance to bias (15% weight)';


--
-- Name: COLUMN results.reproducibility_score; Type: COMMENT; Schema: evaluation; Owner: sfloess
--

COMMENT ON COLUMN evaluation.results.reproducibility_score IS 'Score 0-1 for reproducibility (10% weight)';


--
-- Name: model_performance; Type: MATERIALIZED VIEW; Schema: evaluation; Owner: sfloess
--

CREATE MATERIALIZED VIEW evaluation.model_performance AS
 SELECT model,
    count(*) AS evaluations,
    round((avg(correctness_score))::numeric, 3) AS avg_correctness,
    round((avg(robustness_score))::numeric, 3) AS avg_robustness,
    round((avg(generalization_score))::numeric, 3) AS avg_generalization,
    round((avg(bias_resistance_score))::numeric, 3) AS avg_bias_resistance,
    round((avg(reproducibility_score))::numeric, 3) AS avg_reproducibility,
    round((avg(overall_score))::numeric, 3) AS avg_overall,
    round((avg(confidence))::numeric, 3) AS avg_confidence,
    round((avg((execution_time_ms)::double precision))::numeric, 1) AS avg_execution_ms,
    round(sum(cost_usd), 6) AS total_cost_usd
   FROM evaluation.results
  GROUP BY model
  ORDER BY (round((avg(overall_score))::numeric, 3)) DESC
  WITH NO DATA;


ALTER MATERIALIZED VIEW evaluation.model_performance OWNER TO sfloess;

--
-- Name: results_id_seq; Type: SEQUENCE; Schema: evaluation; Owner: sfloess
--

CREATE SEQUENCE evaluation.results_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE evaluation.results_id_seq OWNER TO sfloess;

--
-- Name: results_id_seq; Type: SEQUENCE OWNED BY; Schema: evaluation; Owner: sfloess
--

ALTER SEQUENCE evaluation.results_id_seq OWNED BY evaluation.results.id;


--
-- Name: task_model_performance; Type: MATERIALIZED VIEW; Schema: evaluation; Owner: sfloess
--

CREATE MATERIALIZED VIEW evaluation.task_model_performance AS
 SELECT b.task_type,
    r.model,
    count(*) AS evaluations,
    round((avg(r.correctness_score))::numeric, 3) AS avg_correctness,
    round((avg(r.overall_score))::numeric, 3) AS avg_overall,
    round((avg((r.execution_time_ms)::double precision))::numeric, 1) AS avg_execution_ms
   FROM (evaluation.results r
     JOIN evaluation.benchmarks b ON ((r.benchmark_id = b.id)))
  GROUP BY b.task_type, r.model
  ORDER BY b.task_type, r.model
  WITH NO DATA;


ALTER MATERIALIZED VIEW evaluation.task_model_performance OWNER TO sfloess;

--
-- Name: registry; Type: TABLE; Schema: experiments; Owner: sfloess
--

CREATE TABLE experiments.registry (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    hypothesis text NOT NULL,
    metric character varying(255) NOT NULL,
    success_criteria text NOT NULL,
    status character varying(50) DEFAULT 'draft'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT registry_status_check CHECK (((status)::text = ANY (ARRAY[('draft'::character varying)::text, ('active'::character varying)::text, ('completed'::character varying)::text, ('abandoned'::character varying)::text])))
);


ALTER TABLE experiments.registry OWNER TO sfloess;

--
-- Name: TABLE registry; Type: COMMENT; Schema: experiments; Owner: sfloess
--

COMMENT ON TABLE experiments.registry IS 'Central registry of experiments with hypotheses and success criteria';


--
-- Name: COLUMN registry.name; Type: COMMENT; Schema: experiments; Owner: sfloess
--

COMMENT ON COLUMN experiments.registry.name IS 'Unique human-readable experiment name';


--
-- Name: COLUMN registry.hypothesis; Type: COMMENT; Schema: experiments; Owner: sfloess
--

COMMENT ON COLUMN experiments.registry.hypothesis IS 'What we expect to observe (falsifiable statement)';


--
-- Name: COLUMN registry.metric; Type: COMMENT; Schema: experiments; Owner: sfloess
--

COMMENT ON COLUMN experiments.registry.metric IS 'The metric being measured (e.g. p95_latency_ms, success_rate)';


--
-- Name: COLUMN registry.success_criteria; Type: COMMENT; Schema: experiments; Owner: sfloess
--

COMMENT ON COLUMN experiments.registry.success_criteria IS 'Condition that confirms the hypothesis (e.g. ">10% improvement")';


--
-- Name: COLUMN registry.status; Type: COMMENT; Schema: experiments; Owner: sfloess
--

COMMENT ON COLUMN experiments.registry.status IS 'Lifecycle: draft -> active -> completed|abandoned';


--
-- Name: registry_id_seq; Type: SEQUENCE; Schema: experiments; Owner: sfloess
--

CREATE SEQUENCE experiments.registry_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE experiments.registry_id_seq OWNER TO sfloess;

--
-- Name: registry_id_seq; Type: SEQUENCE OWNED BY; Schema: experiments; Owner: sfloess
--

ALTER SEQUENCE experiments.registry_id_seq OWNED BY experiments.registry.id;


--
-- Name: runs; Type: TABLE; Schema: experiments; Owner: sfloess
--

CREATE TABLE experiments.runs (
    id integer NOT NULL,
    experiment_id integer NOT NULL,
    baseline_config jsonb DEFAULT '{}'::jsonb NOT NULL,
    treatment_config jsonb DEFAULT '{}'::jsonb NOT NULL,
    result jsonb,
    verdict character varying(50),
    run_date timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT runs_verdict_check CHECK (((verdict IS NULL) OR ((verdict)::text = ANY (ARRAY[('confirmed'::character varying)::text, ('refuted'::character varying)::text, ('inconclusive'::character varying)::text]))))
);


ALTER TABLE experiments.runs OWNER TO sfloess;

--
-- Name: TABLE runs; Type: COMMENT; Schema: experiments; Owner: sfloess
--

COMMENT ON TABLE experiments.runs IS 'Individual runs of an experiment comparing baseline to treatment configurations';


--
-- Name: COLUMN runs.baseline_config; Type: COMMENT; Schema: experiments; Owner: sfloess
--

COMMENT ON COLUMN experiments.runs.baseline_config IS 'JSON config for the control group';


--
-- Name: COLUMN runs.treatment_config; Type: COMMENT; Schema: experiments; Owner: sfloess
--

COMMENT ON COLUMN experiments.runs.treatment_config IS 'JSON config for the experimental group';


--
-- Name: COLUMN runs.result; Type: COMMENT; Schema: experiments; Owner: sfloess
--

COMMENT ON COLUMN experiments.runs.result IS 'JSON with measured outcomes (metrics, durations, scores)';


--
-- Name: COLUMN runs.verdict; Type: COMMENT; Schema: experiments; Owner: sfloess
--

COMMENT ON COLUMN experiments.runs.verdict IS 'NULL while pending; confirmed/refuted/inconclusive after analysis';


--
-- Name: runs_id_seq; Type: SEQUENCE; Schema: experiments; Owner: sfloess
--

CREATE SEQUENCE experiments.runs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE experiments.runs_id_seq OWNER TO sfloess;

--
-- Name: runs_id_seq; Type: SEQUENCE OWNED BY; Schema: experiments; Owner: sfloess
--

ALTER SEQUENCE experiments.runs_id_seq OWNED BY experiments.runs.id;


--
-- Name: command_results; Type: TABLE; Schema: fleet; Owner: claude
--

CREATE TABLE fleet.command_results (
    id integer NOT NULL,
    command_id character varying(255) NOT NULL,
    command text,
    workers text[],
    results jsonb,
    created_at timestamp without time zone
);


ALTER TABLE fleet.command_results OWNER TO claude;

--
-- Name: command_results_id_seq; Type: SEQUENCE; Schema: fleet; Owner: claude
--

CREATE SEQUENCE fleet.command_results_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE fleet.command_results_id_seq OWNER TO claude;

--
-- Name: command_results_id_seq; Type: SEQUENCE OWNED BY; Schema: fleet; Owner: claude
--

ALTER SEQUENCE fleet.command_results_id_seq OWNED BY fleet.command_results.id;


--
-- Name: tasks; Type: TABLE; Schema: fleet; Owner: claude
--

CREATE TABLE fleet.tasks (
    id integer NOT NULL,
    task_id character varying(255) NOT NULL,
    prompt text,
    model character varying(255),
    worker character varying(255),
    status character varying(20) DEFAULT 'pending'::character varying,
    result text,
    error text,
    timeout_ms integer,
    created_at timestamp without time zone,
    started_at timestamp without time zone,
    completed_at timestamp without time zone
);


ALTER TABLE fleet.tasks OWNER TO claude;

--
-- Name: tasks_id_seq; Type: SEQUENCE; Schema: fleet; Owner: claude
--

CREATE SEQUENCE fleet.tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE fleet.tasks_id_seq OWNER TO claude;

--
-- Name: tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: fleet; Owner: claude
--

ALTER SEQUENCE fleet.tasks_id_seq OWNED BY fleet.tasks.id;


--
-- Name: workers; Type: TABLE; Schema: fleet; Owner: claude
--

CREATE TABLE fleet.workers (
    id integer NOT NULL,
    hostname character varying(255) NOT NULL,
    ip_address character varying(45),
    cpu_cores integer,
    ram_gb numeric(6,2),
    architecture character varying(50),
    roles text[],
    capabilities text[],
    status character varying(20) DEFAULT 'active'::character varying,
    last_seen timestamp without time zone,
    created_at timestamp without time zone DEFAULT now(),
    last_heartbeat timestamp without time zone,
    last_failure timestamp without time zone,
    last_failure_reason text,
    failure_count integer DEFAULT 0
);


ALTER TABLE fleet.workers OWNER TO claude;

--
-- Name: workers_id_seq; Type: SEQUENCE; Schema: fleet; Owner: claude
--

CREATE SEQUENCE fleet.workers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE fleet.workers_id_seq OWNER TO claude;

--
-- Name: workers_id_seq; Type: SEQUENCE OWNED BY; Schema: fleet; Owner: claude
--

ALTER SEQUENCE fleet.workers_id_seq OWNED BY fleet.workers.id;


--
-- Name: workflows; Type: TABLE; Schema: fleet; Owner: claude
--

CREATE TABLE fleet.workflows (
    id integer NOT NULL,
    workflow_id character varying(255) NOT NULL,
    workflow_name character varying(255),
    args jsonb,
    description text,
    status character varying(20) DEFAULT 'pending'::character varying,
    result text,
    error text,
    created_at timestamp without time zone,
    started_at timestamp without time zone,
    completed_at timestamp without time zone
);


ALTER TABLE fleet.workflows OWNER TO claude;

--
-- Name: workflows_id_seq; Type: SEQUENCE; Schema: fleet; Owner: claude
--

CREATE SEQUENCE fleet.workflows_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE fleet.workflows_id_seq OWNER TO claude;

--
-- Name: workflows_id_seq; Type: SEQUENCE OWNED BY; Schema: fleet; Owner: claude
--

ALTER SEQUENCE fleet.workflows_id_seq OWNED BY fleet.workflows.id;


--
-- Name: best_solutions; Type: TABLE; Schema: ga; Owner: claude
--

CREATE TABLE ga.best_solutions (
    use_case text NOT NULL,
    chromosome jsonb NOT NULL,
    fitness double precision,
    fitness_details jsonb,
    generation_found integer,
    validation_fitness double precision,
    deployed_at timestamp without time zone,
    notes text
);


ALTER TABLE ga.best_solutions OWNER TO claude;

--
-- Name: convergence_metrics; Type: TABLE; Schema: ga; Owner: claude
--

CREATE TABLE ga.convergence_metrics (
    id integer NOT NULL,
    use_case text NOT NULL,
    generation integer NOT NULL,
    island_id integer,
    best_fitness double precision,
    avg_fitness double precision,
    diversity double precision,
    recorded_at timestamp without time zone DEFAULT now()
);


ALTER TABLE ga.convergence_metrics OWNER TO claude;

--
-- Name: convergence_metrics_id_seq; Type: SEQUENCE; Schema: ga; Owner: claude
--

CREATE SEQUENCE ga.convergence_metrics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE ga.convergence_metrics_id_seq OWNER TO claude;

--
-- Name: convergence_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: ga; Owner: claude
--

ALTER SEQUENCE ga.convergence_metrics_id_seq OWNED BY ga.convergence_metrics.id;


--
-- Name: migration_log; Type: TABLE; Schema: ga; Owner: claude
--

CREATE TABLE ga.migration_log (
    id integer NOT NULL,
    use_case text NOT NULL,
    generation integer NOT NULL,
    from_island integer,
    to_island integer,
    chromosome jsonb,
    fitness double precision,
    migrated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE ga.migration_log OWNER TO claude;

--
-- Name: migration_log_id_seq; Type: SEQUENCE; Schema: ga; Owner: claude
--

CREATE SEQUENCE ga.migration_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE ga.migration_log_id_seq OWNER TO claude;

--
-- Name: migration_log_id_seq; Type: SEQUENCE OWNED BY; Schema: ga; Owner: claude
--

ALTER SEQUENCE ga.migration_log_id_seq OWNED BY ga.migration_log.id;


--
-- Name: populations; Type: TABLE; Schema: ga; Owner: claude
--

CREATE TABLE ga.populations (
    id integer NOT NULL,
    use_case text NOT NULL,
    generation integer NOT NULL,
    island_id integer NOT NULL,
    chromosome jsonb NOT NULL,
    fitness double precision,
    fitness_details jsonb,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE ga.populations OWNER TO claude;

--
-- Name: populations_id_seq; Type: SEQUENCE; Schema: ga; Owner: claude
--

CREATE SEQUENCE ga.populations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE ga.populations_id_seq OWNER TO claude;

--
-- Name: populations_id_seq; Type: SEQUENCE OWNED BY; Schema: ga; Owner: claude
--

ALTER SEQUENCE ga.populations_id_seq OWNED BY ga.populations.id;


--
-- Name: machines; Type: TABLE; Schema: inventory; Owner: claude
--

CREATE TABLE inventory.machines (
    id integer NOT NULL,
    hostname character varying(100) NOT NULL,
    device_type character varying(50) NOT NULL,
    manufacturer character varying(100),
    model character varying(200),
    cpu_model text,
    cpu_arch character varying(20),
    cpu_cores integer,
    cpu_freq_mhz integer,
    ram_mb integer,
    storage_gb integer,
    storage_type character varying(50),
    network_ip inet,
    always_on boolean DEFAULT false,
    primary_role text,
    services text[],
    os character varying(100),
    os_version character varying(50),
    firmware character varying(100),
    has_debian_chroot boolean DEFAULT false,
    has_entware boolean DEFAULT false,
    swap_mb integer,
    nfs_exports text[],
    nfs_mounts text[],
    notes text,
    last_updated timestamp without time zone DEFAULT now(),
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE inventory.machines OWNER TO claude;

--
-- Name: TABLE machines; Type: COMMENT; Schema: inventory; Owner: claude
--

COMMENT ON TABLE inventory.machines IS 'Home lab infrastructure inventory - all machines, routers, NAS devices';


--
-- Name: COLUMN machines.always_on; Type: COMMENT; Schema: inventory; Owner: claude
--

COMMENT ON COLUMN inventory.machines.always_on IS 'True if machine runs 24/7, false if on-demand';


--
-- Name: COLUMN machines.primary_role; Type: COMMENT; Schema: inventory; Owner: claude
--

COMMENT ON COLUMN inventory.machines.primary_role IS 'Main purpose: Orchestrator, NFS server, DNS/DHCP, Heavy compute, etc.';


--
-- Name: machines_id_seq; Type: SEQUENCE; Schema: inventory; Owner: claude
--

CREATE SEQUENCE inventory.machines_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE inventory.machines_id_seq OWNER TO claude;

--
-- Name: machines_id_seq; Type: SEQUENCE OWNED BY; Schema: inventory; Owner: claude
--

ALTER SEQUENCE inventory.machines_id_seq OWNED BY inventory.machines.id;


--
-- Name: chunks; Type: TABLE; Schema: knowledge; Owner: sfloess
--

CREATE TABLE knowledge.chunks (
    id integer NOT NULL,
    document_id integer NOT NULL,
    chunk_index integer NOT NULL,
    content text NOT NULL,
    content_hash text NOT NULL,
    token_count integer,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE knowledge.chunks OWNER TO sfloess;

--
-- Name: chunks_id_seq; Type: SEQUENCE; Schema: knowledge; Owner: sfloess
--

CREATE SEQUENCE knowledge.chunks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE knowledge.chunks_id_seq OWNER TO sfloess;

--
-- Name: chunks_id_seq; Type: SEQUENCE OWNED BY; Schema: knowledge; Owner: sfloess
--

ALTER SEQUENCE knowledge.chunks_id_seq OWNED BY knowledge.chunks.id;


--
-- Name: code_embeddings; Type: TABLE; Schema: knowledge; Owner: claude
--

CREATE TABLE knowledge.code_embeddings (
    id integer NOT NULL,
    file_path text NOT NULL,
    file_type text DEFAULT 'unknown'::text,
    file_hash text DEFAULT ''::text,
    content_preview text,
    embedding public.vector(768),
    metadata jsonb,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    chunk_id text DEFAULT '0'::text,
    content text
);


ALTER TABLE knowledge.code_embeddings OWNER TO claude;

--
-- Name: code_embeddings_id_seq; Type: SEQUENCE; Schema: knowledge; Owner: claude
--

CREATE SEQUENCE knowledge.code_embeddings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE knowledge.code_embeddings_id_seq OWNER TO claude;

--
-- Name: code_embeddings_id_seq; Type: SEQUENCE OWNED BY; Schema: knowledge; Owner: claude
--

ALTER SEQUENCE knowledge.code_embeddings_id_seq OWNED BY knowledge.code_embeddings.id;


--
-- Name: concepts; Type: TABLE; Schema: knowledge; Owner: sfloess
--

CREATE TABLE knowledge.concepts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    type text NOT NULL,
    properties jsonb,
    embedding public.vector(128),
    confidence double precision,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT concepts_confidence_check CHECK (((confidence >= (0.0)::double precision) AND (confidence <= (1.0)::double precision)))
);


ALTER TABLE knowledge.concepts OWNER TO sfloess;

--
-- Name: discovered_sources; Type: TABLE; Schema: knowledge; Owner: claude
--

CREATE TABLE knowledge.discovered_sources (
    id integer NOT NULL,
    url text NOT NULL,
    title text,
    snippet text,
    domain text,
    query text,
    consensus_score double precision,
    quality_score double precision,
    tier text,
    discovered_at timestamp without time zone DEFAULT now()
);


ALTER TABLE knowledge.discovered_sources OWNER TO claude;

--
-- Name: discovered_sources_id_seq; Type: SEQUENCE; Schema: knowledge; Owner: claude
--

CREATE SEQUENCE knowledge.discovered_sources_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE knowledge.discovered_sources_id_seq OWNER TO claude;

--
-- Name: discovered_sources_id_seq; Type: SEQUENCE OWNED BY; Schema: knowledge; Owner: claude
--

ALTER SEQUENCE knowledge.discovered_sources_id_seq OWNED BY knowledge.discovered_sources.id;


--
-- Name: discoveries; Type: TABLE; Schema: knowledge; Owner: claude
--

CREATE TABLE knowledge.discoveries (
    id integer NOT NULL,
    worker_id character varying(255) NOT NULL,
    discovery_type character varying(100) NOT NULL,
    content text NOT NULL,
    confidence double precision NOT NULL,
    embedding public.vector(768),
    verified_by text[] DEFAULT ARRAY[]::text[],
    verification_count integer DEFAULT 0,
    rejection_count integer DEFAULT 0,
    status character varying(50) DEFAULT 'pending'::character varying,
    created_at timestamp without time zone DEFAULT now(),
    verified_at timestamp without time zone,
    metadata jsonb DEFAULT '{}'::jsonb,
    CONSTRAINT discoveries_confidence_check CHECK (((confidence >= (0.0)::double precision) AND (confidence <= (1.0)::double precision)))
);


ALTER TABLE knowledge.discoveries OWNER TO claude;

--
-- Name: discoveries_id_seq; Type: SEQUENCE; Schema: knowledge; Owner: claude
--

CREATE SEQUENCE knowledge.discoveries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE knowledge.discoveries_id_seq OWNER TO claude;

--
-- Name: discoveries_id_seq; Type: SEQUENCE OWNED BY; Schema: knowledge; Owner: claude
--

ALTER SEQUENCE knowledge.discoveries_id_seq OWNED BY knowledge.discoveries.id;


--
-- Name: documents; Type: TABLE; Schema: knowledge; Owner: claude
--

CREATE TABLE knowledge.documents (
    id integer NOT NULL,
    content text NOT NULL,
    embedding public.vector(768),
    category text,
    metadata jsonb,
    created_at timestamp without time zone DEFAULT now(),
    url text,
    title text,
    fetched_at timestamp without time zone,
    content_hash text
);


ALTER TABLE knowledge.documents OWNER TO claude;

--
-- Name: documents_id_seq; Type: SEQUENCE; Schema: knowledge; Owner: claude
--

CREATE SEQUENCE knowledge.documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE knowledge.documents_id_seq OWNER TO claude;

--
-- Name: documents_id_seq; Type: SEQUENCE OWNED BY; Schema: knowledge; Owner: claude
--

ALTER SEQUENCE knowledge.documents_id_seq OWNED BY knowledge.documents.id;


--
-- Name: embeddings; Type: TABLE; Schema: knowledge; Owner: sfloess
--

CREATE TABLE knowledge.embeddings (
    id integer NOT NULL,
    chunk_id integer NOT NULL,
    provider text NOT NULL,
    model text NOT NULL,
    embedding public.vector(768),
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE knowledge.embeddings OWNER TO sfloess;

--
-- Name: embeddings_id_seq; Type: SEQUENCE; Schema: knowledge; Owner: sfloess
--

CREATE SEQUENCE knowledge.embeddings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE knowledge.embeddings_id_seq OWNER TO sfloess;

--
-- Name: embeddings_id_seq; Type: SEQUENCE OWNED BY; Schema: knowledge; Owner: sfloess
--

ALTER SEQUENCE knowledge.embeddings_id_seq OWNED BY knowledge.embeddings.id;


--
-- Name: entries; Type: TABLE; Schema: knowledge; Owner: claude
--

CREATE TABLE knowledge.entries (
    id integer NOT NULL,
    content text NOT NULL,
    embedding public.vector(768),
    source text,
    source_type text,
    metadata jsonb,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE knowledge.entries OWNER TO claude;

--
-- Name: entries_id_seq; Type: SEQUENCE; Schema: knowledge; Owner: claude
--

CREATE SEQUENCE knowledge.entries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE knowledge.entries_id_seq OWNER TO claude;

--
-- Name: entries_id_seq; Type: SEQUENCE OWNED BY; Schema: knowledge; Owner: claude
--

ALTER SEQUENCE knowledge.entries_id_seq OWNED BY knowledge.entries.id;


--
-- Name: ingestion_queue; Type: TABLE; Schema: knowledge; Owner: postgres
--

CREATE TABLE knowledge.ingestion_queue (
    id integer NOT NULL,
    title text NOT NULL,
    url text NOT NULL,
    content text NOT NULL,
    source text NOT NULL,
    category text,
    published_date timestamp without time zone,
    metadata jsonb DEFAULT '{}'::jsonb,
    queued_at timestamp without time zone DEFAULT now(),
    processed_at timestamp without time zone,
    status text DEFAULT 'pending'::text,
    error text,
    CONSTRAINT ingestion_queue_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'processing'::text, 'completed'::text, 'failed'::text])))
);


ALTER TABLE knowledge.ingestion_queue OWNER TO postgres;

--
-- Name: ingestion_queue_id_seq; Type: SEQUENCE; Schema: knowledge; Owner: postgres
--

CREATE SEQUENCE knowledge.ingestion_queue_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE knowledge.ingestion_queue_id_seq OWNER TO postgres;

--
-- Name: ingestion_queue_id_seq; Type: SEQUENCE OWNED BY; Schema: knowledge; Owner: postgres
--

ALTER SEQUENCE knowledge.ingestion_queue_id_seq OWNED BY knowledge.ingestion_queue.id;


--
-- Name: memory_chunks; Type: TABLE; Schema: knowledge; Owner: claude
--

CREATE TABLE knowledge.memory_chunks (
    id integer NOT NULL,
    source_file text NOT NULL,
    chunk_index integer NOT NULL,
    content text NOT NULL,
    chunk_type text,
    char_count integer,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE knowledge.memory_chunks OWNER TO claude;

--
-- Name: memory_chunks_id_seq; Type: SEQUENCE; Schema: knowledge; Owner: claude
--

CREATE SEQUENCE knowledge.memory_chunks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE knowledge.memory_chunks_id_seq OWNER TO claude;

--
-- Name: memory_chunks_id_seq; Type: SEQUENCE OWNED BY; Schema: knowledge; Owner: claude
--

ALTER SEQUENCE knowledge.memory_chunks_id_seq OWNED BY knowledge.memory_chunks.id;


--
-- Name: provenance; Type: TABLE; Schema: knowledge; Owner: claude
--

CREATE TABLE knowledge.provenance (
    id integer NOT NULL,
    entry_id integer,
    action text NOT NULL,
    actor text,
    "timestamp" timestamp without time zone DEFAULT now(),
    details jsonb
);


ALTER TABLE knowledge.provenance OWNER TO claude;

--
-- Name: provenance_id_seq; Type: SEQUENCE; Schema: knowledge; Owner: claude
--

CREATE SEQUENCE knowledge.provenance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE knowledge.provenance_id_seq OWNER TO claude;

--
-- Name: provenance_id_seq; Type: SEQUENCE OWNED BY; Schema: knowledge; Owner: claude
--

ALTER SEQUENCE knowledge.provenance_id_seq OWNED BY knowledge.provenance.id;


--
-- Name: pubmed_articles; Type: TABLE; Schema: knowledge; Owner: claude
--

CREATE TABLE knowledge.pubmed_articles (
    id integer NOT NULL,
    article_id text,
    title text,
    abstract text,
    chunk_text text,
    chunk_index integer,
    embedding public.vector(768),
    metadata jsonb,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE knowledge.pubmed_articles OWNER TO claude;

--
-- Name: pubmed_articles_id_seq; Type: SEQUENCE; Schema: knowledge; Owner: claude
--

CREATE SEQUENCE knowledge.pubmed_articles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE knowledge.pubmed_articles_id_seq OWNER TO claude;

--
-- Name: pubmed_articles_id_seq; Type: SEQUENCE OWNED BY; Schema: knowledge; Owner: claude
--

ALTER SEQUENCE knowledge.pubmed_articles_id_seq OWNED BY knowledge.pubmed_articles.id;


--
-- Name: relationships; Type: TABLE; Schema: knowledge; Owner: sfloess
--

CREATE TABLE knowledge.relationships (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_id uuid,
    target_id uuid,
    relation_type text NOT NULL,
    strength double precision,
    evidence_count integer DEFAULT 1,
    confidence double precision,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT relationships_confidence_check CHECK (((confidence >= (0.0)::double precision) AND (confidence <= (1.0)::double precision))),
    CONSTRAINT relationships_strength_check CHECK (((strength >= (0.0)::double precision) AND (strength <= (1.0)::double precision)))
);


ALTER TABLE knowledge.relationships OWNER TO sfloess;

--
-- Name: research_findings; Type: TABLE; Schema: knowledge; Owner: sfloess
--

CREATE TABLE knowledge.research_findings (
    id integer NOT NULL,
    workflow_id text NOT NULL,
    chunk_index integer NOT NULL,
    content text NOT NULL,
    embedding public.vector(768),
    metadata jsonb,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE knowledge.research_findings OWNER TO sfloess;

--
-- Name: research_findings_id_seq; Type: SEQUENCE; Schema: knowledge; Owner: sfloess
--

CREATE SEQUENCE knowledge.research_findings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE knowledge.research_findings_id_seq OWNER TO sfloess;

--
-- Name: research_findings_id_seq; Type: SEQUENCE OWNED BY; Schema: knowledge; Owner: sfloess
--

ALTER SEQUENCE knowledge.research_findings_id_seq OWNED BY knowledge.research_findings.id;


--
-- Name: scraped_content; Type: TABLE; Schema: knowledge; Owner: claude
--

CREATE TABLE knowledge.scraped_content (
    id integer NOT NULL,
    source_path text NOT NULL,
    category text NOT NULL,
    chunk_index integer NOT NULL,
    content text NOT NULL,
    content_hash text NOT NULL,
    embedding public.vector(768),
    file_size integer,
    chunk_count integer,
    ingested_at timestamp without time zone DEFAULT now()
);


ALTER TABLE knowledge.scraped_content OWNER TO claude;

--
-- Name: scraped_content_id_seq; Type: SEQUENCE; Schema: knowledge; Owner: claude
--

CREATE SEQUENCE knowledge.scraped_content_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE knowledge.scraped_content_id_seq OWNER TO claude;

--
-- Name: scraped_content_id_seq; Type: SEQUENCE OWNED BY; Schema: knowledge; Owner: claude
--

ALTER SEQUENCE knowledge.scraped_content_id_seq OWNED BY knowledge.scraped_content.id;


--
-- Name: scraped_data; Type: TABLE; Schema: knowledge; Owner: claude
--

CREATE TABLE knowledge.scraped_data (
    id integer NOT NULL,
    category character varying(100) NOT NULL,
    source_file text NOT NULL,
    file_hash character varying(32) NOT NULL,
    chunk_index integer NOT NULL,
    chunk_text text NOT NULL,
    embedding public.vector(768),
    ingested_at timestamp without time zone DEFAULT now(),
    worker character varying(50) DEFAULT 'laptop-01'::character varying,
    agent integer DEFAULT 1
);


ALTER TABLE knowledge.scraped_data OWNER TO claude;

--
-- Name: scraped_data_id_seq; Type: SEQUENCE; Schema: knowledge; Owner: claude
--

CREATE SEQUENCE knowledge.scraped_data_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE knowledge.scraped_data_id_seq OWNER TO claude;

--
-- Name: scraped_data_id_seq; Type: SEQUENCE OWNED BY; Schema: knowledge; Owner: claude
--

ALTER SEQUENCE knowledge.scraped_data_id_seq OWNED BY knowledge.scraped_data.id;


--
-- Name: url_status; Type: TABLE; Schema: knowledge; Owner: claude
--

CREATE TABLE knowledge.url_status (
    id integer NOT NULL,
    url text NOT NULL,
    http_status integer,
    category text,
    worker text,
    error_message text,
    content_length integer DEFAULT 0,
    first_seen_at timestamp without time zone DEFAULT now(),
    last_checked_at timestamp without time zone DEFAULT now(),
    attempts integer DEFAULT 1,
    stored boolean DEFAULT false
);


ALTER TABLE knowledge.url_status OWNER TO claude;

--
-- Name: TABLE url_status; Type: COMMENT; Schema: knowledge; Owner: claude
--

COMMENT ON TABLE knowledge.url_status IS 'Tracks HTTP status for all scraped URLs including 404s';


--
-- Name: url_status_id_seq; Type: SEQUENCE; Schema: knowledge; Owner: claude
--

CREATE SEQUENCE knowledge.url_status_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE knowledge.url_status_id_seq OWNER TO claude;

--
-- Name: url_status_id_seq; Type: SEQUENCE OWNED BY; Schema: knowledge; Owner: claude
--

ALTER SEQUENCE knowledge.url_status_id_seq OWNED BY knowledge.url_status.id;


--
-- Name: verification_votes; Type: TABLE; Schema: knowledge; Owner: claude
--

CREATE TABLE knowledge.verification_votes (
    id integer NOT NULL,
    discovery_id integer,
    worker_id character varying(255) NOT NULL,
    vote boolean NOT NULL,
    reasoning text,
    voted_at timestamp without time zone DEFAULT now()
);


ALTER TABLE knowledge.verification_votes OWNER TO claude;

--
-- Name: verification_votes_id_seq; Type: SEQUENCE; Schema: knowledge; Owner: claude
--

CREATE SEQUENCE knowledge.verification_votes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE knowledge.verification_votes_id_seq OWNER TO claude;

--
-- Name: verification_votes_id_seq; Type: SEQUENCE OWNED BY; Schema: knowledge; Owner: claude
--

ALTER SEQUENCE knowledge.verification_votes_id_seq OWNED BY knowledge.verification_votes.id;


--
-- Name: web_articles; Type: TABLE; Schema: knowledge; Owner: sfloess
--

CREATE TABLE knowledge.web_articles (
    id integer NOT NULL,
    title text NOT NULL,
    url text NOT NULL,
    content text NOT NULL,
    embedding public.vector(768),
    published_date timestamp without time zone,
    category text,
    tags text[],
    source text NOT NULL,
    author text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE knowledge.web_articles OWNER TO sfloess;

--
-- Name: web_articles_id_seq; Type: SEQUENCE; Schema: knowledge; Owner: sfloess
--

CREATE SEQUENCE knowledge.web_articles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE knowledge.web_articles_id_seq OWNER TO sfloess;

--
-- Name: web_articles_id_seq; Type: SEQUENCE OWNED BY; Schema: knowledge; Owner: sfloess
--

ALTER SEQUENCE knowledge.web_articles_id_seq OWNED BY knowledge.web_articles.id;


--
-- Name: web_scrape; Type: TABLE; Schema: knowledge; Owner: claude
--

CREATE TABLE knowledge.web_scrape (
    id integer NOT NULL,
    category text NOT NULL,
    source_file text NOT NULL,
    title text,
    chunk_index integer NOT NULL,
    content text NOT NULL,
    embedding public.vector(768),
    metadata jsonb,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE knowledge.web_scrape OWNER TO claude;

--
-- Name: web_scrape_id_seq; Type: SEQUENCE; Schema: knowledge; Owner: claude
--

CREATE SEQUENCE knowledge.web_scrape_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE knowledge.web_scrape_id_seq OWNER TO claude;

--
-- Name: web_scrape_id_seq; Type: SEQUENCE OWNED BY; Schema: knowledge; Owner: claude
--

ALTER SEQUENCE knowledge.web_scrape_id_seq OWNED BY knowledge.web_scrape.id;


--
-- Name: analogical_patterns; Type: TABLE; Schema: learning; Owner: sfloess
--

CREATE TABLE learning.analogical_patterns (
    pattern_id character varying NOT NULL,
    domain character varying,
    entities jsonb,
    relations jsonb,
    solution text,
    context text,
    embedding public.vector(768),
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.analogical_patterns OWNER TO sfloess;

--
-- Name: api_models; Type: TABLE; Schema: learning; Owner: sfloess
--

CREATE TABLE learning.api_models (
    id integer NOT NULL,
    provider text NOT NULL,
    model_id text NOT NULL,
    name text NOT NULL,
    context_length integer,
    pricing text,
    architecture jsonb,
    downloads integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE learning.api_models OWNER TO sfloess;

--
-- Name: api_models_id_seq; Type: SEQUENCE; Schema: learning; Owner: sfloess
--

CREATE SEQUENCE learning.api_models_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.api_models_id_seq OWNER TO sfloess;

--
-- Name: api_models_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: sfloess
--

ALTER SEQUENCE learning.api_models_id_seq OWNED BY learning.api_models.id;


--
-- Name: bandit_models; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.bandit_models (
    model_name character varying NOT NULL,
    model_type character varying,
    num_strategies integer,
    context_dim integer,
    alpha double precision,
    training_records integer,
    accuracy double precision,
    model_path character varying,
    trained_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.bandit_models OWNER TO claude;

--
-- Name: model_capabilities; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.model_capabilities (
    model_id text NOT NULL,
    provider text,
    code_generation double precision,
    code_review double precision,
    research double precision,
    math_reasoning double precision,
    general_qa double precision,
    creative_writing double precision,
    security_analysis double precision,
    avg_latency_ms integer,
    context_window integer,
    last_tested timestamp without time zone DEFAULT now(),
    test_count integer DEFAULT 0,
    notes text,
    CONSTRAINT model_capabilities_code_generation_check CHECK (((code_generation >= (0)::double precision) AND (code_generation <= (1)::double precision))),
    CONSTRAINT model_capabilities_code_review_check CHECK (((code_review >= (0)::double precision) AND (code_review <= (1)::double precision))),
    CONSTRAINT model_capabilities_creative_writing_check CHECK (((creative_writing >= (0)::double precision) AND (creative_writing <= (1)::double precision))),
    CONSTRAINT model_capabilities_general_qa_check CHECK (((general_qa >= (0)::double precision) AND (general_qa <= (1)::double precision))),
    CONSTRAINT model_capabilities_math_reasoning_check CHECK (((math_reasoning >= (0)::double precision) AND (math_reasoning <= (1)::double precision))),
    CONSTRAINT model_capabilities_research_check CHECK (((research >= (0)::double precision) AND (research <= (1)::double precision))),
    CONSTRAINT model_capabilities_security_analysis_check CHECK (((security_analysis >= (0)::double precision) AND (security_analysis <= (1)::double precision)))
);


ALTER TABLE learning.model_capabilities OWNER TO claude;

--
-- Name: best_models_by_task; Type: VIEW; Schema: learning; Owner: sfloess
--

CREATE VIEW learning.best_models_by_task AS
 SELECT 'code_generation'::text AS task,
    model_id,
    provider,
    code_generation AS score,
    avg_latency_ms
   FROM learning.model_capabilities
  WHERE (code_generation IS NOT NULL)
  ORDER BY code_generation DESC
 LIMIT 10;


ALTER VIEW learning.best_models_by_task OWNER TO sfloess;

--
-- Name: claude_memory; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.claude_memory (
    id text NOT NULL,
    document text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb,
    embedding public.vector(768),
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.claude_memory OWNER TO claude;

--
-- Name: codebase_analysis; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.codebase_analysis (
    id integer NOT NULL,
    file_path text NOT NULL,
    absolute_path text NOT NULL,
    extension text,
    size_bytes integer,
    git_introduced_commit text,
    git_introduced_by text,
    git_introduced_date timestamp without time zone,
    git_last_commit text,
    git_last_modified_by text,
    git_last_modified_date timestamp without time zone,
    git_status text,
    related_implementations jsonb DEFAULT '[]'::jsonb,
    enrichment_timestamp timestamp without time zone,
    chunk_index integer DEFAULT 0,
    total_chunks integer DEFAULT 1,
    chunk_size integer,
    embedding public.vector(768),
    embedding_dim integer,
    embedding_text text,
    model text DEFAULT 'all-mpnet-base-v2'::text,
    quality_score real,
    confidence real,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.codebase_analysis OWNER TO claude;

--
-- Name: TABLE codebase_analysis; Type: COMMENT; Schema: learning; Owner: claude
--

COMMENT ON TABLE learning.codebase_analysis IS 'Codebase embeddings with rich git metadata - similar schema to research_full table';


--
-- Name: codebase_analysis_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.codebase_analysis_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.codebase_analysis_id_seq OWNER TO claude;

--
-- Name: codebase_analysis_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.codebase_analysis_id_seq OWNED BY learning.codebase_analysis.id;


--
-- Name: comprehensive_research; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.comprehensive_research (
    id integer NOT NULL,
    source text NOT NULL,
    category text NOT NULL,
    repo_name text,
    document text NOT NULL,
    embedding public.vector(768) NOT NULL,
    metadata jsonb NOT NULL,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.comprehensive_research OWNER TO claude;

--
-- Name: comprehensive_research_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.comprehensive_research_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.comprehensive_research_id_seq OWNER TO claude;

--
-- Name: comprehensive_research_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.comprehensive_research_id_seq OWNED BY learning.comprehensive_research.id;


--
-- Name: concepts; Type: TABLE; Schema: learning; Owner: postgres
--

CREATE TABLE learning.concepts (
    id integer NOT NULL,
    name text NOT NULL,
    concept_type text,
    properties jsonb,
    importance double precision DEFAULT 0.5,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.concepts OWNER TO postgres;

--
-- Name: concepts_id_seq; Type: SEQUENCE; Schema: learning; Owner: postgres
--

CREATE SEQUENCE learning.concepts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.concepts_id_seq OWNER TO postgres;

--
-- Name: concepts_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: postgres
--

ALTER SEQUENCE learning.concepts_id_seq OWNED BY learning.concepts.id;


--
-- Name: confidence_observations; Type: TABLE; Schema: learning; Owner: sfloess
--

CREATE TABLE learning.confidence_observations (
    id integer NOT NULL,
    model text NOT NULL,
    reported_confidence real NOT NULL,
    actual_outcome real NOT NULL,
    task_type text,
    execution_id text,
    "timestamp" timestamp with time zone DEFAULT now()
);


ALTER TABLE learning.confidence_observations OWNER TO sfloess;

--
-- Name: confidence_observations_id_seq; Type: SEQUENCE; Schema: learning; Owner: sfloess
--

CREATE SEQUENCE learning.confidence_observations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.confidence_observations_id_seq OWNER TO sfloess;

--
-- Name: confidence_observations_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: sfloess
--

ALTER SEQUENCE learning.confidence_observations_id_seq OWNED BY learning.confidence_observations.id;


--
-- Name: consciousness_research; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.consciousness_research (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now(),
    original_id text,
    embedding public.vector(768),
    metadata jsonb,
    document text,
    information_density double precision,
    structural_position jsonb,
    claim_assertions jsonb,
    retrieval_feedback jsonb,
    source_document_id text,
    temporal_context text
);


ALTER TABLE learning.consciousness_research OWNER TO claude;

--
-- Name: continual_learning_roadmap; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.continual_learning_roadmap (
    id integer NOT NULL,
    technique text NOT NULL,
    status text NOT NULL,
    roi double precision NOT NULL,
    effort_hours integer NOT NULL,
    impact_pct integer NOT NULL,
    priority text NOT NULL,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE learning.continual_learning_roadmap OWNER TO claude;

--
-- Name: continual_learning_roadmap_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.continual_learning_roadmap_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.continual_learning_roadmap_id_seq OWNER TO claude;

--
-- Name: continual_learning_roadmap_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.continual_learning_roadmap_id_seq OWNED BY learning.continual_learning_roadmap.id;


--
-- Name: conversation_learnings; Type: TABLE; Schema: learning; Owner: sfloess
--

CREATE TABLE learning.conversation_learnings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    learning_type text NOT NULL,
    content text NOT NULL,
    session_id text,
    "timestamp" timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    embedding public.vector(768)
);


ALTER TABLE learning.conversation_learnings OWNER TO sfloess;

--
-- Name: model_quotas; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.model_quotas (
    model text NOT NULL,
    floor_pct real DEFAULT 15.0 NOT NULL,
    ceiling_pct real DEFAULT 40.0 NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    pareto_frontier_member boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT model_quotas_ceiling_pct_check CHECK (((ceiling_pct >= (0)::double precision) AND (ceiling_pct <= (100)::double precision))),
    CONSTRAINT model_quotas_floor_pct_check CHECK (((floor_pct >= (0)::double precision) AND (floor_pct <= (100)::double precision)))
);


ALTER TABLE learning.model_quotas OWNER TO claude;

--
-- Name: request_history; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.request_history (
    id integer NOT NULL,
    request_id uuid NOT NULL,
    model text NOT NULL,
    "timestamp" timestamp without time zone DEFAULT now() NOT NULL,
    task_type text,
    success boolean,
    quality_score real,
    duration_ms integer,
    cost_usd real,
    diversity_score real,
    quota_enforced boolean DEFAULT false NOT NULL,
    excluded_models text[] DEFAULT '{}'::text[],
    forced_models text[] DEFAULT '{}'::text[],
    ab_bucket text,
    CONSTRAINT request_history_ab_bucket_check CHECK (((ab_bucket IS NULL) OR (ab_bucket = ANY (ARRAY['A'::text, 'B'::text])))),
    CONSTRAINT request_history_cost_usd_check CHECK ((cost_usd >= (0)::double precision)),
    CONSTRAINT request_history_diversity_score_check CHECK ((diversity_score >= (0)::double precision)),
    CONSTRAINT request_history_duration_ms_check CHECK ((duration_ms >= 0)),
    CONSTRAINT request_history_quality_score_check CHECK (((quality_score >= (0)::double precision) AND (quality_score <= (1)::double precision)))
);


ALTER TABLE learning.request_history OWNER TO claude;

--
-- Name: diversity_current; Type: VIEW; Schema: learning; Owner: sfloess
--

CREATE VIEW learning.diversity_current AS
 WITH recent_requests AS (
         SELECT request_history.model,
            request_history."timestamp"
           FROM learning.request_history
          ORDER BY request_history."timestamp" DESC
         LIMIT 20
        ), model_counts AS (
         SELECT recent_requests.model,
            count(*) AS request_count
           FROM recent_requests
          GROUP BY recent_requests.model
        ), total_count AS (
         SELECT COALESCE(sum(model_counts.request_count), (0)::numeric) AS total
           FROM model_counts
        )
 SELECT mq.model,
    COALESCE(mc.request_count, (0)::bigint) AS request_count,
        CASE
            WHEN (tc.total = (0)::numeric) THEN (0.0)::double precision
            ELSE (((COALESCE(mc.request_count, (0)::bigint))::real / (tc.total)::real) * (100.0)::double precision)
        END AS usage_pct,
    mq.floor_pct,
    mq.ceiling_pct,
    mq.enabled,
    mq.pareto_frontier_member,
        CASE
            WHEN (tc.total = (0)::numeric) THEN 'OK'::text
            WHEN ((((COALESCE(mc.request_count, (0)::bigint))::real / (tc.total)::real) * (100.0)::double precision) < mq.floor_pct) THEN 'floor_breach'::text
            WHEN ((((COALESCE(mc.request_count, (0)::bigint))::real / (tc.total)::real) * (100.0)::double precision) > mq.ceiling_pct) THEN 'ceiling_breach'::text
            ELSE 'OK'::text
        END AS quota_status,
        CASE
            WHEN ((((COALESCE(mc.request_count, (0)::bigint))::real / (tc.total)::real) * (100.0)::double precision) < mq.floor_pct) THEN 1
            ELSE 0
        END AS floor_violations,
        CASE
            WHEN ((((COALESCE(mc.request_count, (0)::bigint))::real / (tc.total)::real) * (100.0)::double precision) > mq.ceiling_pct) THEN 1
            ELSE 0
        END AS ceiling_violations
   FROM ((learning.model_quotas mq
     CROSS JOIN total_count tc)
     LEFT JOIN model_counts mc ON ((mq.model = mc.model)))
  WHERE (mq.enabled = true);


ALTER VIEW learning.diversity_current OWNER TO sfloess;

--
-- Name: diversity_violations; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.diversity_violations (
    id integer NOT NULL,
    "timestamp" timestamp without time zone DEFAULT now() NOT NULL,
    violation_type text NOT NULL,
    model text NOT NULL,
    current_usage_pct real NOT NULL,
    quota_limit_pct real NOT NULL,
    diversity_entropy real,
    action_taken text NOT NULL,
    CONSTRAINT diversity_violations_violation_type_check CHECK ((violation_type = ANY (ARRAY['floor_breach'::text, 'ceiling_breach'::text, 'entropy_collapse'::text])))
);


ALTER TABLE learning.diversity_violations OWNER TO claude;

--
-- Name: diversity_violations_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.diversity_violations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.diversity_violations_id_seq OWNER TO claude;

--
-- Name: diversity_violations_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.diversity_violations_id_seq OWNED BY learning.diversity_violations.id;


--
-- Name: error_logs; Type: TABLE; Schema: learning; Owner: sfloess
--

CREATE TABLE learning.error_logs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    error_type text,
    message text,
    embedding public.vector(768),
    stack_trace text,
    context jsonb,
    solution text,
    "timestamp" timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE learning.error_logs OWNER TO sfloess;

--
-- Name: exp3_arms; Type: TABLE; Schema: learning; Owner: postgres
--

CREATE TABLE learning.exp3_arms (
    arm_id text NOT NULL,
    weight double precision NOT NULL,
    last_probability double precision NOT NULL,
    total_reward double precision NOT NULL,
    n integer NOT NULL,
    gamma double precision NOT NULL,
    last_updated timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.exp3_arms OWNER TO postgres;

--
-- Name: exp3_state; Type: TABLE; Schema: learning; Owner: postgres
--

CREATE TABLE learning.exp3_state (
    key text NOT NULL,
    value double precision NOT NULL,
    last_updated timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.exp3_state OWNER TO postgres;

--
-- Name: experiences; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.experiences (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now(),
    problem_type text NOT NULL,
    problem_hash text NOT NULL,
    context jsonb,
    embedding_old_128 public.vector(128),
    strategy text NOT NULL,
    strategy_params jsonb,
    success boolean NOT NULL,
    reward double precision NOT NULL,
    execution_time_ms integer,
    cpu_usage_pct double precision,
    memory_mb double precision,
    confidence_before double precision,
    confidence_after double precision,
    user_feedback text,
    novelty_score double precision,
    importance double precision,
    access_count integer DEFAULT 0,
    last_accessed timestamp with time zone,
    embedding public.vector(768),
    CONSTRAINT experiences_confidence_after_check CHECK (((confidence_after >= (0.0)::double precision) AND (confidence_after <= (1.0)::double precision))),
    CONSTRAINT experiences_confidence_before_check CHECK (((confidence_before >= (0.0)::double precision) AND (confidence_before <= (1.0)::double precision))),
    CONSTRAINT experiences_importance_check CHECK (((importance >= (0.0)::double precision) AND (importance <= (1.0)::double precision))),
    CONSTRAINT experiences_novelty_score_check CHECK (((novelty_score >= (0.0)::double precision) AND (novelty_score <= (1.0)::double precision))),
    CONSTRAINT experiences_reward_check CHECK (((reward >= ('-1.0'::numeric)::double precision) AND (reward <= (1.0)::double precision)))
);


ALTER TABLE learning.experiences OWNER TO claude;

--
-- Name: experiences_experiment; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.experiences_experiment (
    id integer NOT NULL,
    problem_type text NOT NULL,
    problem_hash text NOT NULL,
    context jsonb NOT NULL,
    embedding public.vector(128) NOT NULL,
    strategy text NOT NULL,
    success boolean NOT NULL,
    reward double precision NOT NULL,
    novelty_score double precision,
    importance double precision,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.experiences_experiment OWNER TO claude;

--
-- Name: experiences_experiment_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.experiences_experiment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.experiences_experiment_id_seq OWNER TO claude;

--
-- Name: experiences_experiment_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.experiences_experiment_id_seq OWNED BY learning.experiences_experiment.id;


--
-- Name: experiment_results; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.experiment_results (
    id integer NOT NULL,
    experiment_name text NOT NULL,
    method text NOT NULL,
    total_tasks integer,
    success_count integer,
    success_rate double precision,
    avg_reward double precision,
    avg_selection_time_ms double precision,
    convergence_speed integer,
    strategy_counts jsonb,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.experiment_results OWNER TO claude;

--
-- Name: experiment_results_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.experiment_results_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.experiment_results_id_seq OWNER TO claude;

--
-- Name: experiment_results_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.experiment_results_id_seq OWNED BY learning.experiment_results.id;


--
-- Name: fine_tuning_queue; Type: TABLE; Schema: learning; Owner: postgres
--

CREATE TABLE learning.fine_tuning_queue (
    id integer NOT NULL,
    topic text NOT NULL,
    example_data jsonb NOT NULL,
    embedding public.vector(768),
    status text DEFAULT 'pending'::text,
    quality_score double precision,
    "timestamp" timestamp without time zone DEFAULT now(),
    trained_at timestamp without time zone
);


ALTER TABLE learning.fine_tuning_queue OWNER TO postgres;

--
-- Name: TABLE fine_tuning_queue; Type: COMMENT; Schema: learning; Owner: postgres
--

COMMENT ON TABLE learning.fine_tuning_queue IS 'New examples ready for fine-tuning';


--
-- Name: fine_tuning_queue_id_seq; Type: SEQUENCE; Schema: learning; Owner: postgres
--

CREATE SEQUENCE learning.fine_tuning_queue_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.fine_tuning_queue_id_seq OWNER TO postgres;

--
-- Name: fine_tuning_queue_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: postgres
--

ALTER SEQUENCE learning.fine_tuning_queue_id_seq OWNED BY learning.fine_tuning_queue.id;


--
-- Name: free_models; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.free_models (
    id integer NOT NULL,
    provider text NOT NULL,
    model_id text NOT NULL,
    model_name text,
    context_length integer,
    architecture text,
    pricing text DEFAULT 'free'::text,
    discovered_at timestamp without time zone DEFAULT now(),
    last_seen timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.free_models OWNER TO claude;

--
-- Name: free_models_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.free_models_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.free_models_id_seq OWNER TO claude;

--
-- Name: free_models_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.free_models_id_seq OWNED BY learning.free_models.id;


--
-- Name: ga_configs; Type: TABLE; Schema: learning; Owner: postgres
--

CREATE TABLE learning.ga_configs (
    id integer NOT NULL,
    config_type text NOT NULL,
    generation integer NOT NULL,
    config jsonb NOT NULL,
    fitness_score double precision NOT NULL,
    "timestamp" timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.ga_configs OWNER TO postgres;

--
-- Name: TABLE ga_configs; Type: COMMENT; Schema: learning; Owner: postgres
--

COMMENT ON TABLE learning.ga_configs IS 'Evolved configurations from GA';


--
-- Name: ga_configs_id_seq; Type: SEQUENCE; Schema: learning; Owner: postgres
--

CREATE SEQUENCE learning.ga_configs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.ga_configs_id_seq OWNER TO postgres;

--
-- Name: ga_configs_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: postgres
--

ALTER SEQUENCE learning.ga_configs_id_seq OWNED BY learning.ga_configs.id;


--
-- Name: git_commits; Type: TABLE; Schema: learning; Owner: sfloess
--

CREATE TABLE learning.git_commits (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    commit_hash text NOT NULL,
    author text,
    message text,
    embedding public.vector(768),
    files_changed text[],
    additions integer,
    deletions integer,
    branch text,
    "timestamp" timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE learning.git_commits OWNER TO sfloess;

--
-- Name: gitlab_issues; Type: TABLE; Schema: learning; Owner: sfloess
--

CREATE TABLE learning.gitlab_issues (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    issue_id integer NOT NULL,
    title text,
    description text,
    embedding public.vector(768),
    labels text[],
    state text,
    solution text,
    created_at_issue timestamp with time zone,
    closed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE learning.gitlab_issues OWNER TO sfloess;

--
-- Name: icl_examples; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.icl_examples (
    id integer NOT NULL,
    task_type text NOT NULL,
    input text NOT NULL,
    output text NOT NULL,
    quality_score double precision NOT NULL,
    embedding public.vector(768),
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE learning.icl_examples OWNER TO claude;

--
-- Name: icl_examples_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.icl_examples_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.icl_examples_id_seq OWNER TO claude;

--
-- Name: icl_examples_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.icl_examples_id_seq OWNED BY learning.icl_examples.id;


--
-- Name: improvements; Type: TABLE; Schema: learning; Owner: postgres
--

CREATE TABLE learning.improvements (
    id integer NOT NULL,
    topic text NOT NULL,
    before_quality double precision NOT NULL,
    after_quality double precision NOT NULL,
    improvement double precision NOT NULL,
    examples_used integer NOT NULL,
    training_time_sec integer,
    "timestamp" timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.improvements OWNER TO postgres;

--
-- Name: TABLE improvements; Type: COMMENT; Schema: learning; Owner: postgres
--

COMMENT ON TABLE learning.improvements IS 'Track learning progress over time';


--
-- Name: improvements_id_seq; Type: SEQUENCE; Schema: learning; Owner: postgres
--

CREATE SEQUENCE learning.improvements_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.improvements_id_seq OWNER TO postgres;

--
-- Name: improvements_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: postgres
--

ALTER SEQUENCE learning.improvements_id_seq OWNED BY learning.improvements.id;


--
-- Name: infrastructure_knowledge; Type: TABLE; Schema: learning; Owner: postgres
--

CREATE TABLE learning.infrastructure_knowledge (
    id integer NOT NULL,
    chunk_text text NOT NULL,
    embedding public.vector(768),
    metadata jsonb,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.infrastructure_knowledge OWNER TO postgres;

--
-- Name: infrastructure_knowledge_id_seq; Type: SEQUENCE; Schema: learning; Owner: postgres
--

CREATE SEQUENCE learning.infrastructure_knowledge_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.infrastructure_knowledge_id_seq OWNER TO postgres;

--
-- Name: infrastructure_knowledge_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: postgres
--

ALTER SEQUENCE learning.infrastructure_knowledge_id_seq OWNED BY learning.infrastructure_knowledge.id;


--
-- Name: knowledge_embeddings; Type: TABLE; Schema: learning; Owner: postgres
--

CREATE TABLE learning.knowledge_embeddings (
    id integer NOT NULL,
    source_file text NOT NULL,
    category text NOT NULL,
    chunk_index integer NOT NULL,
    content text NOT NULL,
    embedding public.vector(768),
    ingested_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.knowledge_embeddings OWNER TO postgres;

--
-- Name: knowledge_embeddings_id_seq; Type: SEQUENCE; Schema: learning; Owner: postgres
--

CREATE SEQUENCE learning.knowledge_embeddings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.knowledge_embeddings_id_seq OWNER TO postgres;

--
-- Name: knowledge_embeddings_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: postgres
--

ALTER SEQUENCE learning.knowledge_embeddings_id_seq OWNED BY learning.knowledge_embeddings.id;


--
-- Name: linucb_arms; Type: TABLE; Schema: learning; Owner: postgres
--

CREATE TABLE learning.linucb_arms (
    arm_id text NOT NULL,
    feature_dim integer NOT NULL,
    alpha double precision NOT NULL,
    a_matrix bytea NOT NULL,
    b_vector bytea NOT NULL,
    theta_vector bytea NOT NULL,
    observations integer NOT NULL,
    last_updated timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.linucb_arms OWNER TO postgres;

--
-- Name: load_balancer_state; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.load_balancer_state (
    id integer NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    window_days integer NOT NULL,
    model character varying(100) NOT NULL,
    executions integer NOT NULL,
    avg_quality double precision NOT NULL,
    std_quality double precision NOT NULL,
    avg_latency_ms double precision NOT NULL,
    avg_cost double precision NOT NULL,
    success_rate double precision NOT NULL,
    p50_latency double precision NOT NULL,
    p95_latency double precision NOT NULL,
    total_tokens bigint NOT NULL,
    bandit_alpha integer NOT NULL,
    bandit_beta integer NOT NULL,
    load_percentage double precision NOT NULL
);


ALTER TABLE learning.load_balancer_state OWNER TO claude;

--
-- Name: load_balancer_state_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.load_balancer_state_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.load_balancer_state_id_seq OWNER TO claude;

--
-- Name: load_balancer_state_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.load_balancer_state_id_seq OWNED BY learning.load_balancer_state.id;


--
-- Name: massive_validations; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.massive_validations (
    validation_id character varying NOT NULL,
    prompt text,
    strategy character varying,
    total_validators integer,
    mean_quality double precision,
    consensus_verdict character varying,
    provider_breakdown jsonb,
    minority_opinions jsonb,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.massive_validations OWNER TO claude;

--
-- Name: memories; Type: TABLE; Schema: learning; Owner: sfloess
--

CREATE TABLE learning.memories (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    description text,
    memory_type text NOT NULL,
    content text NOT NULL,
    embedding public.vector(768),
    tags text[],
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE learning.memories OWNER TO sfloess;

--
-- Name: memory; Type: TABLE; Schema: learning; Owner: postgres
--

CREATE TABLE learning.memory (
    id integer NOT NULL,
    memory_type character varying(50) NOT NULL,
    content text NOT NULL,
    embedding public.vector(768),
    metadata jsonb DEFAULT '{}'::jsonb,
    source_file character varying(255),
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    access_count integer DEFAULT 0,
    last_accessed timestamp without time zone
);


ALTER TABLE learning.memory OWNER TO postgres;

--
-- Name: TABLE memory; Type: COMMENT; Schema: learning; Owner: postgres
--

COMMENT ON TABLE learning.memory IS 'Memory persistence with embeddings for semantic search';


--
-- Name: COLUMN memory.embedding; Type: COMMENT; Schema: learning; Owner: postgres
--

COMMENT ON COLUMN learning.memory.embedding IS '768-dim sentence embeddings from Jina/Voyage/local';


--
-- Name: memory_id_seq; Type: SEQUENCE; Schema: learning; Owner: postgres
--

CREATE SEQUENCE learning.memory_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.memory_id_seq OWNER TO postgres;

--
-- Name: memory_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: postgres
--

ALTER SEQUENCE learning.memory_id_seq OWNED BY learning.memory.id;


--
-- Name: metadata_schema_test; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.metadata_schema_test (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now(),
    content text NOT NULL,
    embedding public.vector(128),
    content_hash text NOT NULL,
    chunk_type text NOT NULL,
    priority_level text NOT NULL,
    models_involved text[] DEFAULT '{}'::text[] NOT NULL,
    outcome_status text,
    quality_score double precision,
    source_workflow text,
    verification_status text,
    source_attribution text,
    domain_tags text[] DEFAULT '{}'::text[],
    cost_usd numeric(10,6),
    components_used text[] DEFAULT '{}'::text[],
    semantic_topics text[] DEFAULT '{}'::text[],
    confidence_score double precision,
    entity_mentions text[] DEFAULT '{}'::text[],
    latency_sensitivity text,
    task_complexity text,
    retention_policy text,
    embedding_model text,
    temporal_validity text,
    conversation_turn integer,
    execution_time_ms integer,
    access_count integer DEFAULT 0,
    last_accessed timestamp with time zone,
    CONSTRAINT metadata_schema_test_chunk_type_check CHECK ((chunk_type = ANY (ARRAY['discovery'::text, 'execution'::text, 'error'::text, 'strategy_update'::text, 'user_feedback'::text, 'system_event'::text]))),
    CONSTRAINT metadata_schema_test_confidence_score_check CHECK (((confidence_score >= (0.0)::double precision) AND (confidence_score <= (1.0)::double precision))),
    CONSTRAINT metadata_schema_test_latency_sensitivity_check CHECK ((latency_sensitivity = ANY (ARRAY['realtime'::text, 'interactive'::text, 'batch'::text, 'background'::text]))),
    CONSTRAINT metadata_schema_test_outcome_status_check CHECK ((outcome_status = ANY (ARRAY['success'::text, 'partial'::text, 'failed'::text, 'pending'::text, 'skipped'::text]))),
    CONSTRAINT metadata_schema_test_priority_level_check CHECK ((priority_level = ANY (ARRAY['critical'::text, 'high'::text, 'medium'::text, 'low'::text]))),
    CONSTRAINT metadata_schema_test_quality_score_check CHECK (((quality_score >= (0.0)::double precision) AND (quality_score <= (1.0)::double precision))),
    CONSTRAINT metadata_schema_test_retention_policy_check CHECK ((retention_policy = ANY (ARRAY['permanent'::text, '90_days'::text, '30_days'::text, '7_days'::text, 'ephemeral'::text]))),
    CONSTRAINT metadata_schema_test_task_complexity_check CHECK ((task_complexity = ANY (ARRAY['trivial'::text, 'simple'::text, 'moderate'::text, 'complex'::text, 'very_complex'::text]))),
    CONSTRAINT metadata_schema_test_verification_status_check CHECK ((verification_status = ANY (ARRAY['unverified'::text, 'verified'::text, 'adversarial_tested'::text, 'user_confirmed'::text, 'failed_verification'::text])))
);


ALTER TABLE learning.metadata_schema_test OWNER TO claude;

--
-- Name: model_censorship; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.model_censorship (
    id integer NOT NULL,
    model_name text NOT NULL,
    provider text NOT NULL,
    location text,
    size_gb numeric(10,2),
    censorship_level integer NOT NULL,
    censorship_rating text NOT NULL,
    answer_availability_pct integer,
    category text,
    specialization text,
    status text DEFAULT 'installed'::text,
    free_tier boolean DEFAULT true,
    daily_limit integer,
    cost_per_1m_tokens numeric(10,4) DEFAULT 0.00,
    notes text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    CONSTRAINT model_censorship_answer_availability_pct_check CHECK (((answer_availability_pct >= 0) AND (answer_availability_pct <= 100))),
    CONSTRAINT model_censorship_censorship_level_check CHECK (((censorship_level >= 1) AND (censorship_level <= 5)))
);


ALTER TABLE learning.model_censorship OWNER TO claude;

--
-- Name: TABLE model_censorship; Type: COMMENT; Schema: learning; Owner: claude
--

COMMENT ON TABLE learning.model_censorship IS 'Tracks all FREE AI models with censorship ratings and metadata';


--
-- Name: COLUMN model_censorship.censorship_level; Type: COMMENT; Schema: learning; Owner: claude
--

COMMENT ON COLUMN learning.model_censorship.censorship_level IS '5=Uncensored, 4=Minimal, 3=Moderate, 2=Strong, 1=Maximum';


--
-- Name: COLUMN model_censorship.answer_availability_pct; Type: COMMENT; Schema: learning; Owner: claude
--

COMMENT ON COLUMN learning.model_censorship.answer_availability_pct IS 'Percentage of questions answered without refusal';


--
-- Name: model_censorship_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.model_censorship_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.model_censorship_id_seq OWNER TO claude;

--
-- Name: model_censorship_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.model_censorship_id_seq OWNED BY learning.model_censorship.id;


--
-- Name: model_censorship_summary; Type: VIEW; Schema: learning; Owner: sfloess
--

CREATE VIEW learning.model_censorship_summary AS
 SELECT censorship_level,
    censorship_rating,
    count(*) AS model_count,
    count(*) FILTER (WHERE (provider = 'local'::text)) AS local_count,
    count(*) FILTER (WHERE (provider <> 'local'::text)) AS cloud_count,
    sum(size_gb) FILTER (WHERE (provider = 'local'::text)) AS total_size_gb,
    round(avg(answer_availability_pct), 1) AS avg_availability_pct,
    array_agg(DISTINCT category) AS categories
   FROM learning.model_censorship
  GROUP BY censorship_level, censorship_rating
  ORDER BY censorship_level DESC;


ALTER VIEW learning.model_censorship_summary OWNER TO sfloess;

--
-- Name: pdf_knowledge; Type: TABLE; Schema: learning; Owner: sfloess
--

CREATE TABLE learning.pdf_knowledge (
    id integer NOT NULL,
    pdf_path text,
    category text,
    claim text NOT NULL,
    embedding public.vector(768),
    confidence double precision,
    verified_by text[],
    source_page integer,
    created_at timestamp without time zone DEFAULT now(),
    metadata jsonb
);


ALTER TABLE learning.pdf_knowledge OWNER TO sfloess;

--
-- Name: pdf_knowledge_id_seq; Type: SEQUENCE; Schema: learning; Owner: sfloess
--

CREATE SEQUENCE learning.pdf_knowledge_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.pdf_knowledge_id_seq OWNER TO sfloess;

--
-- Name: pdf_knowledge_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: sfloess
--

ALTER SEQUENCE learning.pdf_knowledge_id_seq OWNED BY learning.pdf_knowledge.id;


--
-- Name: pdf_metadata; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.pdf_metadata (
    id integer NOT NULL,
    pdf_path text NOT NULL,
    text_length integer,
    text_preview text,
    processed_at timestamp without time zone DEFAULT now(),
    embedding public.vector(768)
);


ALTER TABLE learning.pdf_metadata OWNER TO claude;

--
-- Name: pdf_metadata_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.pdf_metadata_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.pdf_metadata_id_seq OWNER TO claude;

--
-- Name: pdf_metadata_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.pdf_metadata_id_seq OWNED BY learning.pdf_metadata.id;


--
-- Name: policy_performance; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.policy_performance (
    policy_id text NOT NULL,
    alpha double precision DEFAULT 1.0,
    beta double precision DEFAULT 1.0,
    successes integer DEFAULT 0,
    failures integer DEFAULT 0,
    total_reward double precision DEFAULT 0.0,
    avg_reward double precision DEFAULT 0.0,
    last_updated timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.policy_performance OWNER TO claude;

--
-- Name: preference_learner_stats; Type: TABLE; Schema: learning; Owner: sfloess
--

CREATE TABLE learning.preference_learner_stats (
    model_name character varying NOT NULL,
    num_models integer,
    context_dim integer,
    alpha double precision,
    training_records integer,
    test_accuracy double precision,
    avg_train_reward double precision,
    avg_test_reward double precision,
    model_path character varying,
    trained_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.preference_learner_stats OWNER TO sfloess;

--
-- Name: procedural_rules; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.procedural_rules (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    condition_hash text NOT NULL,
    condition jsonb NOT NULL,
    action text NOT NULL,
    confidence double precision NOT NULL,
    evidence_count integer DEFAULT 1,
    last_updated timestamp with time zone DEFAULT now(),
    CONSTRAINT procedural_rules_confidence_check CHECK (((confidence >= (0.0)::double precision) AND (confidence <= (1.0)::double precision)))
);


ALTER TABLE learning.procedural_rules OWNER TO claude;

--
-- Name: queue_failure_patterns; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.queue_failure_patterns (
    id integer NOT NULL,
    queue_type text NOT NULL,
    error_type text NOT NULL,
    error_fingerprint text,
    document_characteristics jsonb,
    failure_rate numeric(5,3),
    avg_retries_to_success numeric(5,2),
    success_after_retry_rate numeric(5,3),
    common_features jsonb,
    recommended_action text,
    confidence numeric(5,3),
    sample_count integer DEFAULT 0,
    last_seen timestamp without time zone,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    CONSTRAINT queue_failure_patterns_queue_type_check CHECK ((queue_type = ANY (ARRAY['chunk'::text, 'embed'::text, 'graph'::text, 'store'::text])))
);


ALTER TABLE learning.queue_failure_patterns OWNER TO claude;

--
-- Name: queue_failure_patterns_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.queue_failure_patterns_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.queue_failure_patterns_id_seq OWNER TO claude;

--
-- Name: queue_failure_patterns_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.queue_failure_patterns_id_seq OWNED BY learning.queue_failure_patterns.id;


--
-- Name: queue_health_metrics; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.queue_health_metrics (
    id integer NOT NULL,
    queue_type text NOT NULL,
    "timestamp" timestamp without time zone DEFAULT now(),
    pending_count integer,
    processing_count integer,
    error_count integer,
    dead_letter_count integer,
    completed_count integer,
    avg_processing_time_ms integer,
    p95_processing_time_ms integer,
    success_rate numeric(5,3),
    retry_rate numeric(5,3),
    throughput_per_min numeric(10,2),
    oldest_pending_age_sec integer,
    oldest_processing_age_sec integer,
    stuck_items_count integer,
    zombie_items_count integer,
    health_score numeric(5,3),
    alert_level text,
    recommendations jsonb,
    CONSTRAINT queue_health_metrics_alert_level_check CHECK ((alert_level = ANY (ARRAY['ok'::text, 'warning'::text, 'critical'::text]))),
    CONSTRAINT queue_health_metrics_queue_type_check CHECK ((queue_type = ANY (ARRAY['chunk'::text, 'embed'::text, 'graph'::text, 'store'::text])))
);


ALTER TABLE learning.queue_health_metrics OWNER TO claude;

--
-- Name: queue_health_metrics_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.queue_health_metrics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.queue_health_metrics_id_seq OWNER TO claude;

--
-- Name: queue_health_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.queue_health_metrics_id_seq OWNED BY learning.queue_health_metrics.id;


--
-- Name: queue_predictions; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.queue_predictions (
    id integer NOT NULL,
    queue_type text NOT NULL,
    queue_item_id integer NOT NULL,
    document_id uuid,
    predicted_success_prob numeric(5,3),
    predicted_retry_count integer,
    predicted_duration_ms integer,
    predicted_error_type text,
    recommendation text,
    features_used jsonb,
    model_version text DEFAULT 'v1.0'::text,
    actual_outcome text,
    actual_retries integer,
    actual_duration_ms integer,
    actual_error_type text,
    prediction_error numeric(10,3),
    prediction_correct boolean,
    created_at timestamp without time zone DEFAULT now(),
    completed_at timestamp without time zone,
    CONSTRAINT queue_predictions_queue_type_check CHECK ((queue_type = ANY (ARRAY['chunk'::text, 'embed'::text, 'graph'::text, 'store'::text])))
);


ALTER TABLE learning.queue_predictions OWNER TO claude;

--
-- Name: queue_predictions_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.queue_predictions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.queue_predictions_id_seq OWNER TO claude;

--
-- Name: queue_predictions_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.queue_predictions_id_seq OWNED BY learning.queue_predictions.id;


--
-- Name: chunk; Type: TABLE; Schema: queue; Owner: postgres
--

CREATE TABLE queue.chunk (
    id integer NOT NULL,
    document_id uuid NOT NULL,
    priority integer DEFAULT 5,
    status text DEFAULT 'pending'::text,
    retries integer DEFAULT 0,
    error text,
    created_at timestamp without time zone DEFAULT now(),
    started_at timestamp without time zone,
    completed_at timestamp without time zone,
    file_path text,
    idempotency_key text,
    worker_id text,
    chunk_text text
);


ALTER TABLE queue.chunk OWNER TO postgres;

--
-- Name: embed; Type: TABLE; Schema: queue; Owner: postgres
--

CREATE TABLE queue.embed (
    id integer NOT NULL,
    document_id uuid NOT NULL,
    chunk_ids uuid[],
    priority integer DEFAULT 5,
    status text DEFAULT 'pending'::text,
    retries integer DEFAULT 0,
    error text,
    created_at timestamp without time zone DEFAULT now(),
    started_at timestamp without time zone,
    completed_at timestamp without time zone,
    file_path text,
    idempotency_key text,
    worker_id text
);


ALTER TABLE queue.embed OWNER TO postgres;

--
-- Name: graph; Type: TABLE; Schema: queue; Owner: postgres
--

CREATE TABLE queue.graph (
    id integer NOT NULL,
    document_id uuid NOT NULL,
    priority integer DEFAULT 3,
    status text DEFAULT 'pending'::text,
    retries integer DEFAULT 0,
    error text,
    created_at timestamp without time zone DEFAULT now(),
    started_at timestamp without time zone,
    completed_at timestamp without time zone,
    chunk_text text,
    file_path text,
    idempotency_key text,
    worker_id text
);


ALTER TABLE queue.graph OWNER TO postgres;

--
-- Name: store; Type: TABLE; Schema: queue; Owner: postgres
--

CREATE TABLE queue.store (
    id integer NOT NULL,
    data jsonb NOT NULL,
    priority integer DEFAULT 5,
    status text DEFAULT 'pending'::text,
    retries integer DEFAULT 0,
    error text,
    created_at timestamp without time zone DEFAULT now(),
    started_at timestamp without time zone,
    completed_at timestamp without time zone,
    document_id uuid,
    file_path text,
    idempotency_key text,
    worker_id text
);


ALTER TABLE queue.store OWNER TO postgres;

--
-- Name: queue_status_summary; Type: MATERIALIZED VIEW; Schema: learning; Owner: claude
--

CREATE MATERIALIZED VIEW learning.queue_status_summary AS
 SELECT 'chunk'::text AS queue_type,
    (sum(
        CASE
            WHEN (chunk.status = 'pending'::text) THEN 1
            ELSE 0
        END))::integer AS pending,
    (sum(
        CASE
            WHEN (chunk.status = 'processing'::text) THEN 1
            ELSE 0
        END))::integer AS processing,
    (sum(
        CASE
            WHEN (chunk.status = 'error'::text) THEN 1
            ELSE 0
        END))::integer AS errors,
    (sum(
        CASE
            WHEN (chunk.status = 'dead_letter'::text) THEN 1
            ELSE 0
        END))::integer AS dead_letter,
    (sum(
        CASE
            WHEN (chunk.status = 'completed'::text) THEN 1
            ELSE 0
        END))::integer AS completed,
    (avg(
        CASE
            WHEN (chunk.status = 'completed'::text) THEN (EXTRACT(epoch FROM (chunk.completed_at - chunk.started_at)) * (1000)::numeric)
            ELSE NULL::numeric
        END))::integer AS avg_duration_ms,
    (sum(
        CASE
            WHEN ((chunk.status = 'pending'::text) AND (chunk.created_at < (now() - '01:00:00'::interval))) THEN 1
            ELSE 0
        END))::integer AS stuck,
    (sum(
        CASE
            WHEN ((chunk.status = 'processing'::text) AND (chunk.started_at < (now() - '00:05:00'::interval))) THEN 1
            ELSE 0
        END))::integer AS zombies,
    now() AS last_updated
   FROM queue.chunk
UNION ALL
 SELECT 'graph'::text AS queue_type,
    (sum(
        CASE
            WHEN (graph.status = 'pending'::text) THEN 1
            ELSE 0
        END))::integer AS pending,
    (sum(
        CASE
            WHEN (graph.status = 'processing'::text) THEN 1
            ELSE 0
        END))::integer AS processing,
    (sum(
        CASE
            WHEN (graph.status = 'error'::text) THEN 1
            ELSE 0
        END))::integer AS errors,
    (sum(
        CASE
            WHEN (graph.status = 'dead_letter'::text) THEN 1
            ELSE 0
        END))::integer AS dead_letter,
    (sum(
        CASE
            WHEN (graph.status = 'completed'::text) THEN 1
            ELSE 0
        END))::integer AS completed,
    (avg(
        CASE
            WHEN (graph.status = 'completed'::text) THEN (EXTRACT(epoch FROM (graph.completed_at - graph.started_at)) * (1000)::numeric)
            ELSE NULL::numeric
        END))::integer AS avg_duration_ms,
    (sum(
        CASE
            WHEN ((graph.status = 'pending'::text) AND (graph.created_at < (now() - '01:00:00'::interval))) THEN 1
            ELSE 0
        END))::integer AS stuck,
    (sum(
        CASE
            WHEN ((graph.status = 'processing'::text) AND (graph.started_at < (now() - '00:05:00'::interval))) THEN 1
            ELSE 0
        END))::integer AS zombies,
    now() AS last_updated
   FROM queue.graph
UNION ALL
 SELECT 'embed'::text AS queue_type,
    (sum(
        CASE
            WHEN (embed.status = 'pending'::text) THEN 1
            ELSE 0
        END))::integer AS pending,
    (sum(
        CASE
            WHEN (embed.status = 'processing'::text) THEN 1
            ELSE 0
        END))::integer AS processing,
    (sum(
        CASE
            WHEN (embed.status = 'error'::text) THEN 1
            ELSE 0
        END))::integer AS errors,
    (sum(
        CASE
            WHEN (embed.status = 'dead_letter'::text) THEN 1
            ELSE 0
        END))::integer AS dead_letter,
    (sum(
        CASE
            WHEN (embed.status = 'completed'::text) THEN 1
            ELSE 0
        END))::integer AS completed,
    (avg(
        CASE
            WHEN (embed.status = 'completed'::text) THEN (EXTRACT(epoch FROM (embed.completed_at - embed.started_at)) * (1000)::numeric)
            ELSE NULL::numeric
        END))::integer AS avg_duration_ms,
    (sum(
        CASE
            WHEN ((embed.status = 'pending'::text) AND (embed.created_at < (now() - '01:00:00'::interval))) THEN 1
            ELSE 0
        END))::integer AS stuck,
    (sum(
        CASE
            WHEN ((embed.status = 'processing'::text) AND (embed.started_at < (now() - '00:05:00'::interval))) THEN 1
            ELSE 0
        END))::integer AS zombies,
    now() AS last_updated
   FROM queue.embed
UNION ALL
 SELECT 'store'::text AS queue_type,
    (sum(
        CASE
            WHEN (store.status = 'pending'::text) THEN 1
            ELSE 0
        END))::integer AS pending,
    (sum(
        CASE
            WHEN (store.status = 'processing'::text) THEN 1
            ELSE 0
        END))::integer AS processing,
    (sum(
        CASE
            WHEN (store.status = 'error'::text) THEN 1
            ELSE 0
        END))::integer AS errors,
    (sum(
        CASE
            WHEN (store.status = 'dead_letter'::text) THEN 1
            ELSE 0
        END))::integer AS dead_letter,
    (sum(
        CASE
            WHEN (store.status = 'completed'::text) THEN 1
            ELSE 0
        END))::integer AS completed,
    (avg(
        CASE
            WHEN (store.status = 'completed'::text) THEN (EXTRACT(epoch FROM (store.completed_at - store.started_at)) * (1000)::numeric)
            ELSE NULL::numeric
        END))::integer AS avg_duration_ms,
    (sum(
        CASE
            WHEN ((store.status = 'pending'::text) AND (store.created_at < (now() - '01:00:00'::interval))) THEN 1
            ELSE 0
        END))::integer AS stuck,
    (sum(
        CASE
            WHEN ((store.status = 'processing'::text) AND (store.started_at < (now() - '00:05:00'::interval))) THEN 1
            ELSE 0
        END))::integer AS zombies,
    now() AS last_updated
   FROM queue.store
  WITH NO DATA;


ALTER MATERIALIZED VIEW learning.queue_status_summary OWNER TO claude;

--
-- Name: reasoning_patterns; Type: TABLE; Schema: learning; Owner: sfloess
--

CREATE TABLE learning.reasoning_patterns (
    id integer NOT NULL,
    problem_description text NOT NULL,
    problem_category character varying(100) NOT NULL,
    consensus_threshold numeric(3,2) NOT NULL,
    models_used integer NOT NULL,
    successful_approach text NOT NULL,
    common_reasoning_steps jsonb NOT NULL,
    error_patterns_to_avoid jsonb NOT NULL,
    pattern_confidence numeric(3,2) NOT NULL,
    examples jsonb,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.reasoning_patterns OWNER TO sfloess;

--
-- Name: reasoning_patterns_id_seq; Type: SEQUENCE; Schema: learning; Owner: sfloess
--

CREATE SEQUENCE learning.reasoning_patterns_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.reasoning_patterns_id_seq OWNER TO sfloess;

--
-- Name: reasoning_patterns_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: sfloess
--

ALTER SEQUENCE learning.reasoning_patterns_id_seq OWNED BY learning.reasoning_patterns.id;


--
-- Name: relationships; Type: TABLE; Schema: learning; Owner: postgres
--

CREATE TABLE learning.relationships (
    id integer NOT NULL,
    from_concept_id integer,
    to_concept_id integer,
    relationship_type text,
    strength double precision DEFAULT 0.5,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.relationships OWNER TO postgres;

--
-- Name: relationships_id_seq; Type: SEQUENCE; Schema: learning; Owner: postgres
--

CREATE SEQUENCE learning.relationships_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.relationships_id_seq OWNER TO postgres;

--
-- Name: relationships_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: postgres
--

ALTER SEQUENCE learning.relationships_id_seq OWNED BY learning.relationships.id;


--
-- Name: request_history_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.request_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.request_history_id_seq OWNER TO claude;

--
-- Name: request_history_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.request_history_id_seq OWNED BY learning.request_history.id;


--
-- Name: research_chunks; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.research_chunks (
    id integer NOT NULL,
    doc_id text NOT NULL,
    chunk_index integer NOT NULL,
    chunk_text text NOT NULL,
    chunk_embedding public.vector(768),
    page_number integer,
    created_at timestamp without time zone DEFAULT now(),
    content_hash character varying(64),
    access_count integer DEFAULT 1,
    last_accessed timestamp without time zone DEFAULT now(),
    chunk_type text,
    priority text,
    discovery_method text,
    confidence_score double precision,
    verification_status text,
    cost_usd double precision,
    duration_ms integer,
    error_message text,
    retry_count integer DEFAULT 0,
    parent_chunk_id integer,
    child_chunk_ids integer[],
    models_involved text[],
    domain_tags text[],
    components_used text[],
    semantic_topics text[],
    entity_mentions text[],
    code_snippets text[],
    external_references text[],
    valid_from timestamp without time zone DEFAULT now(),
    valid_to timestamp without time zone DEFAULT 'infinity'::timestamp without time zone,
    chunk_text_ts tsvector,
    information_density double precision,
    structural_position jsonb DEFAULT '{}'::jsonb,
    claim_assertions jsonb DEFAULT '[]'::jsonb,
    retrieval_feedback jsonb DEFAULT '{"times_useful": 0, "last_feedback": null, "times_retrieved": 0, "times_irrelevant": 0}'::jsonb,
    source_document_id text,
    temporal_context jsonb DEFAULT '{}'::jsonb,
    CONSTRAINT research_chunks_confidence_score_check CHECK (((confidence_score >= (0)::double precision) AND (confidence_score <= (1)::double precision))),
    CONSTRAINT research_chunks_information_density_check CHECK (((information_density >= (0.0)::double precision) AND (information_density <= (1.0)::double precision))),
    CONSTRAINT research_chunks_priority_check CHECK ((priority = ANY (ARRAY['critical'::text, 'high'::text, 'medium'::text, 'low'::text])))
);


ALTER TABLE learning.research_chunks OWNER TO claude;

--
-- Name: TABLE research_chunks; Type: COMMENT; Schema: learning; Owner: claude
--

COMMENT ON TABLE learning.research_chunks IS 'Chunked research content for semantic search';


--
-- Name: research_chunks_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.research_chunks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.research_chunks_id_seq OWNER TO claude;

--
-- Name: research_chunks_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.research_chunks_id_seq OWNED BY learning.research_chunks.id;


--
-- Name: research_documents; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.research_documents (
    id integer NOT NULL,
    doc_id text NOT NULL,
    doc_path text NOT NULL,
    title text,
    doc_type text,
    created_at timestamp without time zone DEFAULT now(),
    metadata jsonb
);


ALTER TABLE learning.research_documents OWNER TO claude;

--
-- Name: TABLE research_documents; Type: COMMENT; Schema: learning; Owner: claude
--

COMMENT ON TABLE learning.research_documents IS 'Deep research PDFs and documents';


--
-- Name: research_documents_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.research_documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.research_documents_id_seq OWNER TO claude;

--
-- Name: research_documents_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.research_documents_id_seq OWNED BY learning.research_documents.id;


--
-- Name: research_findings; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.research_findings (
    id integer NOT NULL,
    workflow_id text,
    workflow_name text,
    chunk_index integer,
    document text,
    embedding public.vector(768),
    metadata jsonb,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.research_findings OWNER TO claude;

--
-- Name: research_findings_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.research_findings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.research_findings_id_seq OWNER TO claude;

--
-- Name: research_findings_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.research_findings_id_seq OWNED BY learning.research_findings.id;


--
-- Name: research_full; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.research_full (
    id integer NOT NULL,
    finding_id text,
    query text,
    chunk_text text NOT NULL,
    chunk_index integer,
    total_chunks integer,
    embedding public.vector(768) NOT NULL,
    embedding_model text,
    embedding_dim integer,
    relevance_score double precision,
    top_result jsonb,
    execution_metadata jsonb,
    "timestamp" timestamp without time zone,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.research_full OWNER TO claude;

--
-- Name: research_full_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.research_full_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.research_full_id_seq OWNER TO claude;

--
-- Name: research_full_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.research_full_id_seq OWNED BY learning.research_full.id;


--
-- Name: scraping_queue; Type: TABLE; Schema: learning; Owner: postgres
--

CREATE TABLE learning.scraping_queue (
    id integer NOT NULL,
    topic text NOT NULL,
    priority double precision DEFAULT 0.5 NOT NULL,
    status text DEFAULT 'pending'::text,
    source text,
    examples_found integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT now(),
    started_at timestamp without time zone,
    completed_at timestamp without time zone
);


ALTER TABLE learning.scraping_queue OWNER TO postgres;

--
-- Name: TABLE scraping_queue; Type: COMMENT; Schema: learning; Owner: postgres
--

COMMENT ON TABLE learning.scraping_queue IS 'Topics that need more training data';


--
-- Name: scraping_queue_id_seq; Type: SEQUENCE; Schema: learning; Owner: postgres
--

CREATE SEQUENCE learning.scraping_queue_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.scraping_queue_id_seq OWNER TO postgres;

--
-- Name: scraping_queue_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: postgres
--

ALTER SEQUENCE learning.scraping_queue_id_seq OWNED BY learning.scraping_queue.id;


--
-- Name: security_policies; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.security_policies (
    id integer NOT NULL,
    policy_id text NOT NULL,
    policy_name text NOT NULL,
    owasp_category text,
    severity text,
    pattern text NOT NULL,
    pattern_type text DEFAULT 'regex'::text,
    description text,
    embedding public.vector(768),
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    times_triggered integer DEFAULT 0,
    true_positives integer DEFAULT 0,
    false_positives integer DEFAULT 0,
    "precision" double precision DEFAULT 0.0,
    active boolean DEFAULT true
);


ALTER TABLE learning.security_policies OWNER TO claude;

--
-- Name: security_policies_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.security_policies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.security_policies_id_seq OWNER TO claude;

--
-- Name: security_policies_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.security_policies_id_seq OWNED BY learning.security_policies.id;


--
-- Name: security_violations; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.security_violations (
    id integer NOT NULL,
    violation_id text NOT NULL,
    policy_id text,
    file_path text NOT NULL,
    line_number integer,
    code_snippet text,
    severity text,
    fixed boolean DEFAULT false,
    fix_applied text,
    embedding public.vector(768),
    detected_at timestamp without time zone DEFAULT now(),
    fixed_at timestamp without time zone,
    metadata jsonb
);


ALTER TABLE learning.security_violations OWNER TO claude;

--
-- Name: security_violations_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.security_violations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.security_violations_id_seq OWNER TO claude;

--
-- Name: security_violations_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.security_violations_id_seq OWNED BY learning.security_violations.id;


--
-- Name: self_discoveries; Type: TABLE; Schema: learning; Owner: postgres
--

CREATE TABLE learning.self_discoveries (
    id integer NOT NULL,
    question text NOT NULL,
    uncertainty_score double precision NOT NULL,
    topic text,
    queued_for_scraping boolean DEFAULT false,
    "timestamp" timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.self_discoveries OWNER TO postgres;

--
-- Name: TABLE self_discoveries; Type: COMMENT; Schema: learning; Owner: postgres
--

COMMENT ON TABLE learning.self_discoveries IS 'Topics discovered during idle exploration';


--
-- Name: self_discoveries_id_seq; Type: SEQUENCE; Schema: learning; Owner: postgres
--

CREATE SEQUENCE learning.self_discoveries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.self_discoveries_id_seq OWNER TO postgres;

--
-- Name: self_discoveries_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: postgres
--

ALTER SEQUENCE learning.self_discoveries_id_seq OWNED BY learning.self_discoveries.id;


--
-- Name: service_mesh_models; Type: TABLE; Schema: learning; Owner: sfloess
--

CREATE TABLE learning.service_mesh_models (
    model_name character varying NOT NULL,
    category_accuracy double precision,
    category_f1 double precision,
    mesh_accuracy double precision,
    mesh_f1 double precision,
    training_examples integer,
    feature_count integer,
    model_path character varying,
    metadata jsonb,
    trained_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.service_mesh_models OWNER TO sfloess;

--
-- Name: session_chunks; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.session_chunks (
    id integer NOT NULL,
    session_id text NOT NULL,
    chunk_index integer NOT NULL,
    chunk_text text NOT NULL,
    chunk_embedding public.vector(768),
    created_at timestamp without time zone DEFAULT now(),
    content_hash character varying(64),
    access_count integer DEFAULT 1,
    last_accessed timestamp without time zone DEFAULT now(),
    metadata jsonb DEFAULT '{}'::jsonb,
    session_date date,
    temporal_validity tstzrange,
    model text,
    workflow text,
    task_type text,
    cwd text,
    git_branch text,
    tools_used text[],
    message_count integer,
    has_code boolean DEFAULT false,
    has_error boolean DEFAULT false,
    topics text[],
    entities text[],
    quality_score double precision,
    information_density double precision,
    structural_position jsonb DEFAULT '{}'::jsonb,
    claim_assertions jsonb DEFAULT '[]'::jsonb,
    retrieval_feedback jsonb DEFAULT '{"times_useful": 0, "last_feedback": null, "times_retrieved": 0, "times_irrelevant": 0}'::jsonb,
    source_document_id text,
    temporal_context jsonb DEFAULT '{}'::jsonb,
    latency_ms integer,
    input_tokens integer,
    output_tokens integer,
    cache_hit boolean DEFAULT false,
    cost_usd numeric(10,6),
    similarity_score double precision,
    retrieval_rank integer,
    search_query_hash character varying(64),
    retrieval_count integer DEFAULT 0,
    last_retrieved timestamp without time zone,
    prompt_version character varying(64),
    model_version character varying(64),
    api_endpoint text,
    tenant_id text,
    user_id text,
    access_permissions text[],
    contains_pii boolean DEFAULT false,
    data_classification text DEFAULT 'internal'::text,
    keywords text[],
    language character varying(10) DEFAULT 'en'::character varying,
    document_type text,
    error_type text,
    retry_count integer DEFAULT 0,
    success_on_retry boolean,
    feedback_score integer,
    char_count integer,
    word_count integer,
    token_count integer,
    summary text,
    source_url text,
    parent_chunk_id integer,
    conversation_thread_id text,
    embedding_model text,
    is_system_message boolean DEFAULT false,
    is_user_message boolean DEFAULT false,
    message_role text,
    experiment_id text,
    ab_test_variant text,
    log_level text DEFAULT 'INFO'::text,
    request_id text,
    trace_id text,
    recovery_attempts integer DEFAULT 0,
    resource_utilization jsonb DEFAULT '{}'::jsonb,
    cost_allocation text,
    pricing_tier text,
    relevance_score double precision,
    result_ranking integer,
    data_retention_days integer,
    data_encryption_method text,
    session_duration_ms integer,
    model_accuracy double precision,
    model_precision double precision,
    model_recall double precision,
    model_f1_score double precision,
    data_lineage jsonb DEFAULT '{}'::jsonb,
    model_drift_score double precision,
    concept_drift_score double precision,
    data_drift_score double precision,
    explainability_data jsonb DEFAULT '{}'::jsonb,
    feature_importance jsonb DEFAULT '{}'::jsonb,
    gdpr_compliant boolean DEFAULT true,
    hipaa_compliant boolean DEFAULT false,
    ccpa_compliant boolean DEFAULT true,
    anonymization_applied boolean DEFAULT false,
    audit_log jsonb DEFAULT '[]'::jsonb,
    model_update_timestamp timestamp without time zone,
    model_changelog text,
    user_consent jsonb DEFAULT '{}'::jsonb,
    user_preferences jsonb DEFAULT '{}'::jsonb,
    incident_response_time_ms integer,
    incident_resolution_status text,
    root_cause_analysis text,
    user_query_text text,
    llm_response_text text,
    retrieved_chunk_texts text[],
    retrieved_chunk_sources jsonb DEFAULT '[]'::jsonb,
    retrieved_vector_ids integer[],
    request_start_timestamp timestamp without time zone,
    request_end_timestamp timestamp without time zone,
    user_feedback_text text,
    input_data_hash character varying(64),
    output_data_hash character varying(64),
    model_input_parameters jsonb DEFAULT '{}'::jsonb,
    inference_engine_metrics jsonb DEFAULT '{}'::jsonb,
    data_source_info jsonb DEFAULT '{}'::jsonb,
    user_feedback_timestamp timestamp without time zone,
    authentication_method text,
    access_token_hash character varying(64),
    data_deletion_status text,
    system_resource_utilization jsonb DEFAULT '{}'::jsonb,
    system_error_rate double precision,
    model_training_data_version text,
    final_llm_prompt_text text,
    retrieval_strategy_used text,
    tool_invocation_details jsonb DEFAULT '[]'::jsonb,
    retrieval_timestamp timestamp without time zone,
    retrieval_method text,
    vector_store_id text,
    error_message text,
    error_stack_trace text,
    data_consistency_score double precision,
    data_coverage_score double precision,
    client_ip_address inet,
    client_location jsonb DEFAULT '{}'::jsonb,
    business_process_id text,
    business_entity_id text,
    device_type text,
    browser_type text,
    operating_system text,
    screen_resolution text,
    time_zone text,
    locale text,
    data_validation_status text,
    entity_relationships jsonb DEFAULT '{}'::jsonb,
    CONSTRAINT session_chunks_information_density_check CHECK (((information_density >= (0.0)::double precision) AND (information_density <= (1.0)::double precision)))
);


ALTER TABLE learning.session_chunks OWNER TO claude;

--
-- Name: session_chunks_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.session_chunks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.session_chunks_id_seq OWNER TO claude;

--
-- Name: session_chunks_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.session_chunks_id_seq OWNED BY learning.session_chunks.id;


--
-- Name: sessions; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.sessions (
    id integer NOT NULL,
    session_id text NOT NULL,
    session_path text NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone DEFAULT now(),
    title text,
    summary text,
    full_content text,
    message_count integer,
    metadata jsonb,
    title_embedding public.vector(768),
    summary_embedding public.vector(768),
    content_embedding public.vector(768)
);


ALTER TABLE learning.sessions OWNER TO claude;

--
-- Name: sessions_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.sessions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.sessions_id_seq OWNER TO claude;

--
-- Name: sessions_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.sessions_id_seq OWNED BY learning.sessions.id;


--
-- Name: specialist_models; Type: TABLE; Schema: learning; Owner: sfloess
--

CREATE TABLE learning.specialist_models (
    model_name character varying NOT NULL,
    model_type character varying,
    accuracy double precision,
    f1_score double precision,
    training_samples integer,
    categories text[],
    model_path character varying,
    vectorizer_path character varying,
    trained_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.specialist_models OWNER TO sfloess;

--
-- Name: strategy_performance; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.strategy_performance (
    strategy text NOT NULL,
    successes integer DEFAULT 0,
    failures integer DEFAULT 0,
    alpha double precision DEFAULT 1.0,
    beta double precision DEFAULT 1.0,
    total_reward double precision DEFAULT 0.0,
    avg_reward double precision DEFAULT 0.0,
    last_updated timestamp with time zone DEFAULT now()
);


ALTER TABLE learning.strategy_performance OWNER TO claude;

--
-- Name: strategy_performance_multi; Type: TABLE; Schema: learning; Owner: sfloess
--

CREATE TABLE learning.strategy_performance_multi (
    id integer NOT NULL,
    capability character varying(255) NOT NULL,
    task_type character varying(255) NOT NULL,
    strategy character varying(255) NOT NULL,
    alpha numeric(10,2) DEFAULT 1.0,
    beta numeric(10,2) DEFAULT 1.0,
    successes integer DEFAULT 0,
    failures integer DEFAULT 0,
    total_reward numeric(10,4) DEFAULT 0,
    updated_at timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT strategy_performance_multi_alpha_check CHECK ((alpha > (0)::numeric)),
    CONSTRAINT strategy_performance_multi_beta_check CHECK ((beta > (0)::numeric)),
    CONSTRAINT strategy_performance_multi_check CHECK (((successes >= 0) AND (failures >= 0)))
);


ALTER TABLE learning.strategy_performance_multi OWNER TO sfloess;

--
-- Name: strategy_performance_multi_id_seq; Type: SEQUENCE; Schema: learning; Owner: sfloess
--

CREATE SEQUENCE learning.strategy_performance_multi_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.strategy_performance_multi_id_seq OWNER TO sfloess;

--
-- Name: strategy_performance_multi_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: sfloess
--

ALTER SEQUENCE learning.strategy_performance_multi_id_seq OWNED BY learning.strategy_performance_multi.id;


--
-- Name: test_results; Type: TABLE; Schema: learning; Owner: sfloess
--

CREATE TABLE learning.test_results (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    test_suite text NOT NULL,
    total_tests integer,
    passed integer,
    failed integer,
    skipped integer,
    duration_ms integer,
    failures jsonb,
    "timestamp" timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE learning.test_results OWNER TO sfloess;

--
-- Name: ucb1_arms; Type: TABLE; Schema: learning; Owner: postgres
--

CREATE TABLE learning.ucb1_arms (
    arm_id text NOT NULL,
    total_reward double precision NOT NULL,
    n integer NOT NULL,
    mean_reward double precision NOT NULL,
    c double precision NOT NULL,
    last_updated timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.ucb1_arms OWNER TO postgres;

--
-- Name: ucb1_state; Type: TABLE; Schema: learning; Owner: postgres
--

CREATE TABLE learning.ucb1_state (
    key text NOT NULL,
    value double precision NOT NULL,
    last_updated timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.ucb1_state OWNER TO postgres;

--
-- Name: uncensored_models; Type: VIEW; Schema: learning; Owner: sfloess
--

CREATE VIEW learning.uncensored_models AS
 SELECT model_name,
    provider,
    location,
    size_gb,
    answer_availability_pct,
    category,
    specialization,
    status,
    daily_limit,
    notes
   FROM learning.model_censorship
  WHERE (censorship_level = 5)
  ORDER BY
        CASE
            WHEN (provider = 'local'::text) THEN 0
            ELSE 1
        END, size_gb DESC NULLS LAST;


ALTER VIEW learning.uncensored_models OWNER TO sfloess;

--
-- Name: vec_claude_memory; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.vec_claude_memory (
    id text NOT NULL,
    document text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb,
    embedding public.vector(768),
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.vec_claude_memory OWNER TO claude;

--
-- Name: vec_scale_test_1783055901; Type: TABLE; Schema: learning; Owner: sfloess
--

CREATE TABLE learning.vec_scale_test_1783055901 (
    id text NOT NULL,
    document text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb,
    embedding public.vector(768),
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.vec_scale_test_1783055901 OWNER TO sfloess;

--
-- Name: vec_scale_test_1783055962; Type: TABLE; Schema: learning; Owner: sfloess
--

CREATE TABLE learning.vec_scale_test_1783055962 (
    id text NOT NULL,
    document text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb,
    embedding public.vector(768),
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.vec_scale_test_1783055962 OWNER TO sfloess;

--
-- Name: vec_scale_test_1783055991; Type: TABLE; Schema: learning; Owner: sfloess
--

CREATE TABLE learning.vec_scale_test_1783055991 (
    id text NOT NULL,
    document text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb,
    embedding public.vector(768),
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.vec_scale_test_1783055991 OWNER TO sfloess;

--
-- Name: vec_scale_test_1783056573; Type: TABLE; Schema: learning; Owner: sfloess
--

CREATE TABLE learning.vec_scale_test_1783056573 (
    id text NOT NULL,
    document text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb,
    embedding public.vector(768),
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.vec_scale_test_1783056573 OWNER TO sfloess;

--
-- Name: weak_topics; Type: TABLE; Schema: learning; Owner: postgres
--

CREATE TABLE learning.weak_topics (
    topic text NOT NULL,
    avg_quality double precision NOT NULL,
    examples_scraped integer DEFAULT 0,
    last_fine_tune timestamp without time zone,
    status text DEFAULT 'identified'::text,
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE learning.weak_topics OWNER TO postgres;

--
-- Name: TABLE weak_topics; Type: COMMENT; Schema: learning; Owner: postgres
--

COMMENT ON TABLE learning.weak_topics IS 'Current model weaknesses';


--
-- Name: web_synthesis; Type: TABLE; Schema: learning; Owner: claude
--

CREATE TABLE learning.web_synthesis (
    id integer NOT NULL,
    source_line integer NOT NULL,
    batch_id integer NOT NULL,
    worker_id integer NOT NULL,
    processed_at timestamp with time zone DEFAULT now(),
    content jsonb NOT NULL
);


ALTER TABLE learning.web_synthesis OWNER TO claude;

--
-- Name: web_synthesis_id_seq; Type: SEQUENCE; Schema: learning; Owner: claude
--

CREATE SEQUENCE learning.web_synthesis_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE learning.web_synthesis_id_seq OWNER TO claude;

--
-- Name: web_synthesis_id_seq; Type: SEQUENCE OWNED BY; Schema: learning; Owner: claude
--

ALTER SEQUENCE learning.web_synthesis_id_seq OWNED BY learning.web_synthesis.id;


--
-- Name: api_health_checks; Type: TABLE; Schema: monitoring; Owner: sfloess
--

CREATE TABLE monitoring.api_health_checks (
    id integer NOT NULL,
    provider character varying(100) NOT NULL,
    success boolean NOT NULL,
    response_time_ms integer,
    error_message text,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE monitoring.api_health_checks OWNER TO sfloess;

--
-- Name: api_health_checks_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: sfloess
--

CREATE SEQUENCE monitoring.api_health_checks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.api_health_checks_id_seq OWNER TO sfloess;

--
-- Name: api_health_checks_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: sfloess
--

ALTER SEQUENCE monitoring.api_health_checks_id_seq OWNED BY monitoring.api_health_checks.id;


--
-- Name: api_health_status; Type: TABLE; Schema: monitoring; Owner: sfloess
--

CREATE TABLE monitoring.api_health_status (
    provider character varying(100) NOT NULL,
    success_rate numeric(5,4) DEFAULT 1.0 NOT NULL,
    total_checks integer DEFAULT 0 NOT NULL,
    successful_checks integer DEFAULT 0 NOT NULL,
    failed_checks integer DEFAULT 0 NOT NULL,
    status character varying(20) DEFAULT 'healthy'::character varying NOT NULL,
    last_check timestamp with time zone,
    last_success timestamp with time zone,
    last_failure timestamp with time zone,
    failure_reason text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    metadata jsonb DEFAULT '{}'::jsonb
);


ALTER TABLE monitoring.api_health_status OWNER TO sfloess;

--
-- Name: api_usage; Type: TABLE; Schema: monitoring; Owner: sfloess
--

CREATE TABLE monitoring.api_usage (
    id bigint NOT NULL,
    api_key_id uuid NOT NULL,
    endpoint character varying(200) NOT NULL,
    method character varying(10) NOT NULL,
    status_code integer NOT NULL,
    duration_ms integer,
    file_size_bytes bigint,
    chunks_processed integer,
    embeddings_generated integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE monitoring.api_usage OWNER TO sfloess;

--
-- Name: api_usage_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: sfloess
--

CREATE SEQUENCE monitoring.api_usage_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.api_usage_id_seq OWNER TO sfloess;

--
-- Name: api_usage_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: sfloess
--

ALTER SEQUENCE monitoring.api_usage_id_seq OWNED BY monitoring.api_usage.id;


--
-- Name: arbiter_decisions; Type: TABLE; Schema: monitoring; Owner: postgres
--

CREATE TABLE monitoring.arbiter_decisions (
    id integer NOT NULL,
    task_id character varying(100),
    arbiter_model character varying(100),
    decision text,
    confidence numeric(3,2),
    response_time_ms integer,
    cost_usd numeric(10,6),
    "timestamp" timestamp with time zone DEFAULT now()
);


ALTER TABLE monitoring.arbiter_decisions OWNER TO postgres;

--
-- Name: arbiter_decisions_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: postgres
--

CREATE SEQUENCE monitoring.arbiter_decisions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.arbiter_decisions_id_seq OWNER TO postgres;

--
-- Name: arbiter_decisions_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: postgres
--

ALTER SEQUENCE monitoring.arbiter_decisions_id_seq OWNED BY monitoring.arbiter_decisions.id;


--
-- Name: circuit_breaker_events; Type: TABLE; Schema: monitoring; Owner: sfloess
--

CREATE TABLE monitoring.circuit_breaker_events (
    id integer NOT NULL,
    model character varying(100),
    event character varying(20),
    reason text,
    consecutive_failures integer,
    total_failures integer,
    total_successes integer,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE monitoring.circuit_breaker_events OWNER TO sfloess;

--
-- Name: circuit_breaker_events_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: sfloess
--

CREATE SEQUENCE monitoring.circuit_breaker_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.circuit_breaker_events_id_seq OWNER TO sfloess;

--
-- Name: circuit_breaker_events_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: sfloess
--

ALTER SEQUENCE monitoring.circuit_breaker_events_id_seq OWNED BY monitoring.circuit_breaker_events.id;


--
-- Name: compliance_alerts; Type: TABLE; Schema: monitoring; Owner: claude
--

CREATE TABLE monitoring.compliance_alerts (
    id integer NOT NULL,
    task_type text NOT NULL,
    model_attempted text NOT NULL,
    violation_type text NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now(),
    severity text DEFAULT 'CRITICAL'::text,
    resolved boolean DEFAULT false
);


ALTER TABLE monitoring.compliance_alerts OWNER TO claude;

--
-- Name: compliance_alerts_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: claude
--

CREATE SEQUENCE monitoring.compliance_alerts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.compliance_alerts_id_seq OWNER TO claude;

--
-- Name: compliance_alerts_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: claude
--

ALTER SEQUENCE monitoring.compliance_alerts_id_seq OWNED BY monitoring.compliance_alerts.id;


--
-- Name: confidence_calibration; Type: TABLE; Schema: monitoring; Owner: claude
--

CREATE TABLE monitoring.confidence_calibration (
    id integer NOT NULL,
    worker_result_id integer,
    model character varying(100) NOT NULL,
    task_type character varying(100),
    predicted_confidence numeric(5,4) NOT NULL,
    actual_correctness numeric(5,4),
    calibration_error numeric(5,4),
    overconfident boolean,
    underconfident boolean,
    metadata jsonb,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE monitoring.confidence_calibration OWNER TO claude;

--
-- Name: confidence_calibration_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: claude
--

CREATE SEQUENCE monitoring.confidence_calibration_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.confidence_calibration_id_seq OWNER TO claude;

--
-- Name: confidence_calibration_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: claude
--

ALTER SEQUENCE monitoring.confidence_calibration_id_seq OWNED BY monitoring.confidence_calibration.id;


--
-- Name: health_predictions; Type: TABLE; Schema: monitoring; Owner: claude
--

CREATE TABLE monitoring.health_predictions (
    id integer NOT NULL,
    hostname text NOT NULL,
    degradation_probability real NOT NULL,
    primary_risk text,
    time_to_failure_hours real,
    validated_probability real,
    validation_confidence real,
    decision_action text,
    decision_urgency text,
    evidence jsonb,
    reasoning text,
    predicted_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT health_predictions_degradation_probability_check CHECK (((degradation_probability >= (0.0)::double precision) AND (degradation_probability <= (1.0)::double precision))),
    CONSTRAINT health_predictions_validated_probability_check CHECK (((validated_probability IS NULL) OR ((validated_probability >= (0.0)::double precision) AND (validated_probability <= (1.0)::double precision)))),
    CONSTRAINT health_predictions_validation_confidence_check CHECK (((validation_confidence IS NULL) OR ((validation_confidence >= (0.0)::double precision) AND (validation_confidence <= (1.0)::double precision)))),
    CONSTRAINT valid_decision_action CHECK ((decision_action = ANY (ARRAY['migrate_immediately'::text, 'schedule_migration'::text, 'monitor_closely'::text, 'no_action'::text, 'error'::text, 'no_prediction'::text]))),
    CONSTRAINT valid_decision_urgency CHECK ((decision_urgency = ANY (ARRAY['critical'::text, 'high'::text, 'medium'::text, 'low'::text, 'unknown'::text]))),
    CONSTRAINT valid_primary_risk CHECK ((primary_risk = ANY (ARRAY['memory_leak'::text, 'cpu_thermal'::text, 'disk_saturation'::text, 'load_spike'::text, 'none'::text, 'unknown'::text, 'error'::text])))
);


ALTER TABLE monitoring.health_predictions OWNER TO claude;

--
-- Name: TABLE health_predictions; Type: COMMENT; Schema: monitoring; Owner: claude
--

COMMENT ON TABLE monitoring.health_predictions IS 'AI-based predictive server failure detection results from fleet-health-predictor (Issue #108)';


--
-- Name: latest_health_predictions; Type: VIEW; Schema: monitoring; Owner: claude
--

CREATE VIEW monitoring.latest_health_predictions AS
 SELECT DISTINCT ON (hostname) hostname,
    degradation_probability,
    primary_risk,
    time_to_failure_hours,
    validated_probability,
    validation_confidence,
    decision_action,
    decision_urgency,
    predicted_at,
        CASE
            WHEN (degradation_probability >= (0.95)::double precision) THEN 'failing'::text
            WHEN (degradation_probability >= (0.85)::double precision) THEN 'critical'::text
            WHEN (degradation_probability >= (0.70)::double precision) THEN 'degraded'::text
            WHEN (degradation_probability >= (0.50)::double precision) THEN 'at_risk'::text
            ELSE 'healthy'::text
        END AS health_status
   FROM monitoring.health_predictions
  ORDER BY hostname, predicted_at DESC;


ALTER VIEW monitoring.latest_health_predictions OWNER TO claude;

--
-- Name: VIEW latest_health_predictions; Type: COMMENT; Schema: monitoring; Owner: claude
--

COMMENT ON VIEW monitoring.latest_health_predictions IS 'Latest prediction for each server with derived health_status';


--
-- Name: degraded_servers; Type: VIEW; Schema: monitoring; Owner: claude
--

CREATE VIEW monitoring.degraded_servers AS
 SELECT hostname,
    degradation_probability,
    primary_risk,
    time_to_failure_hours,
    validated_probability,
    validation_confidence,
    decision_action,
    decision_urgency,
    predicted_at,
    health_status
   FROM monitoring.latest_health_predictions
  WHERE (degradation_probability >= (0.70)::double precision)
  ORDER BY degradation_probability DESC;


ALTER VIEW monitoring.degraded_servers OWNER TO claude;

--
-- Name: VIEW degraded_servers; Type: COMMENT; Schema: monitoring; Owner: claude
--

COMMENT ON VIEW monitoring.degraded_servers IS 'Servers requiring action (degradation >= 70%)';


--
-- Name: diversity_alerts; Type: TABLE; Schema: monitoring; Owner: sfloess
--

CREATE TABLE monitoring.diversity_alerts (
    id integer NOT NULL,
    model text NOT NULL,
    percentage numeric(5,2) NOT NULL,
    threshold numeric(5,2) NOT NULL,
    window_size integer NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE monitoring.diversity_alerts OWNER TO sfloess;

--
-- Name: diversity_alerts_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: sfloess
--

CREATE SEQUENCE monitoring.diversity_alerts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.diversity_alerts_id_seq OWNER TO sfloess;

--
-- Name: diversity_alerts_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: sfloess
--

ALTER SEQUENCE monitoring.diversity_alerts_id_seq OWNED BY monitoring.diversity_alerts.id;


--
-- Name: document_stats; Type: MATERIALIZED VIEW; Schema: monitoring; Owner: sfloess
--

CREATE MATERIALIZED VIEW monitoring.document_stats AS
 SELECT file_type,
    status,
    count(*) AS document_count,
    sum(file_size_bytes) AS total_size_bytes,
    avg(EXTRACT(epoch FROM (processing_completed_at - processing_started_at))) AS avg_processing_seconds
   FROM documents.documents
  GROUP BY file_type, status
  WITH NO DATA;


ALTER MATERIALIZED VIEW monitoring.document_stats OWNER TO sfloess;

--
-- Name: dual_review_results; Type: TABLE; Schema: monitoring; Owner: postgres
--

CREATE TABLE monitoring.dual_review_results (
    id integer NOT NULL,
    review_id character varying(100),
    review_1_workers text[],
    review_1_arbiter character varying(100),
    potential_issues_count integer,
    review_2_workers text[],
    review_2_arbiter character varying(100),
    confirmed_issues_count integer,
    false_positives_count integer,
    false_positive_rate numeric(5,2),
    confirmation_rate numeric(5,2),
    repo_name character varying(200),
    "timestamp" timestamp with time zone DEFAULT now(),
    reviews_needed integer,
    consensus_score numeric(5,2),
    confirmed_after_2 integer,
    false_positives_after_2 integer,
    review_3_workers text[],
    review_3_arbiter character varying(100),
    final_confirmed integer,
    fixes_attempted integer,
    fixes_succeeded integer,
    fixes_failed_verification integer,
    worktrees_created text[]
);


ALTER TABLE monitoring.dual_review_results OWNER TO postgres;

--
-- Name: dual_review_results_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: postgres
--

CREATE SEQUENCE monitoring.dual_review_results_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.dual_review_results_id_seq OWNER TO postgres;

--
-- Name: dual_review_results_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: postgres
--

ALTER SEQUENCE monitoring.dual_review_results_id_seq OWNED BY monitoring.dual_review_results.id;


--
-- Name: embedding_provider_usage; Type: TABLE; Schema: monitoring; Owner: postgres
--

CREATE TABLE monitoring.embedding_provider_usage (
    id integer NOT NULL,
    provider character varying(50) NOT NULL,
    success boolean NOT NULL,
    response_time_ms integer,
    embedding_dim integer,
    error_type character varying(100),
    "timestamp" timestamp without time zone DEFAULT now()
);


ALTER TABLE monitoring.embedding_provider_usage OWNER TO postgres;

--
-- Name: embedding_provider_usage_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: postgres
--

CREATE SEQUENCE monitoring.embedding_provider_usage_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.embedding_provider_usage_id_seq OWNER TO postgres;

--
-- Name: embedding_provider_usage_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: postgres
--

ALTER SEQUENCE monitoring.embedding_provider_usage_id_seq OWNED BY monitoring.embedding_provider_usage.id;


--
-- Name: execution_log; Type: TABLE; Schema: monitoring; Owner: sfloess
--

CREATE TABLE monitoring.execution_log (
    id integer NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL,
    model text NOT NULL,
    model_role text DEFAULT 'worker'::text NOT NULL,
    workflow text,
    task_type text,
    phase text,
    label text,
    parameters jsonb DEFAULT '{}'::jsonb,
    quality_score real,
    confidence real,
    consensus_score real,
    was_selected boolean DEFAULT false,
    input_tokens integer DEFAULT 0,
    output_tokens integer DEFAULT 0,
    cost_usd real DEFAULT 0.0,
    duration_ms integer DEFAULT 0,
    outcome text DEFAULT 'unknown'::text,
    outcome_notes text,
    request_hash text,
    response_hash text,
    error text,
    run_id text,
    execution_id text,
    task_description text,
    worker_models jsonb DEFAULT '[]'::jsonb,
    arbiter_model text,
    model_count integer DEFAULT 1,
    strategy text,
    diversity_score real,
    total_input_tokens integer DEFAULT 0,
    total_output_tokens integer DEFAULT 0,
    total_cost_usd real DEFAULT 0.0,
    per_model_costs jsonb DEFAULT '{}'::jsonb,
    per_model_durations jsonb DEFAULT '{}'::jsonb,
    selected_model text,
    session_id text,
    parent_execution_id text,
    counterfactual_scores jsonb DEFAULT '{}'::jsonb,
    selection_method text DEFAULT 'static'::text
);


ALTER TABLE monitoring.execution_log OWNER TO sfloess;

--
-- Name: execution_log_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: sfloess
--

CREATE SEQUENCE monitoring.execution_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.execution_log_id_seq OWNER TO sfloess;

--
-- Name: execution_log_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: sfloess
--

ALTER SEQUENCE monitoring.execution_log_id_seq OWNED BY monitoring.execution_log.id;


--
-- Name: execution_summary; Type: TABLE; Schema: monitoring; Owner: sfloess
--

CREATE TABLE monitoring.execution_summary (
    id integer NOT NULL,
    "timestamp" timestamp with time zone,
    model text,
    workflow text,
    task_type text,
    quality_score real,
    input_tokens integer,
    output_tokens integer,
    cost_usd real,
    duration_ms integer,
    outcome text,
    metadata jsonb,
    circuit_breaker_state character varying(32) DEFAULT 'closed'::character varying
);


ALTER TABLE monitoring.execution_summary OWNER TO sfloess;

--
-- Name: execution_summary_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: sfloess
--

CREATE SEQUENCE monitoring.execution_summary_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.execution_summary_id_seq OWNER TO sfloess;

--
-- Name: execution_summary_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: sfloess
--

ALTER SEQUENCE monitoring.execution_summary_id_seq OWNED BY monitoring.execution_summary.id;


--
-- Name: external_api_calls; Type: TABLE; Schema: monitoring; Owner: claude
--

CREATE TABLE monitoring.external_api_calls (
    id integer NOT NULL,
    service character varying(50) NOT NULL,
    worker_id character varying(100) NOT NULL,
    method character varying(10) NOT NULL,
    path text NOT NULL,
    status_code integer,
    response_time_ms integer,
    cached boolean DEFAULT false,
    error text,
    cost_usd numeric(10,6) DEFAULT 0,
    "timestamp" timestamp without time zone DEFAULT now()
);


ALTER TABLE monitoring.external_api_calls OWNER TO claude;

--
-- Name: TABLE external_api_calls; Type: COMMENT; Schema: monitoring; Owner: claude
--

COMMENT ON TABLE monitoring.external_api_calls IS 'Tracks all external API calls proxied through aio-01 for metrics, costs, and rate limiting';


--
-- Name: external_api_calls_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: claude
--

CREATE SEQUENCE monitoring.external_api_calls_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.external_api_calls_id_seq OWNER TO claude;

--
-- Name: external_api_calls_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: claude
--

ALTER SEQUENCE monitoring.external_api_calls_id_seq OWNED BY monitoring.external_api_calls.id;


--
-- Name: external_api_summary; Type: MATERIALIZED VIEW; Schema: monitoring; Owner: claude
--

CREATE MATERIALIZED VIEW monitoring.external_api_summary AS
 SELECT service,
    date("timestamp") AS date,
    count(*) AS total_calls,
    count(*) FILTER (WHERE (cached = true)) AS cached_calls,
    count(*) FILTER (WHERE (status_code >= 400)) AS error_calls,
    avg(response_time_ms) AS avg_response_time_ms,
    percentile_cont((0.5)::double precision) WITHIN GROUP (ORDER BY ((response_time_ms)::double precision)) AS p50_response_time_ms,
    percentile_cont((0.95)::double precision) WITHIN GROUP (ORDER BY ((response_time_ms)::double precision)) AS p95_response_time_ms,
    sum(cost_usd) AS total_cost_usd
   FROM monitoring.external_api_calls
  WHERE ("timestamp" > (now() - '30 days'::interval))
  GROUP BY service, (date("timestamp"))
  WITH NO DATA;


ALTER MATERIALIZED VIEW monitoring.external_api_summary OWNER TO claude;

--
-- Name: fleet_health; Type: TABLE; Schema: monitoring; Owner: sfloess
--

CREATE TABLE monitoring.fleet_health (
    id integer NOT NULL,
    hostname text NOT NULL,
    status text NOT NULL,
    last_seen timestamp with time zone DEFAULT now() NOT NULL,
    response_time_ms bigint,
    available_models jsonb,
    cpu_load numeric(5,2),
    ram_used_mb integer,
    ram_total_mb integer,
    disk_used_gb integer,
    disk_total_gb integer,
    error_message text,
    CONSTRAINT fleet_health_status_check CHECK ((status = ANY (ARRAY['up'::text, 'down'::text, 'degraded'::text])))
);


ALTER TABLE monitoring.fleet_health OWNER TO sfloess;

--
-- Name: fleet_health_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: sfloess
--

CREATE SEQUENCE monitoring.fleet_health_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.fleet_health_id_seq OWNER TO sfloess;

--
-- Name: fleet_health_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: sfloess
--

ALTER SEQUENCE monitoring.fleet_health_id_seq OWNED BY monitoring.fleet_health.id;


--
-- Name: health_checks; Type: TABLE; Schema: monitoring; Owner: claude
--

CREATE TABLE monitoring.health_checks (
    id integer NOT NULL,
    worker_id text NOT NULL,
    status text NOT NULL,
    response_time_ms integer,
    error_message text,
    checked_at timestamp without time zone DEFAULT now()
);


ALTER TABLE monitoring.health_checks OWNER TO claude;

--
-- Name: health_checks_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: claude
--

CREATE SEQUENCE monitoring.health_checks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.health_checks_id_seq OWNER TO claude;

--
-- Name: health_checks_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: claude
--

ALTER SEQUENCE monitoring.health_checks_id_seq OWNED BY monitoring.health_checks.id;


--
-- Name: health_predictions_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: claude
--

CREATE SEQUENCE monitoring.health_predictions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.health_predictions_id_seq OWNER TO claude;

--
-- Name: health_predictions_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: claude
--

ALTER SEQUENCE monitoring.health_predictions_id_seq OWNED BY monitoring.health_predictions.id;


--
-- Name: human_corrections; Type: TABLE; Schema: monitoring; Owner: claude
--

CREATE TABLE monitoring.human_corrections (
    id integer NOT NULL,
    workflow_execution_id integer,
    worker_result_id integer,
    model character varying(100) NOT NULL,
    task_type character varying(100),
    original_output text NOT NULL,
    corrected_output text NOT NULL,
    correction_type character varying(50),
    severity character varying(20),
    corrector character varying(100),
    metadata jsonb,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE monitoring.human_corrections OWNER TO claude;

--
-- Name: human_correction_summary; Type: MATERIALIZED VIEW; Schema: monitoring; Owner: claude
--

CREATE MATERIALIZED VIEW monitoring.human_correction_summary AS
 SELECT model,
    correction_type,
    count(*) AS total_corrections,
    count(*) FILTER (WHERE ((severity)::text = 'critical'::text)) AS critical_corrections,
    count(*) FILTER (WHERE ((severity)::text = 'major'::text)) AS major_corrections,
    count(*) FILTER (WHERE ((severity)::text = 'minor'::text)) AS minor_corrections,
    avg(length(original_output)) AS avg_original_length,
    avg(length(corrected_output)) AS avg_corrected_length
   FROM monitoring.human_corrections
  GROUP BY model, correction_type
  WITH NO DATA;


ALTER MATERIALIZED VIEW monitoring.human_correction_summary OWNER TO claude;

--
-- Name: human_corrections_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: claude
--

CREATE SEQUENCE monitoring.human_corrections_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.human_corrections_id_seq OWNER TO claude;

--
-- Name: human_corrections_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: claude
--

ALTER SEQUENCE monitoring.human_corrections_id_seq OWNED BY monitoring.human_corrections.id;


--
-- Name: llm_provider_usage; Type: TABLE; Schema: monitoring; Owner: postgres
--

CREATE TABLE monitoring.llm_provider_usage (
    id integer NOT NULL,
    provider character varying(50) NOT NULL,
    model character varying(100),
    task_type character varying(50),
    success boolean NOT NULL,
    failure_reason character varying(100),
    response_time_ms integer,
    cost_usd numeric(10,6),
    "timestamp" timestamp with time zone DEFAULT now()
);


ALTER TABLE monitoring.llm_provider_usage OWNER TO postgres;

--
-- Name: llm_provider_usage_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: postgres
--

CREATE SEQUENCE monitoring.llm_provider_usage_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.llm_provider_usage_id_seq OWNER TO postgres;

--
-- Name: llm_provider_usage_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: postgres
--

ALTER SEQUENCE monitoring.llm_provider_usage_id_seq OWNED BY monitoring.llm_provider_usage.id;


--
-- Name: task_attribution; Type: TABLE; Schema: monitoring; Owner: claude
--

CREATE TABLE monitoring.task_attribution (
    id integer NOT NULL,
    workflow_execution_id integer,
    final_output_hash character varying(64) NOT NULL,
    worker_result_id integer,
    model character varying(100) NOT NULL,
    contribution_type character varying(50),
    contribution_percentage numeric(5,2),
    arbiter_reasoning text,
    metadata jsonb,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE monitoring.task_attribution OWNER TO claude;

--
-- Name: model_attribution_summary; Type: MATERIALIZED VIEW; Schema: monitoring; Owner: claude
--

CREATE MATERIALIZED VIEW monitoring.model_attribution_summary AS
 SELECT model,
    contribution_type,
    count(*) AS total_attributions,
    avg(contribution_percentage) AS avg_contribution_pct,
    count(DISTINCT workflow_execution_id) AS workflows_contributed
   FROM monitoring.task_attribution
  GROUP BY model, contribution_type
  WITH NO DATA;


ALTER MATERIALIZED VIEW monitoring.model_attribution_summary OWNER TO claude;

--
-- Name: model_capabilities; Type: TABLE; Schema: monitoring; Owner: sfloess
--

CREATE TABLE monitoring.model_capabilities (
    id integer NOT NULL,
    model text NOT NULL,
    task_type text NOT NULL,
    capability_score numeric(5,4) NOT NULL,
    executions integer DEFAULT 0,
    avg_quality numeric(5,4),
    stddev_quality numeric(5,4),
    min_quality numeric(5,4),
    max_quality numeric(5,4),
    baseline_score numeric(5,4),
    last_updated timestamp without time zone DEFAULT now(),
    CONSTRAINT model_capabilities_capability_score_check CHECK (((capability_score >= 0.0) AND (capability_score <= 1.0))),
    CONSTRAINT model_capabilities_executions_check CHECK ((executions >= 0))
);


ALTER TABLE monitoring.model_capabilities OWNER TO sfloess;

--
-- Name: TABLE model_capabilities; Type: COMMENT; Schema: monitoring; Owner: sfloess
--

COMMENT ON TABLE monitoring.model_capabilities IS 'Example queries:

-- Top models for code_review
SELECT model, capability_score, executions
FROM monitoring.model_capabilities
WHERE task_type = ''code_review''
ORDER BY capability_score DESC
LIMIT 5;

-- Models with high confidence (100+ executions)
SELECT model, task_type, capability_score, monitoring.capability_confidence(executions) AS confidence
FROM monitoring.model_capabilities
WHERE executions >= 100
ORDER BY capability_score DESC;

-- Model performance across all tasks
SELECT
  model,
  COUNT(*) AS num_tasks,
  AVG(capability_score) AS avg_score,
  SUM(executions) AS total_executions
FROM monitoring.model_capabilities
GROUP BY model
ORDER BY avg_score DESC;

-- Tasks with low model coverage
SELECT task_type, COUNT(*) AS num_models
FROM monitoring.model_capabilities
GROUP BY task_type
HAVING COUNT(*) < 3
ORDER BY num_models;
';


--
-- Name: model_capabilities_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: sfloess
--

CREATE SEQUENCE monitoring.model_capabilities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.model_capabilities_id_seq OWNER TO sfloess;

--
-- Name: model_capabilities_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: sfloess
--

ALTER SEQUENCE monitoring.model_capabilities_id_seq OWNED BY monitoring.model_capabilities.id;


--
-- Name: model_capabilities_top; Type: MATERIALIZED VIEW; Schema: monitoring; Owner: sfloess
--

CREATE MATERIALIZED VIEW monitoring.model_capabilities_top AS
 SELECT DISTINCT ON (task_type) task_type,
    array_agg(model ORDER BY capability_score DESC) FILTER (WHERE (capability_score >= 0.7)) AS top_models,
    array_agg(capability_score ORDER BY capability_score DESC) FILTER (WHERE (capability_score >= 0.7)) AS top_scores,
    max(last_updated) AS last_updated
   FROM monitoring.model_capabilities
  GROUP BY task_type
  WITH NO DATA;


ALTER MATERIALIZED VIEW monitoring.model_capabilities_top OWNER TO sfloess;

--
-- Name: MATERIALIZED VIEW model_capabilities_top; Type: COMMENT; Schema: monitoring; Owner: sfloess
--

COMMENT ON MATERIALIZED VIEW monitoring.model_capabilities_top IS 'Pre-computed top models per task type (refreshed on updates)';


--
-- Name: model_capabilities_with_confidence; Type: VIEW; Schema: monitoring; Owner: sfloess
--

CREATE VIEW monitoring.model_capabilities_with_confidence AS
 SELECT model,
    task_type,
    capability_score,
    monitoring.capability_confidence(executions) AS confidence,
    executions,
    avg_quality,
    stddev_quality,
    last_updated,
        CASE
            WHEN (executions < 10) THEN 'low_sample'::text
            WHEN (executions < 50) THEN 'moderate_sample'::text
            WHEN (executions < 100) THEN 'good_sample'::text
            ELSE 'high_sample'::text
        END AS confidence_level
   FROM monitoring.model_capabilities;


ALTER VIEW monitoring.model_capabilities_with_confidence OWNER TO sfloess;

--
-- Name: VIEW model_capabilities_with_confidence; Type: COMMENT; Schema: monitoring; Owner: sfloess
--

COMMENT ON VIEW monitoring.model_capabilities_with_confidence IS 'Model capabilities augmented with confidence scores and levels';


--
-- Name: model_retraining; Type: TABLE; Schema: monitoring; Owner: sfloess
--

CREATE TABLE monitoring.model_retraining (
    id integer NOT NULL,
    model_name character varying(255) NOT NULL,
    model_type character varying(50),
    old_accuracy double precision,
    new_accuracy double precision,
    accuracy_metric character varying(50),
    training_samples integer,
    test_samples integer,
    old_r2 double precision,
    new_r2 double precision,
    old_rmse double precision,
    new_rmse double precision,
    training_duration_seconds double precision,
    result character varying(50),
    notes text,
    created_at timestamp without time zone DEFAULT now(),
    created_by character varying(255)
);


ALTER TABLE monitoring.model_retraining OWNER TO sfloess;

--
-- Name: model_retraining_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: sfloess
--

CREATE SEQUENCE monitoring.model_retraining_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.model_retraining_id_seq OWNER TO sfloess;

--
-- Name: model_retraining_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: sfloess
--

ALTER SEQUENCE monitoring.model_retraining_id_seq OWNED BY monitoring.model_retraining.id;


--
-- Name: model_selections; Type: TABLE; Schema: monitoring; Owner: sfloess
--

CREATE TABLE monitoring.model_selections (
    id integer NOT NULL,
    model text NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE monitoring.model_selections OWNER TO sfloess;

--
-- Name: model_selections_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: sfloess
--

CREATE SEQUENCE monitoring.model_selections_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.model_selections_id_seq OWNER TO sfloess;

--
-- Name: model_selections_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: sfloess
--

ALTER SEQUENCE monitoring.model_selections_id_seq OWNED BY monitoring.model_selections.id;


--
-- Name: model_tuning; Type: TABLE; Schema: monitoring; Owner: sfloess
--

CREATE TABLE monitoring.model_tuning (
    id integer NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    model text NOT NULL,
    task_type text NOT NULL,
    optimal_params jsonb DEFAULT '{}'::jsonb NOT NULL,
    avg_quality real DEFAULT 0.0,
    avg_confidence real DEFAULT 0.0,
    avg_cost_usd real DEFAULT 0.0,
    avg_duration_ms real DEFAULT 0.0,
    sample_count integer DEFAULT 0,
    success_rate real DEFAULT 0.0,
    selection_rate real DEFAULT 0.0,
    quality_trend jsonb DEFAULT '[]'::jsonb,
    cost_trend jsonb DEFAULT '[]'::jsonb
);


ALTER TABLE monitoring.model_tuning OWNER TO sfloess;

--
-- Name: model_tuning_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: sfloess
--

CREATE SEQUENCE monitoring.model_tuning_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.model_tuning_id_seq OWNER TO sfloess;

--
-- Name: model_tuning_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: sfloess
--

ALTER SEQUENCE monitoring.model_tuning_id_seq OWNED BY monitoring.model_tuning.id;


--
-- Name: model_usage; Type: TABLE; Schema: monitoring; Owner: claude
--

CREATE TABLE monitoring.model_usage (
    id integer NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL,
    model text NOT NULL,
    task_type text,
    filter_reason text,
    pool jsonb,
    pool_source text,
    rules_applied jsonb,
    workflow text,
    context text,
    anthropic_only boolean DEFAULT false,
    whitelist jsonb,
    blacklist jsonb
);


ALTER TABLE monitoring.model_usage OWNER TO claude;

--
-- Name: model_usage_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: claude
--

CREATE SEQUENCE monitoring.model_usage_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.model_usage_id_seq OWNER TO claude;

--
-- Name: model_usage_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: claude
--

ALTER SEQUENCE monitoring.model_usage_id_seq OWNED BY monitoring.model_usage.id;


--
-- Name: model_usage_stats_24h; Type: VIEW; Schema: monitoring; Owner: claude
--

CREATE VIEW monitoring.model_usage_stats_24h AS
 SELECT model,
    task_type,
    count(*) AS usage_count,
    count(*) FILTER (WHERE (anthropic_only = true)) AS anthropic_only_count,
    round((avg(
        CASE
            WHEN anthropic_only THEN 1
            ELSE 0
        END) * (100)::numeric), 1) AS anthropic_only_pct,
    min("timestamp") AS first_used,
    max("timestamp") AS last_used
   FROM monitoring.model_usage
  WHERE ("timestamp" > (now() - '24:00:00'::interval))
  GROUP BY model, task_type
  ORDER BY (count(*)) DESC;


ALTER VIEW monitoring.model_usage_stats_24h OWNER TO claude;

--
-- Name: network_latency_matrix; Type: TABLE; Schema: monitoring; Owner: claude
--

CREATE TABLE monitoring.network_latency_matrix (
    id integer NOT NULL,
    source_host character varying(100) NOT NULL,
    destination_host character varying(100) NOT NULL,
    latency_ms numeric(10,2) NOT NULL,
    packet_loss_percent numeric(5,2) DEFAULT 0,
    jitter_ms numeric(10,2),
    measured_at timestamp without time zone DEFAULT now(),
    measurement_method character varying(50) DEFAULT 'ping'::character varying
);


ALTER TABLE monitoring.network_latency_matrix OWNER TO claude;

--
-- Name: network_latency_matrix_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: claude
--

CREATE SEQUENCE monitoring.network_latency_matrix_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.network_latency_matrix_id_seq OWNER TO claude;

--
-- Name: network_latency_matrix_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: claude
--

ALTER SEQUENCE monitoring.network_latency_matrix_id_seq OWNED BY monitoring.network_latency_matrix.id;


--
-- Name: network_measurements; Type: TABLE; Schema: monitoring; Owner: sfloess
--

CREATE TABLE monitoring.network_measurements (
    id integer NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL,
    source_node text NOT NULL,
    target_node text NOT NULL,
    ping_latency_ms real,
    ssh_latency_ms real,
    packet_loss_percent real,
    hour_of_day integer,
    day_of_week integer,
    cpu_load numeric,
    ram_used_percent real,
    concurrent_tasks integer,
    metadata jsonb
);


ALTER TABLE monitoring.network_measurements OWNER TO sfloess;

--
-- Name: network_measurements_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: sfloess
--

CREATE SEQUENCE monitoring.network_measurements_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.network_measurements_id_seq OWNER TO sfloess;

--
-- Name: network_measurements_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: sfloess
--

ALTER SEQUENCE monitoring.network_measurements_id_seq OWNED BY monitoring.network_measurements.id;


--
-- Name: network_predictions; Type: TABLE; Schema: monitoring; Owner: sfloess
--

CREATE TABLE monitoring.network_predictions (
    id integer NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL,
    target_node text NOT NULL,
    predicted_latency_ms real NOT NULL,
    confidence_score real,
    model_used text,
    features jsonb,
    actual_latency_ms real,
    prediction_error_ms real
);


ALTER TABLE monitoring.network_predictions OWNER TO sfloess;

--
-- Name: network_predictions_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: sfloess
--

CREATE SEQUENCE monitoring.network_predictions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.network_predictions_id_seq OWNER TO sfloess;

--
-- Name: network_predictions_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: sfloess
--

ALTER SEQUENCE monitoring.network_predictions_id_seq OWNED BY monitoring.network_predictions.id;


--
-- Name: workers; Type: TABLE; Schema: monitoring; Owner: claude
--

CREATE TABLE monitoring.workers (
    id integer NOT NULL,
    hostname character varying(100) NOT NULL,
    ip_address character varying(50) NOT NULL,
    cpu_cores integer,
    memory_mb integer,
    status character varying(20) DEFAULT 'online'::character varying,
    last_heartbeat timestamp with time zone DEFAULT now(),
    cpu_percent numeric(5,2),
    memory_percent numeric(5,2),
    active_scrapers integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE monitoring.workers OWNER TO claude;

--
-- Name: online_workers; Type: VIEW; Schema: monitoring; Owner: postgres
--

CREATE VIEW monitoring.online_workers AS
 SELECT hostname,
    ip_address,
    cpu_cores,
    memory_mb,
    cpu_percent,
    memory_percent,
    active_scrapers,
    last_heartbeat
   FROM monitoring.workers
  WHERE (last_heartbeat > (now() - '00:05:00'::interval))
  ORDER BY cpu_percent;


ALTER VIEW monitoring.online_workers OWNER TO postgres;

--
-- Name: prediction_accuracy; Type: TABLE; Schema: monitoring; Owner: postgres
--

CREATE TABLE monitoring.prediction_accuracy (
    id integer NOT NULL,
    workflow_name text NOT NULL,
    model text NOT NULL,
    task_type text NOT NULL,
    predicted_duration_ms double precision NOT NULL,
    actual_duration_ms double precision NOT NULL,
    predicted_input_tokens integer NOT NULL,
    actual_input_tokens integer NOT NULL,
    predicted_output_tokens integer NOT NULL,
    actual_output_tokens integer NOT NULL,
    predicted_cost_usd double precision NOT NULL,
    actual_cost_usd double precision NOT NULL,
    prediction_error_percent double precision NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    workflow_id character varying(64)
);


ALTER TABLE monitoring.prediction_accuracy OWNER TO postgres;

--
-- Name: prediction_accuracy_by_model; Type: VIEW; Schema: monitoring; Owner: postgres
--

CREATE VIEW monitoring.prediction_accuracy_by_model AS
 SELECT model,
    count(*) AS total_predictions,
    round((avg(prediction_error_percent))::numeric, 2) AS avg_error_pct,
    round((min(prediction_error_percent))::numeric, 2) AS min_error_pct,
    round((max(prediction_error_percent))::numeric, 2) AS max_error_pct,
    count(
        CASE
            WHEN (prediction_error_percent > (50)::double precision) THEN 1
            ELSE NULL::integer
        END) AS high_error_count
   FROM monitoring.prediction_accuracy
  WHERE (created_at > (now() - '7 days'::interval))
  GROUP BY model
  ORDER BY (count(*)) DESC;


ALTER VIEW monitoring.prediction_accuracy_by_model OWNER TO postgres;

--
-- Name: prediction_accuracy_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: postgres
--

CREATE SEQUENCE monitoring.prediction_accuracy_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.prediction_accuracy_id_seq OWNER TO postgres;

--
-- Name: prediction_accuracy_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: postgres
--

ALTER SEQUENCE monitoring.prediction_accuracy_id_seq OWNED BY monitoring.prediction_accuracy.id;


--
-- Name: prediction_health_summary; Type: VIEW; Schema: monitoring; Owner: postgres
--

CREATE VIEW monitoring.prediction_health_summary AS
 SELECT count(DISTINCT model) AS total_models,
    count(*) AS total_predictions,
    round((avg(prediction_error_percent))::numeric, 2) AS overall_avg_error,
    count(
        CASE
            WHEN (prediction_error_percent < (20)::double precision) THEN 1
            ELSE NULL::integer
        END) AS excellent_predictions,
    count(
        CASE
            WHEN ((prediction_error_percent >= (20)::double precision) AND (prediction_error_percent <= (50)::double precision)) THEN 1
            ELSE NULL::integer
        END) AS good_predictions,
    count(
        CASE
            WHEN (prediction_error_percent > (50)::double precision) THEN 1
            ELSE NULL::integer
        END) AS poor_predictions
   FROM monitoring.prediction_accuracy
  WHERE (created_at > (now() - '24:00:00'::interval));


ALTER VIEW monitoring.prediction_health_summary OWNER TO postgres;

--
-- Name: prediction_trends_hourly; Type: VIEW; Schema: monitoring; Owner: postgres
--

CREATE VIEW monitoring.prediction_trends_hourly AS
 SELECT date_trunc('hour'::text, created_at) AS hour,
    count(*) AS predictions,
    round((avg(prediction_error_percent))::numeric, 2) AS avg_error,
    round((avg(actual_cost_usd))::numeric, 4) AS avg_cost
   FROM monitoring.prediction_accuracy
  WHERE (created_at > (now() - '24:00:00'::interval))
  GROUP BY (date_trunc('hour'::text, created_at))
  ORDER BY (date_trunc('hour'::text, created_at)) DESC;


ALTER VIEW monitoring.prediction_trends_hourly OWNER TO postgres;

--
-- Name: queue_health; Type: TABLE; Schema: monitoring; Owner: claude
--

CREATE TABLE monitoring.queue_health (
    id integer NOT NULL,
    queue_name character varying(100) NOT NULL,
    pending_count integer NOT NULL,
    processing_count integer NOT NULL,
    completed_count integer NOT NULL,
    failed_count integer NOT NULL,
    avg_processing_time_ms numeric(10,2),
    oldest_pending_age_seconds integer,
    throughput_per_minute numeric(10,2),
    error_rate numeric(5,4),
    measured_at timestamp without time zone DEFAULT now()
);


ALTER TABLE monitoring.queue_health OWNER TO claude;

--
-- Name: queue_health_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: claude
--

CREATE SEQUENCE monitoring.queue_health_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.queue_health_id_seq OWNER TO claude;

--
-- Name: queue_health_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: claude
--

ALTER SEQUENCE monitoring.queue_health_id_seq OWNED BY monitoring.queue_health.id;


--
-- Name: rate_limit_hits; Type: TABLE; Schema: monitoring; Owner: claude
--

CREATE TABLE monitoring.rate_limit_hits (
    id integer NOT NULL,
    service character varying(50) NOT NULL,
    worker_id character varying(100),
    limit_value integer NOT NULL,
    current_count integer NOT NULL,
    "timestamp" timestamp without time zone DEFAULT now()
);


ALTER TABLE monitoring.rate_limit_hits OWNER TO claude;

--
-- Name: TABLE rate_limit_hits; Type: COMMENT; Schema: monitoring; Owner: claude
--

COMMENT ON TABLE monitoring.rate_limit_hits IS 'Logs rate limit violations for alerting and analysis';


--
-- Name: rate_limit_hits_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: claude
--

CREATE SEQUENCE monitoring.rate_limit_hits_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.rate_limit_hits_id_seq OWNER TO claude;

--
-- Name: rate_limit_hits_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: claude
--

ALTER SEQUENCE monitoring.rate_limit_hits_id_seq OWNED BY monitoring.rate_limit_hits.id;


--
-- Name: rate_limit_requests; Type: TABLE; Schema: monitoring; Owner: sfloess
--

CREATE TABLE monitoring.rate_limit_requests (
    id integer NOT NULL,
    provider character varying(200) NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now(),
    success boolean DEFAULT true,
    metadata jsonb DEFAULT '{}'::jsonb
);


ALTER TABLE monitoring.rate_limit_requests OWNER TO sfloess;

--
-- Name: rate_limit_requests_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: sfloess
--

CREATE SEQUENCE monitoring.rate_limit_requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.rate_limit_requests_id_seq OWNER TO sfloess;

--
-- Name: rate_limit_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: sfloess
--

ALTER SEQUENCE monitoring.rate_limit_requests_id_seq OWNED BY monitoring.rate_limit_requests.id;


--
-- Name: rate_limit_state; Type: TABLE; Schema: monitoring; Owner: sfloess
--

CREATE TABLE monitoring.rate_limit_state (
    api_key_id uuid NOT NULL,
    minute_window timestamp with time zone NOT NULL,
    request_count integer DEFAULT 0 NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE monitoring.rate_limit_state OWNER TO sfloess;

--
-- Name: rate_limits; Type: TABLE; Schema: monitoring; Owner: sfloess
--

CREATE TABLE monitoring.rate_limits (
    provider character varying(200) NOT NULL,
    requests_last_minute integer DEFAULT 0,
    requests_last_hour integer DEFAULT 0,
    last_reset timestamp with time zone DEFAULT now(),
    last_request timestamp with time zone,
    total_requests bigint DEFAULT 0,
    throttled_count integer DEFAULT 0,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE monitoring.rate_limits OWNER TO sfloess;

--
-- Name: resource_estimation_coefficients; Type: TABLE; Schema: monitoring; Owner: claude
--

CREATE TABLE monitoring.resource_estimation_coefficients (
    id integer NOT NULL,
    trained_at timestamp with time zone DEFAULT now(),
    job_count integer NOT NULL,
    coefficients jsonb NOT NULL,
    duration_mae numeric(10,2),
    duration_rmse numeric(10,2),
    ram_mae numeric(5,4),
    ram_rmse numeric(5,4),
    improvement_pct numeric(5,2),
    notes text,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE monitoring.resource_estimation_coefficients OWNER TO claude;

--
-- Name: resource_estimation_coefficients_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: claude
--

CREATE SEQUENCE monitoring.resource_estimation_coefficients_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.resource_estimation_coefficients_id_seq OWNER TO claude;

--
-- Name: resource_estimation_coefficients_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: claude
--

ALTER SEQUENCE monitoring.resource_estimation_coefficients_id_seq OWNED BY monitoring.resource_estimation_coefficients.id;


--
-- Name: resource_estimation_log; Type: TABLE; Schema: monitoring; Owner: claude
--

CREATE TABLE monitoring.resource_estimation_log (
    id integer NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now(),
    prompt_length integer NOT NULL,
    model character varying(255) NOT NULL,
    schema_complexity integer DEFAULT 0,
    job_type character varying(255) NOT NULL,
    estimated_duration integer NOT NULL,
    estimated_ram numeric(5,2) NOT NULL,
    actual_duration integer NOT NULL,
    actual_ram numeric(5,2) NOT NULL,
    duration_error numeric(5,4) NOT NULL,
    ram_error numeric(5,4) NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE monitoring.resource_estimation_log OWNER TO claude;

--
-- Name: resource_estimation_log_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: claude
--

CREATE SEQUENCE monitoring.resource_estimation_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.resource_estimation_log_id_seq OWNER TO claude;

--
-- Name: resource_estimation_log_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: claude
--

ALTER SEQUENCE monitoring.resource_estimation_log_id_seq OWNED BY monitoring.resource_estimation_log.id;


--
-- Name: resource_usage; Type: TABLE; Schema: monitoring; Owner: sfloess
--

CREATE TABLE monitoring.resource_usage (
    id integer NOT NULL,
    workflow_id text NOT NULL,
    workflow_execution_id integer,
    start_time timestamp with time zone NOT NULL,
    end_time timestamp with time zone NOT NULL,
    duration_ms integer NOT NULL,
    peak_memory_mb numeric(10,2) NOT NULL,
    avg_memory_mb numeric(10,2) NOT NULL,
    min_memory_mb numeric(10,2) NOT NULL,
    avg_cpu_percent numeric(5,2) NOT NULL,
    max_cpu_percent numeric(5,2) NOT NULL,
    min_cpu_percent numeric(5,2) NOT NULL,
    sample_count integer NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE monitoring.resource_usage OWNER TO sfloess;

--
-- Name: resource_usage_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: sfloess
--

CREATE SEQUENCE monitoring.resource_usage_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.resource_usage_id_seq OWNER TO sfloess;

--
-- Name: resource_usage_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: sfloess
--

ALTER SEQUENCE monitoring.resource_usage_id_seq OWNED BY monitoring.resource_usage.id;


--
-- Name: scraping_metrics; Type: TABLE; Schema: monitoring; Owner: claude
--

CREATE TABLE monitoring.scraping_metrics (
    id integer NOT NULL,
    "timestamp" timestamp without time zone DEFAULT now(),
    node character varying(50) NOT NULL,
    total_processes integer,
    beast_mode_processes integer,
    git_clone_processes integer,
    scraper_processes integer,
    cpu_usage_percent double precision,
    cpu_idle_percent double precision,
    load_average double precision,
    cores integer
);


ALTER TABLE monitoring.scraping_metrics OWNER TO claude;

--
-- Name: scraping_metrics_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: claude
--

CREATE SEQUENCE monitoring.scraping_metrics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.scraping_metrics_id_seq OWNER TO claude;

--
-- Name: scraping_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: claude
--

ALTER SEQUENCE monitoring.scraping_metrics_id_seq OWNED BY monitoring.scraping_metrics.id;


--
-- Name: scraping_output; Type: TABLE; Schema: monitoring; Owner: claude
--

CREATE TABLE monitoring.scraping_output (
    id integer NOT NULL,
    "timestamp" timestamp without time zone DEFAULT now(),
    category character varying(100),
    file_count integer,
    total_size_mb double precision,
    latest_file_time timestamp without time zone
);


ALTER TABLE monitoring.scraping_output OWNER TO claude;

--
-- Name: scraping_output_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: claude
--

CREATE SEQUENCE monitoring.scraping_output_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.scraping_output_id_seq OWNER TO claude;

--
-- Name: scraping_output_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: claude
--

ALTER SEQUENCE monitoring.scraping_output_id_seq OWNED BY monitoring.scraping_output.id;


--
-- Name: session_learnings; Type: TABLE; Schema: monitoring; Owner: claude
--

CREATE TABLE monitoring.session_learnings (
    id integer NOT NULL,
    session_date date NOT NULL,
    topic text NOT NULL,
    learnings jsonb NOT NULL,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE monitoring.session_learnings OWNER TO claude;

--
-- Name: session_learnings_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: claude
--

CREATE SEQUENCE monitoring.session_learnings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.session_learnings_id_seq OWNER TO claude;

--
-- Name: session_learnings_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: claude
--

ALTER SEQUENCE monitoring.session_learnings_id_seq OWNED BY monitoring.session_learnings.id;


--
-- Name: task_attribution_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: claude
--

CREATE SEQUENCE monitoring.task_attribution_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.task_attribution_id_seq OWNER TO claude;

--
-- Name: task_attribution_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: claude
--

ALTER SEQUENCE monitoring.task_attribution_id_seq OWNED BY monitoring.task_attribution.id;


--
-- Name: training_jobs; Type: TABLE; Schema: monitoring; Owner: claude
--

CREATE TABLE monitoring.training_jobs (
    id integer NOT NULL,
    model_name character varying(255) NOT NULL,
    platform character varying(100) NOT NULL,
    job_id character varying(255),
    task_type character varying(100),
    training_file_path text,
    training_examples integer,
    test_examples integer,
    started_at timestamp without time zone DEFAULT now(),
    completed_at timestamp without time zone,
    duration_seconds numeric,
    estimated_cost_usd numeric(10,4),
    actual_cost_usd numeric(10,4),
    training_accuracy numeric(5,4),
    validation_accuracy numeric(5,4),
    test_accuracy numeric(5,4),
    loss_final numeric,
    base_model character varying(255),
    hyperparameters jsonb,
    status character varying(50) DEFAULT 'queued'::character varying,
    error_message text,
    deployed boolean DEFAULT false,
    deployed_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE monitoring.training_jobs OWNER TO claude;

--
-- Name: training_jobs_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: claude
--

CREATE SEQUENCE monitoring.training_jobs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.training_jobs_id_seq OWNER TO claude;

--
-- Name: training_jobs_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: claude
--

ALTER SEQUENCE monitoring.training_jobs_id_seq OWNED BY monitoring.training_jobs.id;


--
-- Name: worker_assignments; Type: TABLE; Schema: monitoring; Owner: postgres
--

CREATE TABLE monitoring.worker_assignments (
    id integer NOT NULL,
    worker_id character varying(100),
    task_id character varying(100),
    success boolean,
    duration_ms integer,
    "timestamp" timestamp with time zone DEFAULT now()
);


ALTER TABLE monitoring.worker_assignments OWNER TO postgres;

--
-- Name: worker_assignments_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: postgres
--

CREATE SEQUENCE monitoring.worker_assignments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.worker_assignments_id_seq OWNER TO postgres;

--
-- Name: worker_assignments_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: postgres
--

ALTER SEQUENCE monitoring.worker_assignments_id_seq OWNED BY monitoring.worker_assignments.id;


--
-- Name: workers_id_seq; Type: SEQUENCE; Schema: monitoring; Owner: claude
--

CREATE SEQUENCE monitoring.workers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE monitoring.workers_id_seq OWNER TO claude;

--
-- Name: workers_id_seq; Type: SEQUENCE OWNED BY; Schema: monitoring; Owner: claude
--

ALTER SEQUENCE monitoring.workers_id_seq OWNED BY monitoring.workers.id;


--
-- Name: auto_storage; Type: TABLE; Schema: orchestration; Owner: sfloess
--

CREATE TABLE orchestration.auto_storage (
    id integer NOT NULL,
    source_type text NOT NULL,
    source_id text NOT NULL,
    chunk_index integer DEFAULT 0,
    text text,
    embedding public.vector(768),
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE orchestration.auto_storage OWNER TO sfloess;

--
-- Name: auto_storage_id_seq; Type: SEQUENCE; Schema: orchestration; Owner: sfloess
--

CREATE SEQUENCE orchestration.auto_storage_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE orchestration.auto_storage_id_seq OWNER TO sfloess;

--
-- Name: auto_storage_id_seq; Type: SEQUENCE OWNED BY; Schema: orchestration; Owner: sfloess
--

ALTER SEQUENCE orchestration.auto_storage_id_seq OWNED BY orchestration.auto_storage.id;


--
-- Name: conversation_history; Type: TABLE; Schema: orchestration; Owner: sfloess
--

CREATE TABLE orchestration.conversation_history (
    id integer NOT NULL,
    session_id text NOT NULL,
    turn_number integer NOT NULL,
    user_message text,
    assistant_response text,
    tools_used jsonb DEFAULT '[]'::jsonb,
    "timestamp" timestamp with time zone DEFAULT now()
);


ALTER TABLE orchestration.conversation_history OWNER TO sfloess;

--
-- Name: conversation_history_id_seq; Type: SEQUENCE; Schema: orchestration; Owner: sfloess
--

CREATE SEQUENCE orchestration.conversation_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE orchestration.conversation_history_id_seq OWNER TO sfloess;

--
-- Name: conversation_history_id_seq; Type: SEQUENCE OWNED BY; Schema: orchestration; Owner: sfloess
--

ALTER SEQUENCE orchestration.conversation_history_id_seq OWNED BY orchestration.conversation_history.id;


--
-- Name: gitlab_issues; Type: TABLE; Schema: orchestration; Owner: sfloess
--

CREATE TABLE orchestration.gitlab_issues (
    id integer NOT NULL,
    issue_id text NOT NULL,
    repository text,
    title text,
    description text,
    labels text[],
    created_at timestamp with time zone,
    url text
);


ALTER TABLE orchestration.gitlab_issues OWNER TO sfloess;

--
-- Name: gitlab_issues_id_seq; Type: SEQUENCE; Schema: orchestration; Owner: sfloess
--

CREATE SEQUENCE orchestration.gitlab_issues_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE orchestration.gitlab_issues_id_seq OWNER TO sfloess;

--
-- Name: gitlab_issues_id_seq; Type: SEQUENCE OWNED BY; Schema: orchestration; Owner: sfloess
--

ALTER SEQUENCE orchestration.gitlab_issues_id_seq OWNED BY orchestration.gitlab_issues.id;


--
-- Name: task_queue; Type: TABLE; Schema: orchestration; Owner: sfloess
--

CREATE TABLE orchestration.task_queue (
    id integer NOT NULL,
    task_id text NOT NULL,
    task_type text NOT NULL,
    description text NOT NULL,
    embedding public.vector(768),
    assigned_worker text,
    workflow_run_id text,
    status text DEFAULT 'queued'::text NOT NULL,
    priority integer DEFAULT 50,
    depends_on integer[],
    blocks integer[],
    progress_percent integer DEFAULT 0,
    current_phase text,
    phases_total integer,
    phases_completed integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    estimated_duration_ms bigint,
    actual_duration_ms bigint,
    input_tokens bigint DEFAULT 0,
    output_tokens bigint DEFAULT 0,
    cost_usd numeric(10,6) DEFAULT 0,
    metadata jsonb DEFAULT '{}'::jsonb,
    result_path text,
    result_summary text,
    outcome text,
    error_message text
);


ALTER TABLE orchestration.task_queue OWNER TO sfloess;

--
-- Name: queue_summary; Type: MATERIALIZED VIEW; Schema: orchestration; Owner: sfloess
--

CREATE MATERIALIZED VIEW orchestration.queue_summary AS
 SELECT status,
    task_type,
    count(*) AS count,
    avg(progress_percent) AS avg_progress,
    sum(input_tokens) AS total_input_tokens,
    sum(output_tokens) AS total_output_tokens,
    sum(cost_usd) AS total_cost,
    min(created_at) AS oldest_task,
    max(created_at) AS newest_task
   FROM orchestration.task_queue
  GROUP BY status, task_type
  WITH NO DATA;


ALTER MATERIALIZED VIEW orchestration.queue_summary OWNER TO sfloess;

--
-- Name: MATERIALIZED VIEW queue_summary; Type: COMMENT; Schema: orchestration; Owner: sfloess
--

COMMENT ON MATERIALIZED VIEW orchestration.queue_summary IS 'Auto-refresh: */5 * * * * (every 5 minutes)';


--
-- Name: task_dependencies; Type: TABLE; Schema: orchestration; Owner: sfloess
--

CREATE TABLE orchestration.task_dependencies (
    id integer NOT NULL,
    from_task_id text NOT NULL,
    to_task_id text NOT NULL,
    dependency_type text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    metadata jsonb DEFAULT '{}'::jsonb
);


ALTER TABLE orchestration.task_dependencies OWNER TO sfloess;

--
-- Name: task_dependencies_id_seq; Type: SEQUENCE; Schema: orchestration; Owner: sfloess
--

CREATE SEQUENCE orchestration.task_dependencies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE orchestration.task_dependencies_id_seq OWNER TO sfloess;

--
-- Name: task_dependencies_id_seq; Type: SEQUENCE OWNED BY; Schema: orchestration; Owner: sfloess
--

ALTER SEQUENCE orchestration.task_dependencies_id_seq OWNED BY orchestration.task_dependencies.id;


--
-- Name: task_progress_log; Type: TABLE; Schema: orchestration; Owner: sfloess
--

CREATE TABLE orchestration.task_progress_log (
    id integer NOT NULL,
    task_id text NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now(),
    phase text,
    message text,
    progress_percent integer,
    metadata jsonb DEFAULT '{}'::jsonb
);


ALTER TABLE orchestration.task_progress_log OWNER TO sfloess;

--
-- Name: task_progress_log_id_seq; Type: SEQUENCE; Schema: orchestration; Owner: sfloess
--

CREATE SEQUENCE orchestration.task_progress_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE orchestration.task_progress_log_id_seq OWNER TO sfloess;

--
-- Name: task_progress_log_id_seq; Type: SEQUENCE OWNED BY; Schema: orchestration; Owner: sfloess
--

ALTER SEQUENCE orchestration.task_progress_log_id_seq OWNED BY orchestration.task_progress_log.id;


--
-- Name: task_queue_id_seq; Type: SEQUENCE; Schema: orchestration; Owner: sfloess
--

CREATE SEQUENCE orchestration.task_queue_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE orchestration.task_queue_id_seq OWNER TO sfloess;

--
-- Name: task_queue_id_seq; Type: SEQUENCE OWNED BY; Schema: orchestration; Owner: sfloess
--

ALTER SEQUENCE orchestration.task_queue_id_seq OWNED BY orchestration.task_queue.id;


--
-- Name: worker_heartbeats; Type: TABLE; Schema: orchestration; Owner: sfloess
--

CREATE TABLE orchestration.worker_heartbeats (
    worker_id text NOT NULL,
    hostname text NOT NULL,
    last_seen timestamp with time zone DEFAULT now(),
    current_task_id text,
    status text DEFAULT 'idle'::text,
    capabilities jsonb DEFAULT '{}'::jsonb,
    metadata jsonb DEFAULT '{}'::jsonb
);


ALTER TABLE orchestration.worker_heartbeats OWNER TO sfloess;

--
-- Name: worker_utilization; Type: MATERIALIZED VIEW; Schema: orchestration; Owner: sfloess
--

CREATE MATERIALIZED VIEW orchestration.worker_utilization AS
 SELECT w.worker_id,
    w.hostname,
    w.status,
    w.last_seen,
    count(t.id) FILTER (WHERE (t.status = 'running'::text)) AS active_tasks,
    count(t.id) FILTER (WHERE (t.status = 'completed'::text)) AS completed_tasks,
    sum(t.actual_duration_ms) FILTER (WHERE (t.status = 'completed'::text)) AS total_work_ms,
    sum(t.cost_usd) AS total_cost
   FROM (orchestration.worker_heartbeats w
     LEFT JOIN orchestration.task_queue t ON ((w.worker_id = t.assigned_worker)))
  GROUP BY w.worker_id, w.hostname, w.status, w.last_seen
  WITH NO DATA;


ALTER MATERIALIZED VIEW orchestration.worker_utilization OWNER TO sfloess;

--
-- Name: MATERIALIZED VIEW worker_utilization; Type: COMMENT; Schema: orchestration; Owner: sfloess
--

COMMENT ON MATERIALIZED VIEW orchestration.worker_utilization IS 'Auto-refresh: */5 * * * * (every 5 minutes)';


--
-- Name: file_locks; Type: TABLE; Schema: orchestrator; Owner: sfloess
--

CREATE TABLE orchestrator.file_locks (
    file_path text NOT NULL,
    locked_by text NOT NULL,
    locked_at timestamp with time zone DEFAULT now(),
    expires_at timestamp with time zone DEFAULT (now() + '00:05:00'::interval)
);


ALTER TABLE orchestrator.file_locks OWNER TO sfloess;

--
-- Name: messages; Type: TABLE; Schema: orchestrator; Owner: sfloess
--

CREATE TABLE orchestrator.messages (
    message_id integer NOT NULL,
    from_session text NOT NULL,
    to_session text NOT NULL,
    message_type text NOT NULL,
    payload jsonb NOT NULL,
    sent_at timestamp with time zone DEFAULT now(),
    read_at timestamp with time zone,
    expires_at timestamp with time zone DEFAULT (now() + '24:00:00'::interval),
    ack_required boolean DEFAULT false,
    acked_at timestamp with time zone
)
WITH (autovacuum_vacuum_scale_factor='0.01');


ALTER TABLE orchestrator.messages OWNER TO sfloess;

--
-- Name: messages_message_id_seq; Type: SEQUENCE; Schema: orchestrator; Owner: sfloess
--

CREATE SEQUENCE orchestrator.messages_message_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE orchestrator.messages_message_id_seq OWNER TO sfloess;

--
-- Name: messages_message_id_seq; Type: SEQUENCE OWNED BY; Schema: orchestrator; Owner: sfloess
--

ALTER SEQUENCE orchestrator.messages_message_id_seq OWNED BY orchestrator.messages.message_id;


--
-- Name: node_performance; Type: TABLE; Schema: orchestrator; Owner: sfloess
--

CREATE TABLE orchestrator.node_performance (
    node_id text NOT NULL,
    task_type text NOT NULL,
    alpha double precision DEFAULT 1.0,
    beta double precision DEFAULT 1.0,
    total_assigned integer DEFAULT 0,
    total_completed integer DEFAULT 0,
    total_failed integer DEFAULT 0,
    avg_duration_ms double precision,
    avg_reward double precision DEFAULT 0.5,
    last_assigned timestamp with time zone
);


ALTER TABLE orchestrator.node_performance OWNER TO sfloess;

--
-- Name: schema_version; Type: TABLE; Schema: orchestrator; Owner: sfloess
--

CREATE TABLE orchestrator.schema_version (
    version integer NOT NULL,
    applied_at timestamp with time zone DEFAULT now(),
    description text
);


ALTER TABLE orchestrator.schema_version OWNER TO sfloess;

--
-- Name: sessions; Type: TABLE; Schema: orchestrator; Owner: sfloess
--

CREATE TABLE orchestrator.sessions (
    session_id text NOT NULL,
    node_id text NOT NULL,
    started_at timestamp with time zone DEFAULT now(),
    last_heartbeat timestamp with time zone DEFAULT now(),
    expires_at timestamp with time zone DEFAULT (now() + '7 days'::interval),
    status text DEFAULT 'active'::text,
    metadata jsonb DEFAULT '{}'::jsonb,
    health_state text DEFAULT 'active'::text,
    CONSTRAINT sessions_status_check CHECK ((status = ANY (ARRAY['active'::text, 'idle'::text, 'dead'::text])))
);


ALTER TABLE orchestrator.sessions OWNER TO sfloess;

--
-- Name: work_queue; Type: TABLE; Schema: orchestrator; Owner: sfloess
--

CREATE TABLE orchestrator.work_queue (
    work_id integer NOT NULL,
    task_type text NOT NULL,
    task_data jsonb DEFAULT '{}'::jsonb,
    files text[] DEFAULT ARRAY[]::text[],
    status text DEFAULT 'pending'::text,
    assigned_to text,
    enqueued_at timestamp with time zone DEFAULT now(),
    assigned_at timestamp with time zone,
    completed_at timestamp with time zone,
    expires_at timestamp with time zone DEFAULT (now() + '30 days'::interval),
    priority integer DEFAULT 0,
    retry_count integer DEFAULT 0,
    result jsonb,
    session_id text,
    CONSTRAINT work_queue_priority_check CHECK (((priority >= 0) AND (priority <= 10))),
    CONSTRAINT work_queue_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'assigned'::text, 'completed'::text, 'failed'::text])))
)
WITH (autovacuum_vacuum_scale_factor='0.05');


ALTER TABLE orchestrator.work_queue OWNER TO sfloess;

--
-- Name: work_queue_backup; Type: TABLE; Schema: orchestrator; Owner: sfloess
--

CREATE TABLE orchestrator.work_queue_backup (
    work_id integer,
    task_type text,
    task_payload jsonb,
    files text[],
    status text,
    assigned_to text,
    enqueued_at timestamp with time zone,
    assigned_at timestamp with time zone,
    completed_at timestamp with time zone,
    expires_at timestamp with time zone,
    priority integer,
    retry_count integer,
    result jsonb
);


ALTER TABLE orchestrator.work_queue_backup OWNER TO sfloess;

--
-- Name: work_queue_work_id_seq; Type: SEQUENCE; Schema: orchestrator; Owner: sfloess
--

CREATE SEQUENCE orchestrator.work_queue_work_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE orchestrator.work_queue_work_id_seq OWNER TO sfloess;

--
-- Name: work_queue_work_id_seq; Type: SEQUENCE OWNED BY; Schema: orchestrator; Owner: sfloess
--

ALTER SEQUENCE orchestrator.work_queue_work_id_seq OWNED BY orchestrator.work_queue.work_id;


--
-- Name: chunks; Type: TABLE; Schema: processing; Owner: sfloess
--

CREATE TABLE processing.chunks (
    id bigint NOT NULL,
    chunk_id uuid DEFAULT public.uuid_generate_v4(),
    source_file_id integer,
    chunk_index integer NOT NULL,
    chunk_text text NOT NULL,
    token_count integer,
    embedding public.vector(768),
    created_at timestamp without time zone DEFAULT now(),
    embedded_at timestamp without time zone,
    graphed_at timestamp without time zone,
    metadata jsonb
);


ALTER TABLE processing.chunks OWNER TO sfloess;

--
-- Name: chunks_id_seq; Type: SEQUENCE; Schema: processing; Owner: sfloess
--

CREATE SEQUENCE processing.chunks_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE processing.chunks_id_seq OWNER TO sfloess;

--
-- Name: chunks_id_seq; Type: SEQUENCE OWNED BY; Schema: processing; Owner: sfloess
--

ALTER SEQUENCE processing.chunks_id_seq OWNED BY processing.chunks.id;


--
-- Name: source_files; Type: TABLE; Schema: processing; Owner: sfloess
--

CREATE TABLE processing.source_files (
    id integer NOT NULL,
    file_path text NOT NULL,
    source text NOT NULL,
    file_size_bytes bigint,
    discovered_at timestamp without time zone DEFAULT now(),
    processing_started_at timestamp without time zone,
    processing_completed_at timestamp without time zone,
    status text DEFAULT 'pending'::text,
    error_message text,
    retry_count integer DEFAULT 0,
    total_chunks integer,
    metadata jsonb,
    CONSTRAINT source_files_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'chunking'::text, 'chunked'::text, 'embedding'::text, 'embedded'::text, 'graphing'::text, 'completed'::text, 'failed'::text])))
);


ALTER TABLE processing.source_files OWNER TO sfloess;

--
-- Name: pipeline_summary; Type: MATERIALIZED VIEW; Schema: processing; Owner: sfloess
--

CREATE MATERIALIZED VIEW processing.pipeline_summary AS
 SELECT status,
    count(*) AS file_count,
    sum(total_chunks) AS total_chunks,
    avg(total_chunks) AS avg_chunks_per_file,
    sum(file_size_bytes) AS total_bytes,
    min(discovered_at) AS first_discovered,
    max(processing_completed_at) AS last_completed
   FROM processing.source_files sf
  GROUP BY status
  WITH NO DATA;


ALTER MATERIALIZED VIEW processing.pipeline_summary OWNER TO sfloess;

--
-- Name: processing_stats; Type: TABLE; Schema: processing; Owner: sfloess
--

CREATE TABLE processing.processing_stats (
    id integer NOT NULL,
    recorded_at timestamp without time zone DEFAULT now(),
    queue_type text NOT NULL,
    pending_count integer,
    processing_count integer,
    completed_count integer,
    failed_count integer,
    avg_processing_ms numeric,
    chunks_per_second numeric,
    active_workers integer,
    metadata jsonb
);


ALTER TABLE processing.processing_stats OWNER TO sfloess;

--
-- Name: processing_stats_id_seq; Type: SEQUENCE; Schema: processing; Owner: sfloess
--

CREATE SEQUENCE processing.processing_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE processing.processing_stats_id_seq OWNER TO sfloess;

--
-- Name: processing_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: processing; Owner: sfloess
--

ALTER SEQUENCE processing.processing_stats_id_seq OWNED BY processing.processing_stats.id;


--
-- Name: work_queue; Type: TABLE; Schema: processing; Owner: sfloess
--

CREATE TABLE processing.work_queue (
    id bigint NOT NULL,
    queue_type text NOT NULL,
    source_file_id integer,
    chunk_id bigint,
    priority integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT now(),
    claimed_at timestamp without time zone,
    claimed_by text,
    completed_at timestamp without time zone,
    failed_at timestamp without time zone,
    retry_count integer DEFAULT 0,
    max_retries integer DEFAULT 3,
    error_message text,
    processing_duration_ms integer,
    metadata jsonb,
    CONSTRAINT work_queue_queue_type_check CHECK ((queue_type = ANY (ARRAY['chunk'::text, 'embed'::text, 'graph'::text])))
);


ALTER TABLE processing.work_queue OWNER TO sfloess;

--
-- Name: queue_summary; Type: MATERIALIZED VIEW; Schema: processing; Owner: sfloess
--

CREATE MATERIALIZED VIEW processing.queue_summary AS
 SELECT queue_type,
    count(*) FILTER (WHERE ((completed_at IS NULL) AND (failed_at IS NULL) AND (claimed_at IS NULL))) AS pending,
    count(*) FILTER (WHERE ((completed_at IS NULL) AND (failed_at IS NULL) AND (claimed_at IS NOT NULL))) AS processing,
    count(*) FILTER (WHERE (completed_at IS NOT NULL)) AS completed,
    count(*) FILTER (WHERE ((failed_at IS NOT NULL) AND (retry_count >= max_retries))) AS failed,
    avg(processing_duration_ms) FILTER (WHERE (completed_at IS NOT NULL)) AS avg_duration_ms,
    percentile_cont((0.95)::double precision) WITHIN GROUP (ORDER BY ((processing_duration_ms)::double precision)) FILTER (WHERE (completed_at IS NOT NULL)) AS p95_duration_ms
   FROM processing.work_queue
  GROUP BY queue_type
  WITH NO DATA;


ALTER MATERIALIZED VIEW processing.queue_summary OWNER TO sfloess;

--
-- Name: source_files_id_seq; Type: SEQUENCE; Schema: processing; Owner: sfloess
--

CREATE SEQUENCE processing.source_files_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE processing.source_files_id_seq OWNER TO sfloess;

--
-- Name: source_files_id_seq; Type: SEQUENCE OWNED BY; Schema: processing; Owner: sfloess
--

ALTER SEQUENCE processing.source_files_id_seq OWNED BY processing.source_files.id;


--
-- Name: work_queue_id_seq; Type: SEQUENCE; Schema: processing; Owner: sfloess
--

CREATE SEQUENCE processing.work_queue_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE processing.work_queue_id_seq OWNER TO sfloess;

--
-- Name: work_queue_id_seq; Type: SEQUENCE OWNED BY; Schema: processing; Owner: sfloess
--

ALTER SEQUENCE processing.work_queue_id_seq OWNED BY processing.work_queue.id;


--
-- Name: workers; Type: TABLE; Schema: processing; Owner: sfloess
--

CREATE TABLE processing.workers (
    worker_id text NOT NULL,
    hostname text NOT NULL,
    process_id integer NOT NULL,
    queue_types text[] NOT NULL,
    started_at timestamp without time zone DEFAULT now(),
    last_heartbeat timestamp without time zone DEFAULT now(),
    status text DEFAULT 'active'::text,
    total_processed integer DEFAULT 0,
    current_task_id bigint,
    metadata jsonb,
    CONSTRAINT workers_status_check CHECK ((status = ANY (ARRAY['active'::text, 'stopping'::text, 'stopped'::text, 'failed'::text])))
);


ALTER TABLE processing.workers OWNER TO sfloess;

--
-- Name: api_cache; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.api_cache (
    request_hash text NOT NULL,
    model text,
    messages jsonb,
    response jsonb,
    provider text,
    cached_at timestamp without time zone DEFAULT now(),
    hit_count integer DEFAULT 1,
    last_hit timestamp without time zone DEFAULT now()
);


ALTER TABLE public.api_cache OWNER TO postgres;

--
-- Name: api_embedding_usage; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.api_embedding_usage (
    id integer NOT NULL,
    worker_id text,
    provider text,
    model text,
    input_tokens integer,
    dimensions integer,
    cost_usd numeric(10,6),
    cached boolean DEFAULT false,
    latency_ms integer,
    "timestamp" timestamp without time zone DEFAULT now()
);


ALTER TABLE public.api_embedding_usage OWNER TO postgres;

--
-- Name: api_embedding_usage_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.api_embedding_usage_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.api_embedding_usage_id_seq OWNER TO postgres;

--
-- Name: api_embedding_usage_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.api_embedding_usage_id_seq OWNED BY public.api_embedding_usage.id;


--
-- Name: api_failures; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.api_failures (
    id integer NOT NULL,
    worker_id text,
    requested_model text,
    requested_provider text,
    failure_reason text,
    fallback_model text,
    fallback_provider text,
    fallback_successful boolean,
    http_status integer,
    error_message text,
    "timestamp" timestamp without time zone DEFAULT now()
);


ALTER TABLE public.api_failures OWNER TO postgres;

--
-- Name: api_failures_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.api_failures_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.api_failures_id_seq OWNER TO postgres;

--
-- Name: api_failures_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.api_failures_id_seq OWNED BY public.api_failures.id;


--
-- Name: api_models; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.api_models (
    id integer NOT NULL,
    model_name text NOT NULL,
    provider text NOT NULL,
    tier text NOT NULL,
    cost_input_per_1k numeric(10,6) DEFAULT 0.0 NOT NULL,
    cost_output_per_1k numeric(10,6) DEFAULT 0.0 NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    notes text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    CONSTRAINT api_models_tier_check CHECK ((tier = ANY (ARRAY['high'::text, 'medium'::text, 'fast'::text])))
);


ALTER TABLE public.api_models OWNER TO postgres;

--
-- Name: api_models_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.api_models_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.api_models_id_seq OWNER TO postgres;

--
-- Name: api_models_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.api_models_id_seq OWNED BY public.api_models.id;


--
-- Name: api_usage; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.api_usage (
    id integer NOT NULL,
    worker_id text,
    provider text,
    model text,
    prompt_tokens integer,
    completion_tokens integer,
    cost_usd numeric(10,6),
    cached boolean DEFAULT false,
    latency_ms integer,
    "timestamp" timestamp without time zone DEFAULT now()
);


ALTER TABLE public.api_usage OWNER TO postgres;

--
-- Name: api_usage_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.api_usage_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.api_usage_id_seq OWNER TO postgres;

--
-- Name: api_usage_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.api_usage_id_seq OWNED BY public.api_usage.id;


--
-- Name: pdf_knowledge; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.pdf_knowledge (
    id integer NOT NULL,
    pdf_path text NOT NULL,
    category text,
    claim text NOT NULL,
    embedding public.vector(768),
    confidence double precision,
    verified_by text[],
    source_page integer,
    created_at timestamp without time zone DEFAULT now(),
    metadata jsonb
);


ALTER TABLE public.pdf_knowledge OWNER TO postgres;

--
-- Name: pdf_knowledge_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.pdf_knowledge_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.pdf_knowledge_id_seq OWNER TO postgres;

--
-- Name: pdf_knowledge_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.pdf_knowledge_id_seq OWNED BY public.pdf_knowledge.id;


--
-- Name: session_context; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.session_context (
    session_id character varying(255) NOT NULL,
    context_data jsonb NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    last_accessed timestamp without time zone DEFAULT now(),
    metadata jsonb DEFAULT '{}'::jsonb
);


ALTER TABLE public.session_context OWNER TO postgres;

--
-- Name: batch_test; Type: TABLE; Schema: queue; Owner: sfloess
--

CREATE TABLE queue.batch_test (
    id integer NOT NULL,
    data jsonb NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying,
    priority integer DEFAULT 50,
    created_at timestamp without time zone DEFAULT now(),
    claimed_by character varying(255),
    claimed_at timestamp without time zone,
    last_heartbeat timestamp without time zone,
    last_worker_id character varying(255),
    timeout_at timestamp without time zone,
    completed_at timestamp without time zone,
    retry_count integer DEFAULT 0,
    scheduled_at timestamp without time zone,
    error text,
    result jsonb
);


ALTER TABLE queue.batch_test OWNER TO sfloess;

--
-- Name: batch_test_id_seq; Type: SEQUENCE; Schema: queue; Owner: sfloess
--

CREATE SEQUENCE queue.batch_test_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE queue.batch_test_id_seq OWNER TO sfloess;

--
-- Name: batch_test_id_seq; Type: SEQUENCE OWNED BY; Schema: queue; Owner: sfloess
--

ALTER SEQUENCE queue.batch_test_id_seq OWNED BY queue.batch_test.id;


--
-- Name: chunk_id_seq; Type: SEQUENCE; Schema: queue; Owner: postgres
--

CREATE SEQUENCE queue.chunk_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE queue.chunk_id_seq OWNER TO postgres;

--
-- Name: chunk_id_seq; Type: SEQUENCE OWNED BY; Schema: queue; Owner: postgres
--

ALTER SEQUENCE queue.chunk_id_seq OWNED BY queue.chunk.id;


--
-- Name: embed_id_seq; Type: SEQUENCE; Schema: queue; Owner: postgres
--

CREATE SEQUENCE queue.embed_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE queue.embed_id_seq OWNER TO postgres;

--
-- Name: embed_id_seq; Type: SEQUENCE OWNED BY; Schema: queue; Owner: postgres
--

ALTER SEQUENCE queue.embed_id_seq OWNED BY queue.embed.id;


--
-- Name: graph_id_seq; Type: SEQUENCE; Schema: queue; Owner: postgres
--

CREATE SEQUENCE queue.graph_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE queue.graph_id_seq OWNER TO postgres;

--
-- Name: graph_id_seq; Type: SEQUENCE OWNED BY; Schema: queue; Owner: postgres
--

ALTER SEQUENCE queue.graph_id_seq OWNED BY queue.graph.id;


--
-- Name: status; Type: VIEW; Schema: queue; Owner: claude
--

CREATE VIEW queue.status AS
 SELECT queue_name,
    COALESCE(sum(
        CASE
            WHEN (status = 'pending'::text) THEN 1
            ELSE 0
        END), (0)::bigint) AS pending,
    COALESCE(sum(
        CASE
            WHEN (status = 'processing'::text) THEN 1
            ELSE 0
        END), (0)::bigint) AS processing,
    COALESCE(sum(
        CASE
            WHEN (status = 'completed'::text) THEN 1
            ELSE 0
        END), (0)::bigint) AS completed,
    COALESCE(sum(
        CASE
            WHEN ((status = 'failed'::text) OR (status = 'dead_letter'::text)) THEN 1
            ELSE 0
        END), (0)::bigint) AS failed
   FROM ( SELECT 'store'::text AS queue_name,
            store.status
           FROM queue.store
        UNION ALL
         SELECT 'chunk'::text AS queue_name,
            chunk.status
           FROM queue.chunk
        UNION ALL
         SELECT 'embed'::text AS queue_name,
            embed.status
           FROM queue.embed
        UNION ALL
         SELECT 'graph'::text AS queue_name,
            graph.status
           FROM queue.graph) all_queues
  GROUP BY queue_name;


ALTER VIEW queue.status OWNER TO claude;

--
-- Name: store_id_seq; Type: SEQUENCE; Schema: queue; Owner: postgres
--

CREATE SEQUENCE queue.store_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE queue.store_id_seq OWNER TO postgres;

--
-- Name: store_id_seq; Type: SEQUENCE OWNED BY; Schema: queue; Owner: postgres
--

ALTER SEQUENCE queue.store_id_seq OWNED BY queue.store.id;


--
-- Name: tasks; Type: TABLE; Schema: queue; Owner: claude
--

CREATE TABLE queue.tasks (
    id integer NOT NULL,
    priority integer NOT NULL,
    task_type character varying(255) NOT NULL,
    payload jsonb NOT NULL,
    status character varying(50) DEFAULT 'pending'::character varying NOT NULL,
    worker_id character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    claimed_at timestamp with time zone,
    completed_at timestamp with time zone,
    error_message text,
    retry_count integer DEFAULT 0,
    CONSTRAINT tasks_priority_check CHECK (((priority >= 1) AND (priority <= 10)))
);


ALTER TABLE queue.tasks OWNER TO claude;

--
-- Name: tasks_id_seq; Type: SEQUENCE; Schema: queue; Owner: claude
--

CREATE SEQUENCE queue.tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE queue.tasks_id_seq OWNER TO claude;

--
-- Name: tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: queue; Owner: claude
--

ALTER SEQUENCE queue.tasks_id_seq OWNED BY queue.tasks.id;


--
-- Name: worker_heartbeat; Type: TABLE; Schema: queue; Owner: sfloess
--

CREATE TABLE queue.worker_heartbeat (
    worker_id character varying(255) NOT NULL,
    queue_name character varying(50) NOT NULL,
    item_id integer NOT NULL,
    last_heartbeat timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT fk_queue_name CHECK (((queue_name)::text = ANY ((ARRAY['store'::character varying, 'chunk'::character varying, 'embed'::character varying, 'graph'::character varying])::text[])))
);


ALTER TABLE queue.worker_heartbeat OWNER TO sfloess;

--
-- Name: TABLE worker_heartbeat; Type: COMMENT; Schema: queue; Owner: sfloess
--

COMMENT ON TABLE queue.worker_heartbeat IS 'Worker heartbeat tracking for stuck item recovery';


--
-- Name: COLUMN worker_heartbeat.worker_id; Type: COMMENT; Schema: queue; Owner: sfloess
--

COMMENT ON COLUMN queue.worker_heartbeat.worker_id IS 'Unique worker identifier';


--
-- Name: COLUMN worker_heartbeat.queue_name; Type: COMMENT; Schema: queue; Owner: sfloess
--

COMMENT ON COLUMN queue.worker_heartbeat.queue_name IS 'Queue being processed';


--
-- Name: COLUMN worker_heartbeat.item_id; Type: COMMENT; Schema: queue; Owner: sfloess
--

COMMENT ON COLUMN queue.worker_heartbeat.item_id IS 'Item ID being processed';


--
-- Name: COLUMN worker_heartbeat.last_heartbeat; Type: COMMENT; Schema: queue; Owner: sfloess
--

COMMENT ON COLUMN queue.worker_heartbeat.last_heartbeat IS 'Last heartbeat timestamp';


--
-- Name: evidence; Type: TABLE; Schema: reasoning; Owner: claude
--

CREATE TABLE reasoning.evidence (
    id integer NOT NULL,
    evidence_text text NOT NULL,
    embedding public.vector(768),
    domain text,
    observed_at timestamp without time zone DEFAULT now()
);


ALTER TABLE reasoning.evidence OWNER TO claude;

--
-- Name: evidence_id_seq; Type: SEQUENCE; Schema: reasoning; Owner: claude
--

CREATE SEQUENCE reasoning.evidence_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE reasoning.evidence_id_seq OWNER TO claude;

--
-- Name: evidence_id_seq; Type: SEQUENCE OWNED BY; Schema: reasoning; Owner: claude
--

ALTER SEQUENCE reasoning.evidence_id_seq OWNED BY reasoning.evidence.id;


--
-- Name: explanations; Type: TABLE; Schema: reasoning; Owner: claude
--

CREATE TABLE reasoning.explanations (
    id integer NOT NULL,
    evidence_id integer,
    hypothesis_id integer,
    likelihood double precision NOT NULL,
    prior double precision NOT NULL,
    posterior double precision NOT NULL,
    explanation_quality double precision NOT NULL,
    chosen_as_best boolean DEFAULT false,
    confirmed boolean,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE reasoning.explanations OWNER TO claude;

--
-- Name: explanations_id_seq; Type: SEQUENCE; Schema: reasoning; Owner: claude
--

CREATE SEQUENCE reasoning.explanations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE reasoning.explanations_id_seq OWNER TO claude;

--
-- Name: explanations_id_seq; Type: SEQUENCE OWNED BY; Schema: reasoning; Owner: claude
--

ALTER SEQUENCE reasoning.explanations_id_seq OWNED BY reasoning.explanations.id;


--
-- Name: hypotheses; Type: TABLE; Schema: reasoning; Owner: claude
--

CREATE TABLE reasoning.hypotheses (
    id integer NOT NULL,
    hypothesis_text text NOT NULL,
    embedding public.vector(768),
    domain text,
    prior_probability double precision DEFAULT 0.5,
    simplicity_score double precision DEFAULT 0.5,
    coherence_score double precision DEFAULT 0.5,
    num_confirmations integer DEFAULT 0,
    num_refutations integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE reasoning.hypotheses OWNER TO claude;

--
-- Name: hypotheses_id_seq; Type: SEQUENCE; Schema: reasoning; Owner: claude
--

CREATE SEQUENCE reasoning.hypotheses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE reasoning.hypotheses_id_seq OWNER TO claude;

--
-- Name: hypotheses_id_seq; Type: SEQUENCE OWNED BY; Schema: reasoning; Owner: claude
--

ALTER SEQUENCE reasoning.hypotheses_id_seq OWNED BY reasoning.hypotheses.id;


--
-- Name: tasks; Type: TABLE; Schema: scraping; Owner: sfloess
--

CREATE TABLE scraping.tasks (
    id integer NOT NULL,
    url text NOT NULL,
    category text NOT NULL,
    priority integer DEFAULT 5 NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    retries integer DEFAULT 0 NOT NULL,
    max_retries integer DEFAULT 3 NOT NULL,
    error_message text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    queued_at timestamp without time zone,
    started_at timestamp without time zone,
    completed_at timestamp without time zone,
    CONSTRAINT tasks_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'queued'::text, 'processing'::text, 'completed'::text, 'failed'::text])))
);


ALTER TABLE scraping.tasks OWNER TO sfloess;

--
-- Name: tasks_id_seq; Type: SEQUENCE; Schema: scraping; Owner: sfloess
--

CREATE SEQUENCE scraping.tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE scraping.tasks_id_seq OWNER TO sfloess;

--
-- Name: tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: scraping; Owner: sfloess
--

ALTER SEQUENCE scraping.tasks_id_seq OWNED BY scraping.tasks.id;


--
-- Name: knowledge_base; Type: TABLE; Schema: search; Owner: postgres
--

CREATE TABLE search.knowledge_base (
    id integer NOT NULL,
    title text NOT NULL,
    content text NOT NULL,
    category text,
    tags text[],
    metadata jsonb,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    search_vector tsvector GENERATED ALWAYS AS (((setweight(to_tsvector('english'::regconfig, COALESCE(title, ''::text)), 'A'::"char") || setweight(to_tsvector('english'::regconfig, COALESCE(content, ''::text)), 'B'::"char")) || setweight(to_tsvector('english'::regconfig, COALESCE(category, ''::text)), 'C'::"char"))) STORED
);


ALTER TABLE search.knowledge_base OWNER TO postgres;

--
-- Name: knowledge_base_id_seq; Type: SEQUENCE; Schema: search; Owner: postgres
--

CREATE SEQUENCE search.knowledge_base_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE search.knowledge_base_id_seq OWNER TO postgres;

--
-- Name: knowledge_base_id_seq; Type: SEQUENCE OWNED BY; Schema: search; Owner: postgres
--

ALTER SEQUENCE search.knowledge_base_id_seq OWNED BY search.knowledge_base.id;


--
-- Name: api_calls; Type: TABLE; Schema: storage; Owner: claude
--

CREATE TABLE storage.api_calls (
    id integer NOT NULL,
    worker_id character varying(255),
    model character varying(255) NOT NULL,
    provider character varying(100),
    prompt text,
    response text,
    input_tokens integer,
    output_tokens integer,
    total_tokens integer,
    cost_usd numeric(10,6),
    latency_ms integer,
    status character varying(50),
    error text,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE storage.api_calls OWNER TO claude;

--
-- Name: api_calls_id_seq; Type: SEQUENCE; Schema: storage; Owner: claude
--

CREATE SEQUENCE storage.api_calls_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE storage.api_calls_id_seq OWNER TO claude;

--
-- Name: api_calls_id_seq; Type: SEQUENCE OWNED BY; Schema: storage; Owner: claude
--

ALTER SEQUENCE storage.api_calls_id_seq OWNED BY storage.api_calls.id;


--
-- Name: ab_test_plans; Type: TABLE; Schema: workflow; Owner: sfloess
--

CREATE TABLE workflow.ab_test_plans (
    id integer NOT NULL,
    name text NOT NULL,
    hypothesis text,
    config jsonb NOT NULL,
    status text NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    completed_at timestamp without time zone
);


ALTER TABLE workflow.ab_test_plans OWNER TO sfloess;

--
-- Name: ab_test_plans_id_seq; Type: SEQUENCE; Schema: workflow; Owner: sfloess
--

CREATE SEQUENCE workflow.ab_test_plans_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE workflow.ab_test_plans_id_seq OWNER TO sfloess;

--
-- Name: ab_test_plans_id_seq; Type: SEQUENCE OWNED BY; Schema: workflow; Owner: sfloess
--

ALTER SEQUENCE workflow.ab_test_plans_id_seq OWNED BY workflow.ab_test_plans.id;


--
-- Name: ab_test_rollbacks; Type: TABLE; Schema: workflow; Owner: sfloess
--

CREATE TABLE workflow.ab_test_rollbacks (
    id integer NOT NULL,
    test_name text NOT NULL,
    reason text NOT NULL,
    rolled_back_at timestamp without time zone DEFAULT now()
);


ALTER TABLE workflow.ab_test_rollbacks OWNER TO sfloess;

--
-- Name: ab_test_rollbacks_id_seq; Type: SEQUENCE; Schema: workflow; Owner: sfloess
--

CREATE SEQUENCE workflow.ab_test_rollbacks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE workflow.ab_test_rollbacks_id_seq OWNER TO sfloess;

--
-- Name: ab_test_rollbacks_id_seq; Type: SEQUENCE OWNED BY; Schema: workflow; Owner: sfloess
--

ALTER SEQUENCE workflow.ab_test_rollbacks_id_seq OWNED BY workflow.ab_test_rollbacks.id;


--
-- Name: ab_test_rollout_plans; Type: TABLE; Schema: workflow; Owner: sfloess
--

CREATE TABLE workflow.ab_test_rollout_plans (
    id integer NOT NULL,
    test_name text NOT NULL,
    variant text NOT NULL,
    plan jsonb NOT NULL,
    status text DEFAULT 'pending'::text,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE workflow.ab_test_rollout_plans OWNER TO sfloess;

--
-- Name: ab_test_rollout_plans_id_seq; Type: SEQUENCE; Schema: workflow; Owner: sfloess
--

CREATE SEQUENCE workflow.ab_test_rollout_plans_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE workflow.ab_test_rollout_plans_id_seq OWNER TO sfloess;

--
-- Name: ab_test_rollout_plans_id_seq; Type: SEQUENCE OWNED BY; Schema: workflow; Owner: sfloess
--

ALTER SEQUENCE workflow.ab_test_rollout_plans_id_seq OWNED BY workflow.ab_test_rollout_plans.id;


--
-- Name: ab_test_traffic; Type: TABLE; Schema: workflow; Owner: sfloess
--

CREATE TABLE workflow.ab_test_traffic (
    test_name text NOT NULL,
    variant text NOT NULL,
    traffic_pct integer NOT NULL,
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE workflow.ab_test_traffic OWNER TO sfloess;

--
-- Name: arbiter_decisions; Type: TABLE; Schema: workflow; Owner: sfloess
--

CREATE TABLE workflow.arbiter_decisions (
    id integer NOT NULL,
    workflow_execution_id integer NOT NULL,
    arbiter_model character varying(64) NOT NULL,
    worker_result_ids integer[] NOT NULL,
    decision text NOT NULL,
    decision_embedding public.vector(768),
    reasoning text NOT NULL,
    confidence real,
    duration_ms bigint NOT NULL,
    input_tokens integer NOT NULL,
    output_tokens integer NOT NULL,
    cost_usd numeric(10,6) NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT arbiter_decisions_confidence_check CHECK (((confidence >= (0.0)::double precision) AND (confidence <= (1.0)::double precision)))
);


ALTER TABLE workflow.arbiter_decisions OWNER TO sfloess;

--
-- Name: arbiter_decisions_id_seq; Type: SEQUENCE; Schema: workflow; Owner: sfloess
--

CREATE SEQUENCE workflow.arbiter_decisions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE workflow.arbiter_decisions_id_seq OWNER TO sfloess;

--
-- Name: arbiter_decisions_id_seq; Type: SEQUENCE OWNED BY; Schema: workflow; Owner: sfloess
--

ALTER SEQUENCE workflow.arbiter_decisions_id_seq OWNED BY workflow.arbiter_decisions.id;


--
-- Name: circuit_breaker_state; Type: TABLE; Schema: workflow; Owner: sfloess
--

CREATE TABLE workflow.circuit_breaker_state (
    model text NOT NULL,
    state text DEFAULT 'closed'::text NOT NULL,
    success_count integer DEFAULT 0 NOT NULL,
    failure_count integer DEFAULT 0 NOT NULL,
    consecutive_failures integer DEFAULT 0 NOT NULL,
    last_failure_time timestamp with time zone,
    last_success_time timestamp with time zone,
    call_history jsonb DEFAULT '[]'::jsonb,
    half_open_calls integer DEFAULT 0 NOT NULL,
    half_open_successes integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE workflow.circuit_breaker_state OWNER TO sfloess;

--
-- Name: confidence_calibration; Type: TABLE; Schema: workflow; Owner: sfloess
--

CREATE TABLE workflow.confidence_calibration (
    id integer NOT NULL,
    model text NOT NULL,
    reported_confidence numeric NOT NULL,
    actual_outcome numeric NOT NULL,
    task_type text,
    workflow_execution_id text,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE workflow.confidence_calibration OWNER TO sfloess;

--
-- Name: confidence_calibration_id_seq; Type: SEQUENCE; Schema: workflow; Owner: sfloess
--

CREATE SEQUENCE workflow.confidence_calibration_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE workflow.confidence_calibration_id_seq OWNER TO sfloess;

--
-- Name: confidence_calibration_id_seq; Type: SEQUENCE OWNED BY; Schema: workflow; Owner: sfloess
--

ALTER SEQUENCE workflow.confidence_calibration_id_seq OWNED BY workflow.confidence_calibration.id;


--
-- Name: consensus_cache; Type: TABLE; Schema: workflow; Owner: sfloess
--

CREATE TABLE workflow.consensus_cache (
    id integer NOT NULL,
    cache_key text NOT NULL,
    question text NOT NULL,
    question_embedding public.vector(768),
    task_type text NOT NULL,
    consensus_result jsonb NOT NULL,
    model_weight_version integer NOT NULL,
    cache_hit_count integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT now(),
    expires_at timestamp without time zone NOT NULL,
    last_hit_at timestamp without time zone
);


ALTER TABLE workflow.consensus_cache OWNER TO sfloess;

--
-- Name: consensus_cache_id_seq; Type: SEQUENCE; Schema: workflow; Owner: sfloess
--

CREATE SEQUENCE workflow.consensus_cache_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE workflow.consensus_cache_id_seq OWNER TO sfloess;

--
-- Name: consensus_cache_id_seq; Type: SEQUENCE OWNED BY; Schema: workflow; Owner: sfloess
--

ALTER SEQUENCE workflow.consensus_cache_id_seq OWNED BY workflow.consensus_cache.id;


--
-- Name: consensus_cache_stats; Type: TABLE; Schema: workflow; Owner: sfloess
--

CREATE TABLE workflow.consensus_cache_stats (
    id integer NOT NULL,
    date date DEFAULT CURRENT_DATE NOT NULL,
    total_lookups integer DEFAULT 0,
    exact_hits integer DEFAULT 0,
    semantic_hits integer DEFAULT 0,
    misses integer DEFAULT 0,
    hit_rate numeric DEFAULT 0.0,
    avg_similarity numeric DEFAULT 0.0,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE workflow.consensus_cache_stats OWNER TO sfloess;

--
-- Name: consensus_cache_stats_id_seq; Type: SEQUENCE; Schema: workflow; Owner: sfloess
--

CREATE SEQUENCE workflow.consensus_cache_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE workflow.consensus_cache_stats_id_seq OWNER TO sfloess;

--
-- Name: consensus_cache_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: workflow; Owner: sfloess
--

ALTER SEQUENCE workflow.consensus_cache_stats_id_seq OWNED BY workflow.consensus_cache_stats.id;


--
-- Name: executions; Type: TABLE; Schema: workflow; Owner: sfloess
--

CREATE TABLE workflow.executions (
    id integer NOT NULL,
    workflow_id character varying(64) NOT NULL,
    workflow_name character varying(255) NOT NULL,
    task_description text NOT NULL,
    task_embedding public.vector(768),
    total_workers integer NOT NULL,
    total_duration_ms bigint NOT NULL,
    outcome character varying(32) NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    execution_hosts text[],
    quality_score numeric(3,2) DEFAULT 0.75,
    CONSTRAINT valid_outcome CHECK (((outcome)::text = ANY (ARRAY[('success'::character varying)::text, ('failed'::character varying)::text, ('error'::character varying)::text])))
);


ALTER TABLE workflow.executions OWNER TO sfloess;

--
-- Name: COLUMN executions.execution_hosts; Type: COMMENT; Schema: workflow; Owner: sfloess
--

COMMENT ON COLUMN workflow.executions.execution_hosts IS 'Array of all physical hosts used in this workflow execution';


--
-- Name: context_impact_analysis; Type: VIEW; Schema: workflow; Owner: sfloess
--

CREATE VIEW workflow.context_impact_analysis AS
 SELECT (metadata ->> 'context_used'::text) AS context_used,
    count(*) AS total_executions,
    avg(total_duration_ms) AS avg_duration_ms,
    avg(total_workers) AS avg_workers,
    count(
        CASE
            WHEN ((outcome)::text = 'success'::text) THEN 1
            ELSE NULL::integer
        END) AS success_count,
    count(
        CASE
            WHEN ((outcome)::text = 'error'::text) THEN 1
            ELSE NULL::integer
        END) AS error_count,
    round(((100.0 * (count(
        CASE
            WHEN ((outcome)::text = 'success'::text) THEN 1
            ELSE NULL::integer
        END))::numeric) / (count(*))::numeric), 2) AS success_rate_percent,
    avg(((metadata ->> 'similar_workflows_found'::text))::integer) AS avg_similar_workflows_found
   FROM workflow.executions
  WHERE ((metadata ->> 'context_used'::text) IS NOT NULL)
  GROUP BY (metadata ->> 'context_used'::text)
  ORDER BY (metadata ->> 'context_used'::text) DESC;


ALTER VIEW workflow.context_impact_analysis OWNER TO sfloess;

--
-- Name: VIEW context_impact_analysis; Type: COMMENT; Schema: workflow; Owner: sfloess
--

COMMENT ON VIEW workflow.context_impact_analysis IS 'A/B testing view: Compare quality metrics for workflows with vs without cross-session context';


--
-- Name: executions_id_seq; Type: SEQUENCE; Schema: workflow; Owner: sfloess
--

CREATE SEQUENCE workflow.executions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE workflow.executions_id_seq OWNER TO sfloess;

--
-- Name: executions_id_seq; Type: SEQUENCE OWNED BY; Schema: workflow; Owner: sfloess
--

ALTER SEQUENCE workflow.executions_id_seq OWNED BY workflow.executions.id;


--
-- Name: experiments; Type: TABLE; Schema: workflow; Owner: sfloess
--

CREATE TABLE workflow.experiments (
    id integer NOT NULL,
    name text NOT NULL,
    hypothesis text,
    metric text NOT NULL,
    baseline_config jsonb,
    treatment_config jsonb,
    baseline_samples jsonb NOT NULL,
    treatment_samples jsonb NOT NULL,
    baseline_mean numeric,
    treatment_mean numeric,
    improvement_pct numeric,
    p_value numeric,
    ci_lower numeric,
    ci_upper numeric,
    effect_size numeric,
    verdict text NOT NULL,
    success_criteria jsonb,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE workflow.experiments OWNER TO sfloess;

--
-- Name: experiments_id_seq; Type: SEQUENCE; Schema: workflow; Owner: sfloess
--

CREATE SEQUENCE workflow.experiments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE workflow.experiments_id_seq OWNER TO sfloess;

--
-- Name: experiments_id_seq; Type: SEQUENCE OWNED BY; Schema: workflow; Owner: sfloess
--

ALTER SEQUENCE workflow.experiments_id_seq OWNED BY workflow.experiments.id;


--
-- Name: feedback; Type: TABLE; Schema: workflow; Owner: sfloess
--

CREATE TABLE workflow.feedback (
    id integer NOT NULL,
    workflow_execution_id integer NOT NULL,
    feedback_type character varying(32) NOT NULL,
    quality_score real,
    feedback_text text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    processed boolean DEFAULT false,
    processed_at timestamp with time zone,
    CONSTRAINT feedback_quality_score_check CHECK (((quality_score >= (0.0)::double precision) AND (quality_score <= (1.0)::double precision))),
    CONSTRAINT valid_feedback_type CHECK (((feedback_type)::text = ANY (ARRAY[('user'::character varying)::text, ('automated'::character varying)::text, ('adversarial'::character varying)::text])))
);


ALTER TABLE workflow.feedback OWNER TO sfloess;

--
-- Name: feedback_id_seq; Type: SEQUENCE; Schema: workflow; Owner: sfloess
--

CREATE SEQUENCE workflow.feedback_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE workflow.feedback_id_seq OWNER TO sfloess;

--
-- Name: feedback_id_seq; Type: SEQUENCE OWNED BY; Schema: workflow; Owner: sfloess
--

ALTER SEQUENCE workflow.feedback_id_seq OWNED BY workflow.feedback.id;


--
-- Name: worker_results; Type: TABLE; Schema: workflow; Owner: sfloess
--

CREATE TABLE workflow.worker_results (
    id integer NOT NULL,
    workflow_execution_id integer NOT NULL,
    worker_id character varying(64) NOT NULL,
    model character varying(64) NOT NULL,
    task_assigned text NOT NULL,
    result text NOT NULL,
    result_embedding public.vector(768),
    confidence real,
    duration_ms bigint NOT NULL,
    input_tokens integer NOT NULL,
    output_tokens integer NOT NULL,
    cost_usd numeric(10,6) NOT NULL,
    outcome character varying(32) NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    execution_host character varying(255),
    ttft_ms bigint,
    queue_wait_ms bigint,
    retry_overhead_ms bigint DEFAULT 0,
    cache_hit boolean DEFAULT false,
    CONSTRAINT valid_worker_outcome CHECK (((outcome)::text = ANY (ARRAY[('success'::character varying)::text, ('failed'::character varying)::text, ('error'::character varying)::text]))),
    CONSTRAINT worker_results_confidence_check CHECK (((confidence >= (0.0)::double precision) AND (confidence <= (1.0)::double precision)))
);


ALTER TABLE workflow.worker_results OWNER TO sfloess;

--
-- Name: COLUMN worker_results.execution_host; Type: COMMENT; Schema: workflow; Owner: sfloess
--

COMMENT ON COLUMN workflow.worker_results.execution_host IS 'Physical host that executed this worker task';


--
-- Name: hourly_performance; Type: VIEW; Schema: workflow; Owner: postgres
--

CREATE VIEW workflow.hourly_performance AS
 SELECT EXTRACT(hour FROM (created_at AT TIME ZONE 'America/New_York'::text)) AS hour_of_day,
    count(*) AS executions,
    count(*) FILTER (WHERE ((outcome)::text = 'success'::text)) AS successes,
    round(avg(duration_ms)) AS avg_duration_ms,
    round((((count(*) FILTER (WHERE ((outcome)::text = 'success'::text)))::numeric * 100.0) / (count(*))::numeric), 2) AS success_rate,
    round(((((sum(
        CASE
            WHEN cache_hit THEN 1
            ELSE 0
        END))::double precision / (NULLIF(count(*), 0))::double precision) * (100)::double precision))::numeric, 2) AS cache_hit_rate,
        CASE
            WHEN ((count(*))::numeric > (( SELECT avg(sub.cnt) AS avg
               FROM ( SELECT count(*) AS cnt
                       FROM workflow.worker_results worker_results_1
                      GROUP BY (EXTRACT(hour FROM worker_results_1.created_at))) sub) * 1.2)) THEN 'peak'::text
            ELSE 'off-peak'::text
        END AS period_type
   FROM workflow.worker_results
  WHERE (created_at > (now() - '7 days'::interval))
  GROUP BY (EXTRACT(hour FROM (created_at AT TIME ZONE 'America/New_York'::text)))
  ORDER BY (EXTRACT(hour FROM (created_at AT TIME ZONE 'America/New_York'::text)));


ALTER VIEW workflow.hourly_performance OWNER TO postgres;

--
-- Name: learnings; Type: TABLE; Schema: workflow; Owner: sfloess
--

CREATE TABLE workflow.learnings (
    id integer NOT NULL,
    workflow_execution_id integer NOT NULL,
    learning_type character varying(32) NOT NULL,
    description text NOT NULL,
    learning_embedding public.vector(768),
    actionable_insight text NOT NULL,
    importance real,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT learnings_importance_check CHECK (((importance >= (0.0)::double precision) AND (importance <= (1.0)::double precision))),
    CONSTRAINT valid_learning_type CHECK (((learning_type)::text = ANY (ARRAY[('pattern'::character varying)::text, ('failure'::character varying)::text, ('optimization'::character varying)::text])))
);


ALTER TABLE workflow.learnings OWNER TO sfloess;

--
-- Name: learnings_id_seq; Type: SEQUENCE; Schema: workflow; Owner: sfloess
--

CREATE SEQUENCE workflow.learnings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE workflow.learnings_id_seq OWNER TO sfloess;

--
-- Name: learnings_id_seq; Type: SEQUENCE OWNED BY; Schema: workflow; Owner: sfloess
--

ALTER SEQUENCE workflow.learnings_id_seq OWNED BY workflow.learnings.id;


--
-- Name: model_rotation_schedule; Type: TABLE; Schema: workflow; Owner: sfloess
--

CREATE TABLE workflow.model_rotation_schedule (
    id integer NOT NULL,
    model text NOT NULL,
    rollout_stage text NOT NULL,
    traffic_percent numeric NOT NULL,
    stage_started_at timestamp without time zone NOT NULL,
    stage_duration_days integer,
    next_stage text,
    auto_promote boolean DEFAULT false,
    force_exploration boolean DEFAULT false,
    total_executions integer DEFAULT 0,
    successful_executions integer DEFAULT 0,
    avg_quality numeric DEFAULT 0.0,
    last_execution_at timestamp without time zone,
    days_since_execution integer DEFAULT 0,
    is_stale boolean DEFAULT false,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE workflow.model_rotation_schedule OWNER TO sfloess;

--
-- Name: model_rotation_schedule_id_seq; Type: SEQUENCE; Schema: workflow; Owner: sfloess
--

CREATE SEQUENCE workflow.model_rotation_schedule_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE workflow.model_rotation_schedule_id_seq OWNER TO sfloess;

--
-- Name: model_rotation_schedule_id_seq; Type: SEQUENCE OWNED BY; Schema: workflow; Owner: sfloess
--

ALTER SEQUENCE workflow.model_rotation_schedule_id_seq OWNED BY workflow.model_rotation_schedule.id;


--
-- Name: phases; Type: TABLE; Schema: workflow; Owner: sfloess
--

CREATE TABLE workflow.phases (
    id integer NOT NULL,
    workflow_execution_id integer NOT NULL,
    phase_name character varying(255) NOT NULL,
    phase_order integer NOT NULL,
    duration_ms bigint NOT NULL,
    outcome character varying(32) NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT valid_phase_outcome CHECK (((outcome)::text = ANY (ARRAY[('success'::character varying)::text, ('failed'::character varying)::text, ('error'::character varying)::text])))
);


ALTER TABLE workflow.phases OWNER TO sfloess;

--
-- Name: phases_id_seq; Type: SEQUENCE; Schema: workflow; Owner: sfloess
--

CREATE SEQUENCE workflow.phases_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE workflow.phases_id_seq OWNER TO sfloess;

--
-- Name: phases_id_seq; Type: SEQUENCE OWNED BY; Schema: workflow; Owner: sfloess
--

ALTER SEQUENCE workflow.phases_id_seq OWNED BY workflow.phases.id;


--
-- Name: prediction_accuracy; Type: TABLE; Schema: workflow; Owner: sfloess
--

CREATE TABLE workflow.prediction_accuracy (
    id integer NOT NULL,
    workflow_name text NOT NULL,
    task_description text NOT NULL,
    predicted_duration_ms integer,
    actual_duration_ms integer,
    predicted_cost_usd numeric(10,6),
    actual_cost_usd numeric(10,6),
    predicted_quality numeric(4,3),
    actual_quality numeric(4,3),
    prediction_confidence numeric(4,3),
    duration_error_pct numeric(6,2),
    cost_error_pct numeric(6,2),
    quality_error_abs numeric(4,3),
    outcome text NOT NULL,
    model_version text,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE workflow.prediction_accuracy OWNER TO sfloess;

--
-- Name: prediction_accuracy_id_seq; Type: SEQUENCE; Schema: workflow; Owner: sfloess
--

CREATE SEQUENCE workflow.prediction_accuracy_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE workflow.prediction_accuracy_id_seq OWNER TO sfloess;

--
-- Name: prediction_accuracy_id_seq; Type: SEQUENCE OWNED BY; Schema: workflow; Owner: sfloess
--

ALTER SEQUENCE workflow.prediction_accuracy_id_seq OWNED BY workflow.prediction_accuracy.id;


--
-- Name: replays; Type: TABLE; Schema: workflow; Owner: sfloess
--

CREATE TABLE workflow.replays (
    id integer NOT NULL,
    original_workflow_id character varying(255),
    replayed_at timestamp without time zone,
    original_created_at timestamp without time zone,
    avg_confidence_delta numeric,
    arbiter_confidence_delta numeric,
    total_cost_delta numeric,
    verdict character varying(50),
    comparison_data jsonb,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE workflow.replays OWNER TO sfloess;

--
-- Name: replays_id_seq; Type: SEQUENCE; Schema: workflow; Owner: sfloess
--

CREATE SEQUENCE workflow.replays_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE workflow.replays_id_seq OWNER TO sfloess;

--
-- Name: replays_id_seq; Type: SEQUENCE OWNED BY; Schema: workflow; Owner: sfloess
--

ALTER SEQUENCE workflow.replays_id_seq OWNED BY workflow.replays.id;


--
-- Name: response_cache; Type: TABLE; Schema: workflow; Owner: postgres
--

CREATE TABLE workflow.response_cache (
    request_hash character varying(64) NOT NULL,
    model character varying(255) NOT NULL,
    prompt_hash character varying(64) NOT NULL,
    response text NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    hit_count integer DEFAULT 0,
    last_hit_at timestamp without time zone
);


ALTER TABLE workflow.response_cache OWNER TO postgres;

--
-- Name: training_system_build; Type: TABLE; Schema: workflow; Owner: claude
--

CREATE TABLE workflow.training_system_build (
    id integer NOT NULL,
    component text,
    worker text,
    status text,
    code text,
    review_score real,
    issues text[],
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE workflow.training_system_build OWNER TO claude;

--
-- Name: training_system_build_id_seq; Type: SEQUENCE; Schema: workflow; Owner: claude
--

CREATE SEQUENCE workflow.training_system_build_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE workflow.training_system_build_id_seq OWNER TO claude;

--
-- Name: training_system_build_id_seq; Type: SEQUENCE OWNED BY; Schema: workflow; Owner: claude
--

ALTER SEQUENCE workflow.training_system_build_id_seq OWNED BY workflow.training_system_build.id;


--
-- Name: worker_results_id_seq; Type: SEQUENCE; Schema: workflow; Owner: sfloess
--

CREATE SEQUENCE workflow.worker_results_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE workflow.worker_results_id_seq OWNER TO sfloess;

--
-- Name: worker_results_id_seq; Type: SEQUENCE OWNED BY; Schema: workflow; Owner: sfloess
--

ALTER SEQUENCE workflow.worker_results_id_seq OWNED BY workflow.worker_results.id;


--
-- Name: arbiter_decisions; Type: TABLE; Schema: workflows; Owner: sfloess
--

CREATE TABLE workflows.arbiter_decisions (
    decision_id uuid DEFAULT gen_random_uuid() NOT NULL,
    execution_id uuid NOT NULL,
    arbiter_model character varying(100) NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    duration_ms bigint,
    decision text NOT NULL,
    confidence numeric(5,4),
    rationale text,
    selected_workers text[],
    rejected_workers text[],
    input_tokens integer,
    output_tokens integer,
    cost_usd numeric(10,6),
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE workflows.arbiter_decisions OWNER TO sfloess;

--
-- Name: execution_embeddings; Type: TABLE; Schema: workflows; Owner: sfloess
--

CREATE TABLE workflows.execution_embeddings (
    execution_id uuid NOT NULL,
    input_embedding public.vector(768),
    output_embedding public.vector(768),
    context_embedding public.vector(768),
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE workflows.execution_embeddings OWNER TO sfloess;

--
-- Name: execution_phases; Type: TABLE; Schema: workflows; Owner: sfloess
--

CREATE TABLE workflows.execution_phases (
    phase_id uuid DEFAULT gen_random_uuid() NOT NULL,
    execution_id uuid NOT NULL,
    phase_name character varying(255) NOT NULL,
    phase_order integer NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    duration_ms bigint,
    status character varying(50) NOT NULL,
    input_data jsonb,
    output_data jsonb,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT execution_phases_status_check CHECK (((status)::text = ANY (ARRAY[('pending'::character varying)::text, ('running'::character varying)::text, ('completed'::character varying)::text, ('failed'::character varying)::text, ('skipped'::character varying)::text])))
);


ALTER TABLE workflows.execution_phases OWNER TO sfloess;

--
-- Name: executions; Type: TABLE; Schema: workflows; Owner: sfloess
--

CREATE TABLE workflows.executions (
    execution_id uuid DEFAULT gen_random_uuid() NOT NULL,
    workflow_name character varying(255) NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    duration_ms bigint,
    status character varying(50) NOT NULL,
    total_workers integer DEFAULT 0,
    successful_workers integer DEFAULT 0,
    failed_workers integer DEFAULT 0,
    arbiter_model character varying(100),
    final_decision text,
    final_confidence numeric(5,4),
    input_prompt text,
    input_context jsonb,
    output_result text,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT executions_status_check CHECK (((status)::text = ANY (ARRAY[('running'::character varying)::text, ('completed'::character varying)::text, ('failed'::character varying)::text, ('timeout'::character varying)::text])))
);


ALTER TABLE workflows.executions OWNER TO sfloess;

--
-- Name: feedback; Type: TABLE; Schema: workflows; Owner: sfloess
--

CREATE TABLE workflows.feedback (
    feedback_id uuid DEFAULT gen_random_uuid() NOT NULL,
    execution_id uuid NOT NULL,
    feedback_type character varying(50) NOT NULL,
    rating integer,
    comment text,
    ground_truth text,
    corrected_output text,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT feedback_feedback_type_check CHECK (((feedback_type)::text = ANY (ARRAY[('quality'::character varying)::text, ('correctness'::character varying)::text, ('usefulness'::character varying)::text, ('efficiency'::character varying)::text, ('other'::character varying)::text]))),
    CONSTRAINT feedback_rating_check CHECK (((rating >= 1) AND (rating <= 5)))
);


ALTER TABLE workflows.feedback OWNER TO sfloess;

--
-- Name: learnings; Type: TABLE; Schema: workflows; Owner: sfloess
--

CREATE TABLE workflows.learnings (
    learning_id uuid DEFAULT gen_random_uuid() NOT NULL,
    execution_id uuid,
    workflow_name character varying(255) NOT NULL,
    learning_type character varying(50) NOT NULL,
    title character varying(500) NOT NULL,
    description text NOT NULL,
    embedding public.vector(768),
    context jsonb,
    impact_score numeric(5,4),
    confidence numeric(5,4),
    verified boolean DEFAULT false,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT learnings_learning_type_check CHECK (((learning_type)::text = ANY (ARRAY[('pattern'::character varying)::text, ('failure'::character varying)::text, ('optimization'::character varying)::text, ('insight'::character varying)::text, ('best_practice'::character varying)::text])))
);


ALTER TABLE workflows.learnings OWNER TO sfloess;

--
-- Name: model_combinations; Type: TABLE; Schema: workflows; Owner: sfloess
--

CREATE TABLE workflows.model_combinations (
    combination_id uuid DEFAULT gen_random_uuid() NOT NULL,
    workflow_name character varying(255) NOT NULL,
    worker_models character varying(100)[] NOT NULL,
    arbiter_model character varying(100) NOT NULL,
    num_executions integer DEFAULT 0,
    avg_confidence numeric(5,4),
    avg_quality numeric(5,4),
    avg_duration_ms bigint,
    avg_cost_usd numeric(10,6),
    success_rate numeric(5,4),
    last_used_at timestamp with time zone,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE workflows.model_combinations OWNER TO sfloess;

--
-- Name: worker_results; Type: TABLE; Schema: workflows; Owner: sfloess
--

CREATE TABLE workflows.worker_results (
    result_id uuid DEFAULT gen_random_uuid() NOT NULL,
    execution_id uuid NOT NULL,
    worker_id character varying(255) NOT NULL,
    model character varying(100) NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    duration_ms bigint,
    status character varying(50) NOT NULL,
    output text,
    confidence numeric(5,4),
    quality_score numeric(5,4),
    input_tokens integer,
    output_tokens integer,
    cost_usd numeric(10,6),
    error_message text,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT worker_results_status_check CHECK (((status)::text = ANY (ARRAY[('running'::character varying)::text, ('completed'::character varying)::text, ('failed'::character varying)::text, ('timeout'::character varying)::text])))
);


ALTER TABLE workflows.worker_results OWNER TO sfloess;

--
-- Name: model_performance; Type: MATERIALIZED VIEW; Schema: workflows; Owner: sfloess
--

CREATE MATERIALIZED VIEW workflows.model_performance AS
 SELECT model,
    count(*) AS total_executions,
    count(*) FILTER (WHERE ((status)::text = 'completed'::text)) AS successful_executions,
    avg(duration_ms) AS avg_duration_ms,
    avg(confidence) AS avg_confidence,
    avg(quality_score) AS avg_quality_score,
    sum(input_tokens) AS total_input_tokens,
    sum(output_tokens) AS total_output_tokens,
    sum(cost_usd) AS total_cost_usd,
    max(completed_at) AS last_used_at
   FROM workflows.worker_results wr
  WHERE ((status)::text = 'completed'::text)
  GROUP BY model
  WITH NO DATA;


ALTER MATERIALIZED VIEW workflows.model_performance OWNER TO sfloess;

--
-- Name: summary; Type: MATERIALIZED VIEW; Schema: workflows; Owner: sfloess
--

CREATE MATERIALIZED VIEW workflows.summary AS
 SELECT e.workflow_name,
    count(*) AS total_executions,
    count(*) FILTER (WHERE ((e.status)::text = 'completed'::text)) AS successful_executions,
    count(*) FILTER (WHERE ((e.status)::text = 'failed'::text)) AS failed_executions,
    avg(e.duration_ms) AS avg_duration_ms,
    avg(e.final_confidence) AS avg_confidence,
    avg(wr.quality_score) AS avg_quality_score,
    sum(wr.input_tokens) AS total_input_tokens,
    sum(wr.output_tokens) AS total_output_tokens,
    sum(wr.cost_usd) AS total_cost_usd,
    max(e.completed_at) AS last_execution_at
   FROM (workflows.executions e
     LEFT JOIN workflows.worker_results wr ON ((e.execution_id = wr.execution_id)))
  WHERE ((e.status)::text = 'completed'::text)
  GROUP BY e.workflow_name
  WITH NO DATA;


ALTER MATERIALIZED VIEW workflows.summary OWNER TO sfloess;

--
-- Name: api_calls id; Type: DEFAULT; Schema: auto_storage; Owner: claude
--

ALTER TABLE ONLY auto_storage.api_calls ALTER COLUMN id SET DEFAULT nextval('auto_storage.api_calls_id_seq'::regclass);


--
-- Name: api_keys id; Type: DEFAULT; Schema: config; Owner: claude
--

ALTER TABLE ONLY config.api_keys ALTER COLUMN id SET DEFAULT nextval('config.api_keys_id_seq'::regclass);


--
-- Name: key_usage_log id; Type: DEFAULT; Schema: config; Owner: claude
--

ALTER TABLE ONLY config.key_usage_log ALTER COLUMN id SET DEFAULT nextval('config.key_usage_log_id_seq'::regclass);


--
-- Name: entries id; Type: DEFAULT; Schema: costs; Owner: sfloess
--

ALTER TABLE ONLY costs.entries ALTER COLUMN id SET DEFAULT nextval('costs.entries_id_seq'::regclass);


--
-- Name: similar_pairs id; Type: DEFAULT; Schema: dedup; Owner: claude
--

ALTER TABLE ONLY dedup.similar_pairs ALTER COLUMN id SET DEFAULT nextval('dedup.similar_pairs_id_seq'::regclass);


--
-- Name: processing_log id; Type: DEFAULT; Schema: documents; Owner: sfloess
--

ALTER TABLE ONLY documents.processing_log ALTER COLUMN id SET DEFAULT nextval('documents.processing_log_id_seq'::regclass);


--
-- Name: benchmarks id; Type: DEFAULT; Schema: evaluation; Owner: sfloess
--

ALTER TABLE ONLY evaluation.benchmarks ALTER COLUMN id SET DEFAULT nextval('evaluation.benchmarks_id_seq'::regclass);


--
-- Name: results id; Type: DEFAULT; Schema: evaluation; Owner: sfloess
--

ALTER TABLE ONLY evaluation.results ALTER COLUMN id SET DEFAULT nextval('evaluation.results_id_seq'::regclass);


--
-- Name: registry id; Type: DEFAULT; Schema: experiments; Owner: sfloess
--

ALTER TABLE ONLY experiments.registry ALTER COLUMN id SET DEFAULT nextval('experiments.registry_id_seq'::regclass);


--
-- Name: runs id; Type: DEFAULT; Schema: experiments; Owner: sfloess
--

ALTER TABLE ONLY experiments.runs ALTER COLUMN id SET DEFAULT nextval('experiments.runs_id_seq'::regclass);


--
-- Name: command_results id; Type: DEFAULT; Schema: fleet; Owner: claude
--

ALTER TABLE ONLY fleet.command_results ALTER COLUMN id SET DEFAULT nextval('fleet.command_results_id_seq'::regclass);


--
-- Name: tasks id; Type: DEFAULT; Schema: fleet; Owner: claude
--

ALTER TABLE ONLY fleet.tasks ALTER COLUMN id SET DEFAULT nextval('fleet.tasks_id_seq'::regclass);


--
-- Name: workers id; Type: DEFAULT; Schema: fleet; Owner: claude
--

ALTER TABLE ONLY fleet.workers ALTER COLUMN id SET DEFAULT nextval('fleet.workers_id_seq'::regclass);


--
-- Name: workflows id; Type: DEFAULT; Schema: fleet; Owner: claude
--

ALTER TABLE ONLY fleet.workflows ALTER COLUMN id SET DEFAULT nextval('fleet.workflows_id_seq'::regclass);


--
-- Name: convergence_metrics id; Type: DEFAULT; Schema: ga; Owner: claude
--

ALTER TABLE ONLY ga.convergence_metrics ALTER COLUMN id SET DEFAULT nextval('ga.convergence_metrics_id_seq'::regclass);


--
-- Name: migration_log id; Type: DEFAULT; Schema: ga; Owner: claude
--

ALTER TABLE ONLY ga.migration_log ALTER COLUMN id SET DEFAULT nextval('ga.migration_log_id_seq'::regclass);


--
-- Name: populations id; Type: DEFAULT; Schema: ga; Owner: claude
--

ALTER TABLE ONLY ga.populations ALTER COLUMN id SET DEFAULT nextval('ga.populations_id_seq'::regclass);


--
-- Name: machines id; Type: DEFAULT; Schema: inventory; Owner: claude
--

ALTER TABLE ONLY inventory.machines ALTER COLUMN id SET DEFAULT nextval('inventory.machines_id_seq'::regclass);


--
-- Name: chunks id; Type: DEFAULT; Schema: knowledge; Owner: sfloess
--

ALTER TABLE ONLY knowledge.chunks ALTER COLUMN id SET DEFAULT nextval('knowledge.chunks_id_seq'::regclass);


--
-- Name: code_embeddings id; Type: DEFAULT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.code_embeddings ALTER COLUMN id SET DEFAULT nextval('knowledge.code_embeddings_id_seq'::regclass);


--
-- Name: discovered_sources id; Type: DEFAULT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.discovered_sources ALTER COLUMN id SET DEFAULT nextval('knowledge.discovered_sources_id_seq'::regclass);


--
-- Name: discoveries id; Type: DEFAULT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.discoveries ALTER COLUMN id SET DEFAULT nextval('knowledge.discoveries_id_seq'::regclass);


--
-- Name: documents id; Type: DEFAULT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.documents ALTER COLUMN id SET DEFAULT nextval('knowledge.documents_id_seq'::regclass);


--
-- Name: embeddings id; Type: DEFAULT; Schema: knowledge; Owner: sfloess
--

ALTER TABLE ONLY knowledge.embeddings ALTER COLUMN id SET DEFAULT nextval('knowledge.embeddings_id_seq'::regclass);


--
-- Name: entries id; Type: DEFAULT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.entries ALTER COLUMN id SET DEFAULT nextval('knowledge.entries_id_seq'::regclass);


--
-- Name: ingestion_queue id; Type: DEFAULT; Schema: knowledge; Owner: postgres
--

ALTER TABLE ONLY knowledge.ingestion_queue ALTER COLUMN id SET DEFAULT nextval('knowledge.ingestion_queue_id_seq'::regclass);


--
-- Name: memory_chunks id; Type: DEFAULT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.memory_chunks ALTER COLUMN id SET DEFAULT nextval('knowledge.memory_chunks_id_seq'::regclass);


--
-- Name: provenance id; Type: DEFAULT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.provenance ALTER COLUMN id SET DEFAULT nextval('knowledge.provenance_id_seq'::regclass);


--
-- Name: pubmed_articles id; Type: DEFAULT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.pubmed_articles ALTER COLUMN id SET DEFAULT nextval('knowledge.pubmed_articles_id_seq'::regclass);


--
-- Name: research_findings id; Type: DEFAULT; Schema: knowledge; Owner: sfloess
--

ALTER TABLE ONLY knowledge.research_findings ALTER COLUMN id SET DEFAULT nextval('knowledge.research_findings_id_seq'::regclass);


--
-- Name: scraped_content id; Type: DEFAULT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.scraped_content ALTER COLUMN id SET DEFAULT nextval('knowledge.scraped_content_id_seq'::regclass);


--
-- Name: scraped_data id; Type: DEFAULT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.scraped_data ALTER COLUMN id SET DEFAULT nextval('knowledge.scraped_data_id_seq'::regclass);


--
-- Name: url_status id; Type: DEFAULT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.url_status ALTER COLUMN id SET DEFAULT nextval('knowledge.url_status_id_seq'::regclass);


--
-- Name: verification_votes id; Type: DEFAULT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.verification_votes ALTER COLUMN id SET DEFAULT nextval('knowledge.verification_votes_id_seq'::regclass);


--
-- Name: web_articles id; Type: DEFAULT; Schema: knowledge; Owner: sfloess
--

ALTER TABLE ONLY knowledge.web_articles ALTER COLUMN id SET DEFAULT nextval('knowledge.web_articles_id_seq'::regclass);


--
-- Name: web_scrape id; Type: DEFAULT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.web_scrape ALTER COLUMN id SET DEFAULT nextval('knowledge.web_scrape_id_seq'::regclass);


--
-- Name: api_models id; Type: DEFAULT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.api_models ALTER COLUMN id SET DEFAULT nextval('learning.api_models_id_seq'::regclass);


--
-- Name: codebase_analysis id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.codebase_analysis ALTER COLUMN id SET DEFAULT nextval('learning.codebase_analysis_id_seq'::regclass);


--
-- Name: comprehensive_research id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.comprehensive_research ALTER COLUMN id SET DEFAULT nextval('learning.comprehensive_research_id_seq'::regclass);


--
-- Name: concepts id; Type: DEFAULT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.concepts ALTER COLUMN id SET DEFAULT nextval('learning.concepts_id_seq'::regclass);


--
-- Name: confidence_observations id; Type: DEFAULT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.confidence_observations ALTER COLUMN id SET DEFAULT nextval('learning.confidence_observations_id_seq'::regclass);


--
-- Name: continual_learning_roadmap id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.continual_learning_roadmap ALTER COLUMN id SET DEFAULT nextval('learning.continual_learning_roadmap_id_seq'::regclass);


--
-- Name: diversity_violations id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.diversity_violations ALTER COLUMN id SET DEFAULT nextval('learning.diversity_violations_id_seq'::regclass);


--
-- Name: experiences_experiment id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.experiences_experiment ALTER COLUMN id SET DEFAULT nextval('learning.experiences_experiment_id_seq'::regclass);


--
-- Name: experiment_results id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.experiment_results ALTER COLUMN id SET DEFAULT nextval('learning.experiment_results_id_seq'::regclass);


--
-- Name: fine_tuning_queue id; Type: DEFAULT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.fine_tuning_queue ALTER COLUMN id SET DEFAULT nextval('learning.fine_tuning_queue_id_seq'::regclass);


--
-- Name: free_models id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.free_models ALTER COLUMN id SET DEFAULT nextval('learning.free_models_id_seq'::regclass);


--
-- Name: ga_configs id; Type: DEFAULT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.ga_configs ALTER COLUMN id SET DEFAULT nextval('learning.ga_configs_id_seq'::regclass);


--
-- Name: icl_examples id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.icl_examples ALTER COLUMN id SET DEFAULT nextval('learning.icl_examples_id_seq'::regclass);


--
-- Name: improvements id; Type: DEFAULT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.improvements ALTER COLUMN id SET DEFAULT nextval('learning.improvements_id_seq'::regclass);


--
-- Name: infrastructure_knowledge id; Type: DEFAULT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.infrastructure_knowledge ALTER COLUMN id SET DEFAULT nextval('learning.infrastructure_knowledge_id_seq'::regclass);


--
-- Name: knowledge_embeddings id; Type: DEFAULT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.knowledge_embeddings ALTER COLUMN id SET DEFAULT nextval('learning.knowledge_embeddings_id_seq'::regclass);


--
-- Name: load_balancer_state id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.load_balancer_state ALTER COLUMN id SET DEFAULT nextval('learning.load_balancer_state_id_seq'::regclass);


--
-- Name: memory id; Type: DEFAULT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.memory ALTER COLUMN id SET DEFAULT nextval('learning.memory_id_seq'::regclass);


--
-- Name: model_censorship id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.model_censorship ALTER COLUMN id SET DEFAULT nextval('learning.model_censorship_id_seq'::regclass);


--
-- Name: pdf_knowledge id; Type: DEFAULT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.pdf_knowledge ALTER COLUMN id SET DEFAULT nextval('learning.pdf_knowledge_id_seq'::regclass);


--
-- Name: pdf_metadata id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.pdf_metadata ALTER COLUMN id SET DEFAULT nextval('learning.pdf_metadata_id_seq'::regclass);


--
-- Name: queue_failure_patterns id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.queue_failure_patterns ALTER COLUMN id SET DEFAULT nextval('learning.queue_failure_patterns_id_seq'::regclass);


--
-- Name: queue_health_metrics id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.queue_health_metrics ALTER COLUMN id SET DEFAULT nextval('learning.queue_health_metrics_id_seq'::regclass);


--
-- Name: queue_predictions id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.queue_predictions ALTER COLUMN id SET DEFAULT nextval('learning.queue_predictions_id_seq'::regclass);


--
-- Name: reasoning_patterns id; Type: DEFAULT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.reasoning_patterns ALTER COLUMN id SET DEFAULT nextval('learning.reasoning_patterns_id_seq'::regclass);


--
-- Name: relationships id; Type: DEFAULT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.relationships ALTER COLUMN id SET DEFAULT nextval('learning.relationships_id_seq'::regclass);


--
-- Name: request_history id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.request_history ALTER COLUMN id SET DEFAULT nextval('learning.request_history_id_seq'::regclass);


--
-- Name: research_chunks id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.research_chunks ALTER COLUMN id SET DEFAULT nextval('learning.research_chunks_id_seq'::regclass);


--
-- Name: research_documents id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.research_documents ALTER COLUMN id SET DEFAULT nextval('learning.research_documents_id_seq'::regclass);


--
-- Name: research_findings id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.research_findings ALTER COLUMN id SET DEFAULT nextval('learning.research_findings_id_seq'::regclass);


--
-- Name: research_full id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.research_full ALTER COLUMN id SET DEFAULT nextval('learning.research_full_id_seq'::regclass);


--
-- Name: scraping_queue id; Type: DEFAULT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.scraping_queue ALTER COLUMN id SET DEFAULT nextval('learning.scraping_queue_id_seq'::regclass);


--
-- Name: security_policies id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.security_policies ALTER COLUMN id SET DEFAULT nextval('learning.security_policies_id_seq'::regclass);


--
-- Name: security_violations id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.security_violations ALTER COLUMN id SET DEFAULT nextval('learning.security_violations_id_seq'::regclass);


--
-- Name: self_discoveries id; Type: DEFAULT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.self_discoveries ALTER COLUMN id SET DEFAULT nextval('learning.self_discoveries_id_seq'::regclass);


--
-- Name: session_chunks id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.session_chunks ALTER COLUMN id SET DEFAULT nextval('learning.session_chunks_id_seq'::regclass);


--
-- Name: sessions id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.sessions ALTER COLUMN id SET DEFAULT nextval('learning.sessions_id_seq'::regclass);


--
-- Name: strategy_performance_multi id; Type: DEFAULT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.strategy_performance_multi ALTER COLUMN id SET DEFAULT nextval('learning.strategy_performance_multi_id_seq'::regclass);


--
-- Name: web_synthesis id; Type: DEFAULT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.web_synthesis ALTER COLUMN id SET DEFAULT nextval('learning.web_synthesis_id_seq'::regclass);


--
-- Name: api_health_checks id; Type: DEFAULT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.api_health_checks ALTER COLUMN id SET DEFAULT nextval('monitoring.api_health_checks_id_seq'::regclass);


--
-- Name: api_usage id; Type: DEFAULT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.api_usage ALTER COLUMN id SET DEFAULT nextval('monitoring.api_usage_id_seq'::regclass);


--
-- Name: arbiter_decisions id; Type: DEFAULT; Schema: monitoring; Owner: postgres
--

ALTER TABLE ONLY monitoring.arbiter_decisions ALTER COLUMN id SET DEFAULT nextval('monitoring.arbiter_decisions_id_seq'::regclass);


--
-- Name: circuit_breaker_events id; Type: DEFAULT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.circuit_breaker_events ALTER COLUMN id SET DEFAULT nextval('monitoring.circuit_breaker_events_id_seq'::regclass);


--
-- Name: compliance_alerts id; Type: DEFAULT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.compliance_alerts ALTER COLUMN id SET DEFAULT nextval('monitoring.compliance_alerts_id_seq'::regclass);


--
-- Name: confidence_calibration id; Type: DEFAULT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.confidence_calibration ALTER COLUMN id SET DEFAULT nextval('monitoring.confidence_calibration_id_seq'::regclass);


--
-- Name: diversity_alerts id; Type: DEFAULT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.diversity_alerts ALTER COLUMN id SET DEFAULT nextval('monitoring.diversity_alerts_id_seq'::regclass);


--
-- Name: dual_review_results id; Type: DEFAULT; Schema: monitoring; Owner: postgres
--

ALTER TABLE ONLY monitoring.dual_review_results ALTER COLUMN id SET DEFAULT nextval('monitoring.dual_review_results_id_seq'::regclass);


--
-- Name: embedding_provider_usage id; Type: DEFAULT; Schema: monitoring; Owner: postgres
--

ALTER TABLE ONLY monitoring.embedding_provider_usage ALTER COLUMN id SET DEFAULT nextval('monitoring.embedding_provider_usage_id_seq'::regclass);


--
-- Name: execution_log id; Type: DEFAULT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.execution_log ALTER COLUMN id SET DEFAULT nextval('monitoring.execution_log_id_seq'::regclass);


--
-- Name: execution_summary id; Type: DEFAULT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.execution_summary ALTER COLUMN id SET DEFAULT nextval('monitoring.execution_summary_id_seq'::regclass);


--
-- Name: external_api_calls id; Type: DEFAULT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.external_api_calls ALTER COLUMN id SET DEFAULT nextval('monitoring.external_api_calls_id_seq'::regclass);


--
-- Name: fleet_health id; Type: DEFAULT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.fleet_health ALTER COLUMN id SET DEFAULT nextval('monitoring.fleet_health_id_seq'::regclass);


--
-- Name: health_checks id; Type: DEFAULT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.health_checks ALTER COLUMN id SET DEFAULT nextval('monitoring.health_checks_id_seq'::regclass);


--
-- Name: health_predictions id; Type: DEFAULT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.health_predictions ALTER COLUMN id SET DEFAULT nextval('monitoring.health_predictions_id_seq'::regclass);


--
-- Name: human_corrections id; Type: DEFAULT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.human_corrections ALTER COLUMN id SET DEFAULT nextval('monitoring.human_corrections_id_seq'::regclass);


--
-- Name: llm_provider_usage id; Type: DEFAULT; Schema: monitoring; Owner: postgres
--

ALTER TABLE ONLY monitoring.llm_provider_usage ALTER COLUMN id SET DEFAULT nextval('monitoring.llm_provider_usage_id_seq'::regclass);


--
-- Name: model_capabilities id; Type: DEFAULT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.model_capabilities ALTER COLUMN id SET DEFAULT nextval('monitoring.model_capabilities_id_seq'::regclass);


--
-- Name: model_retraining id; Type: DEFAULT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.model_retraining ALTER COLUMN id SET DEFAULT nextval('monitoring.model_retraining_id_seq'::regclass);


--
-- Name: model_selections id; Type: DEFAULT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.model_selections ALTER COLUMN id SET DEFAULT nextval('monitoring.model_selections_id_seq'::regclass);


--
-- Name: model_tuning id; Type: DEFAULT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.model_tuning ALTER COLUMN id SET DEFAULT nextval('monitoring.model_tuning_id_seq'::regclass);


--
-- Name: model_usage id; Type: DEFAULT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.model_usage ALTER COLUMN id SET DEFAULT nextval('monitoring.model_usage_id_seq'::regclass);


--
-- Name: network_latency_matrix id; Type: DEFAULT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.network_latency_matrix ALTER COLUMN id SET DEFAULT nextval('monitoring.network_latency_matrix_id_seq'::regclass);


--
-- Name: network_measurements id; Type: DEFAULT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.network_measurements ALTER COLUMN id SET DEFAULT nextval('monitoring.network_measurements_id_seq'::regclass);


--
-- Name: network_predictions id; Type: DEFAULT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.network_predictions ALTER COLUMN id SET DEFAULT nextval('monitoring.network_predictions_id_seq'::regclass);


--
-- Name: prediction_accuracy id; Type: DEFAULT; Schema: monitoring; Owner: postgres
--

ALTER TABLE ONLY monitoring.prediction_accuracy ALTER COLUMN id SET DEFAULT nextval('monitoring.prediction_accuracy_id_seq'::regclass);


--
-- Name: queue_health id; Type: DEFAULT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.queue_health ALTER COLUMN id SET DEFAULT nextval('monitoring.queue_health_id_seq'::regclass);


--
-- Name: rate_limit_hits id; Type: DEFAULT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.rate_limit_hits ALTER COLUMN id SET DEFAULT nextval('monitoring.rate_limit_hits_id_seq'::regclass);


--
-- Name: rate_limit_requests id; Type: DEFAULT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.rate_limit_requests ALTER COLUMN id SET DEFAULT nextval('monitoring.rate_limit_requests_id_seq'::regclass);


--
-- Name: resource_estimation_coefficients id; Type: DEFAULT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.resource_estimation_coefficients ALTER COLUMN id SET DEFAULT nextval('monitoring.resource_estimation_coefficients_id_seq'::regclass);


--
-- Name: resource_estimation_log id; Type: DEFAULT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.resource_estimation_log ALTER COLUMN id SET DEFAULT nextval('monitoring.resource_estimation_log_id_seq'::regclass);


--
-- Name: resource_usage id; Type: DEFAULT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.resource_usage ALTER COLUMN id SET DEFAULT nextval('monitoring.resource_usage_id_seq'::regclass);


--
-- Name: scraping_metrics id; Type: DEFAULT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.scraping_metrics ALTER COLUMN id SET DEFAULT nextval('monitoring.scraping_metrics_id_seq'::regclass);


--
-- Name: scraping_output id; Type: DEFAULT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.scraping_output ALTER COLUMN id SET DEFAULT nextval('monitoring.scraping_output_id_seq'::regclass);


--
-- Name: session_learnings id; Type: DEFAULT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.session_learnings ALTER COLUMN id SET DEFAULT nextval('monitoring.session_learnings_id_seq'::regclass);


--
-- Name: task_attribution id; Type: DEFAULT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.task_attribution ALTER COLUMN id SET DEFAULT nextval('monitoring.task_attribution_id_seq'::regclass);


--
-- Name: training_jobs id; Type: DEFAULT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.training_jobs ALTER COLUMN id SET DEFAULT nextval('monitoring.training_jobs_id_seq'::regclass);


--
-- Name: worker_assignments id; Type: DEFAULT; Schema: monitoring; Owner: postgres
--

ALTER TABLE ONLY monitoring.worker_assignments ALTER COLUMN id SET DEFAULT nextval('monitoring.worker_assignments_id_seq'::regclass);


--
-- Name: workers id; Type: DEFAULT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.workers ALTER COLUMN id SET DEFAULT nextval('monitoring.workers_id_seq'::regclass);


--
-- Name: auto_storage id; Type: DEFAULT; Schema: orchestration; Owner: sfloess
--

ALTER TABLE ONLY orchestration.auto_storage ALTER COLUMN id SET DEFAULT nextval('orchestration.auto_storage_id_seq'::regclass);


--
-- Name: conversation_history id; Type: DEFAULT; Schema: orchestration; Owner: sfloess
--

ALTER TABLE ONLY orchestration.conversation_history ALTER COLUMN id SET DEFAULT nextval('orchestration.conversation_history_id_seq'::regclass);


--
-- Name: gitlab_issues id; Type: DEFAULT; Schema: orchestration; Owner: sfloess
--

ALTER TABLE ONLY orchestration.gitlab_issues ALTER COLUMN id SET DEFAULT nextval('orchestration.gitlab_issues_id_seq'::regclass);


--
-- Name: task_dependencies id; Type: DEFAULT; Schema: orchestration; Owner: sfloess
--

ALTER TABLE ONLY orchestration.task_dependencies ALTER COLUMN id SET DEFAULT nextval('orchestration.task_dependencies_id_seq'::regclass);


--
-- Name: task_progress_log id; Type: DEFAULT; Schema: orchestration; Owner: sfloess
--

ALTER TABLE ONLY orchestration.task_progress_log ALTER COLUMN id SET DEFAULT nextval('orchestration.task_progress_log_id_seq'::regclass);


--
-- Name: task_queue id; Type: DEFAULT; Schema: orchestration; Owner: sfloess
--

ALTER TABLE ONLY orchestration.task_queue ALTER COLUMN id SET DEFAULT nextval('orchestration.task_queue_id_seq'::regclass);


--
-- Name: messages message_id; Type: DEFAULT; Schema: orchestrator; Owner: sfloess
--

ALTER TABLE ONLY orchestrator.messages ALTER COLUMN message_id SET DEFAULT nextval('orchestrator.messages_message_id_seq'::regclass);


--
-- Name: work_queue work_id; Type: DEFAULT; Schema: orchestrator; Owner: sfloess
--

ALTER TABLE ONLY orchestrator.work_queue ALTER COLUMN work_id SET DEFAULT nextval('orchestrator.work_queue_work_id_seq'::regclass);


--
-- Name: chunks id; Type: DEFAULT; Schema: processing; Owner: sfloess
--

ALTER TABLE ONLY processing.chunks ALTER COLUMN id SET DEFAULT nextval('processing.chunks_id_seq'::regclass);


--
-- Name: processing_stats id; Type: DEFAULT; Schema: processing; Owner: sfloess
--

ALTER TABLE ONLY processing.processing_stats ALTER COLUMN id SET DEFAULT nextval('processing.processing_stats_id_seq'::regclass);


--
-- Name: source_files id; Type: DEFAULT; Schema: processing; Owner: sfloess
--

ALTER TABLE ONLY processing.source_files ALTER COLUMN id SET DEFAULT nextval('processing.source_files_id_seq'::regclass);


--
-- Name: work_queue id; Type: DEFAULT; Schema: processing; Owner: sfloess
--

ALTER TABLE ONLY processing.work_queue ALTER COLUMN id SET DEFAULT nextval('processing.work_queue_id_seq'::regclass);


--
-- Name: api_embedding_usage id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.api_embedding_usage ALTER COLUMN id SET DEFAULT nextval('public.api_embedding_usage_id_seq'::regclass);


--
-- Name: api_failures id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.api_failures ALTER COLUMN id SET DEFAULT nextval('public.api_failures_id_seq'::regclass);


--
-- Name: api_models id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.api_models ALTER COLUMN id SET DEFAULT nextval('public.api_models_id_seq'::regclass);


--
-- Name: api_usage id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.api_usage ALTER COLUMN id SET DEFAULT nextval('public.api_usage_id_seq'::regclass);


--
-- Name: pdf_knowledge id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pdf_knowledge ALTER COLUMN id SET DEFAULT nextval('public.pdf_knowledge_id_seq'::regclass);


--
-- Name: batch_test id; Type: DEFAULT; Schema: queue; Owner: sfloess
--

ALTER TABLE ONLY queue.batch_test ALTER COLUMN id SET DEFAULT nextval('queue.batch_test_id_seq'::regclass);


--
-- Name: chunk id; Type: DEFAULT; Schema: queue; Owner: postgres
--

ALTER TABLE ONLY queue.chunk ALTER COLUMN id SET DEFAULT nextval('queue.chunk_id_seq'::regclass);


--
-- Name: embed id; Type: DEFAULT; Schema: queue; Owner: postgres
--

ALTER TABLE ONLY queue.embed ALTER COLUMN id SET DEFAULT nextval('queue.embed_id_seq'::regclass);


--
-- Name: graph id; Type: DEFAULT; Schema: queue; Owner: postgres
--

ALTER TABLE ONLY queue.graph ALTER COLUMN id SET DEFAULT nextval('queue.graph_id_seq'::regclass);


--
-- Name: store id; Type: DEFAULT; Schema: queue; Owner: postgres
--

ALTER TABLE ONLY queue.store ALTER COLUMN id SET DEFAULT nextval('queue.store_id_seq'::regclass);


--
-- Name: tasks id; Type: DEFAULT; Schema: queue; Owner: claude
--

ALTER TABLE ONLY queue.tasks ALTER COLUMN id SET DEFAULT nextval('queue.tasks_id_seq'::regclass);


--
-- Name: evidence id; Type: DEFAULT; Schema: reasoning; Owner: claude
--

ALTER TABLE ONLY reasoning.evidence ALTER COLUMN id SET DEFAULT nextval('reasoning.evidence_id_seq'::regclass);


--
-- Name: explanations id; Type: DEFAULT; Schema: reasoning; Owner: claude
--

ALTER TABLE ONLY reasoning.explanations ALTER COLUMN id SET DEFAULT nextval('reasoning.explanations_id_seq'::regclass);


--
-- Name: hypotheses id; Type: DEFAULT; Schema: reasoning; Owner: claude
--

ALTER TABLE ONLY reasoning.hypotheses ALTER COLUMN id SET DEFAULT nextval('reasoning.hypotheses_id_seq'::regclass);


--
-- Name: tasks id; Type: DEFAULT; Schema: scraping; Owner: sfloess
--

ALTER TABLE ONLY scraping.tasks ALTER COLUMN id SET DEFAULT nextval('scraping.tasks_id_seq'::regclass);


--
-- Name: knowledge_base id; Type: DEFAULT; Schema: search; Owner: postgres
--

ALTER TABLE ONLY search.knowledge_base ALTER COLUMN id SET DEFAULT nextval('search.knowledge_base_id_seq'::regclass);


--
-- Name: api_calls id; Type: DEFAULT; Schema: storage; Owner: claude
--

ALTER TABLE ONLY storage.api_calls ALTER COLUMN id SET DEFAULT nextval('storage.api_calls_id_seq'::regclass);


--
-- Name: ab_test_plans id; Type: DEFAULT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.ab_test_plans ALTER COLUMN id SET DEFAULT nextval('workflow.ab_test_plans_id_seq'::regclass);


--
-- Name: ab_test_rollbacks id; Type: DEFAULT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.ab_test_rollbacks ALTER COLUMN id SET DEFAULT nextval('workflow.ab_test_rollbacks_id_seq'::regclass);


--
-- Name: ab_test_rollout_plans id; Type: DEFAULT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.ab_test_rollout_plans ALTER COLUMN id SET DEFAULT nextval('workflow.ab_test_rollout_plans_id_seq'::regclass);


--
-- Name: arbiter_decisions id; Type: DEFAULT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.arbiter_decisions ALTER COLUMN id SET DEFAULT nextval('workflow.arbiter_decisions_id_seq'::regclass);


--
-- Name: confidence_calibration id; Type: DEFAULT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.confidence_calibration ALTER COLUMN id SET DEFAULT nextval('workflow.confidence_calibration_id_seq'::regclass);


--
-- Name: consensus_cache id; Type: DEFAULT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.consensus_cache ALTER COLUMN id SET DEFAULT nextval('workflow.consensus_cache_id_seq'::regclass);


--
-- Name: consensus_cache_stats id; Type: DEFAULT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.consensus_cache_stats ALTER COLUMN id SET DEFAULT nextval('workflow.consensus_cache_stats_id_seq'::regclass);


--
-- Name: executions id; Type: DEFAULT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.executions ALTER COLUMN id SET DEFAULT nextval('workflow.executions_id_seq'::regclass);


--
-- Name: experiments id; Type: DEFAULT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.experiments ALTER COLUMN id SET DEFAULT nextval('workflow.experiments_id_seq'::regclass);


--
-- Name: feedback id; Type: DEFAULT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.feedback ALTER COLUMN id SET DEFAULT nextval('workflow.feedback_id_seq'::regclass);


--
-- Name: learnings id; Type: DEFAULT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.learnings ALTER COLUMN id SET DEFAULT nextval('workflow.learnings_id_seq'::regclass);


--
-- Name: model_rotation_schedule id; Type: DEFAULT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.model_rotation_schedule ALTER COLUMN id SET DEFAULT nextval('workflow.model_rotation_schedule_id_seq'::regclass);


--
-- Name: phases id; Type: DEFAULT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.phases ALTER COLUMN id SET DEFAULT nextval('workflow.phases_id_seq'::regclass);


--
-- Name: prediction_accuracy id; Type: DEFAULT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.prediction_accuracy ALTER COLUMN id SET DEFAULT nextval('workflow.prediction_accuracy_id_seq'::regclass);


--
-- Name: replays id; Type: DEFAULT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.replays ALTER COLUMN id SET DEFAULT nextval('workflow.replays_id_seq'::regclass);


--
-- Name: training_system_build id; Type: DEFAULT; Schema: workflow; Owner: claude
--

ALTER TABLE ONLY workflow.training_system_build ALTER COLUMN id SET DEFAULT nextval('workflow.training_system_build_id_seq'::regclass);


--
-- Name: worker_results id; Type: DEFAULT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.worker_results ALTER COLUMN id SET DEFAULT nextval('workflow.worker_results_id_seq'::regclass);


--
-- Name: background_tasks background_tasks_pkey; Type: CONSTRAINT; Schema: admin; Owner: claude
--

ALTER TABLE ONLY admin.background_tasks
    ADD CONSTRAINT background_tasks_pkey PRIMARY KEY (job_id);


--
-- Name: config config_pkey; Type: CONSTRAINT; Schema: admin; Owner: sfloess
--

ALTER TABLE ONLY admin.config
    ADD CONSTRAINT config_pkey PRIMARY KEY (key);


--
-- Name: api_keys api_keys_key_hash_key; Type: CONSTRAINT; Schema: auth; Owner: sfloess
--

ALTER TABLE ONLY auth.api_keys
    ADD CONSTRAINT api_keys_key_hash_key UNIQUE (key_hash);


--
-- Name: api_keys api_keys_key_prefix_key; Type: CONSTRAINT; Schema: auth; Owner: sfloess
--

ALTER TABLE ONLY auth.api_keys
    ADD CONSTRAINT api_keys_key_prefix_key UNIQUE (key_prefix);


--
-- Name: api_keys api_keys_pkey; Type: CONSTRAINT; Schema: auth; Owner: sfloess
--

ALTER TABLE ONLY auth.api_keys
    ADD CONSTRAINT api_keys_pkey PRIMARY KEY (id);


--
-- Name: secrets secrets_pkey; Type: CONSTRAINT; Schema: auth; Owner: sfloess
--

ALTER TABLE ONLY auth.secrets
    ADD CONSTRAINT secrets_pkey PRIMARY KEY (key);


--
-- Name: api_calls api_calls_pkey; Type: CONSTRAINT; Schema: auto_storage; Owner: claude
--

ALTER TABLE ONLY auto_storage.api_calls
    ADD CONSTRAINT api_calls_pkey PRIMARY KEY (id);


--
-- Name: api_keys api_keys_key_name_key; Type: CONSTRAINT; Schema: config; Owner: claude
--

ALTER TABLE ONLY config.api_keys
    ADD CONSTRAINT api_keys_key_name_key UNIQUE (key_name);


--
-- Name: api_keys api_keys_pkey; Type: CONSTRAINT; Schema: config; Owner: claude
--

ALTER TABLE ONLY config.api_keys
    ADD CONSTRAINT api_keys_pkey PRIMARY KEY (id);


--
-- Name: key_usage_log key_usage_log_pkey; Type: CONSTRAINT; Schema: config; Owner: claude
--

ALTER TABLE ONLY config.key_usage_log
    ADD CONSTRAINT key_usage_log_pkey PRIMARY KEY (id);


--
-- Name: entries entries_pkey; Type: CONSTRAINT; Schema: costs; Owner: sfloess
--

ALTER TABLE ONLY costs.entries
    ADD CONSTRAINT entries_pkey PRIMARY KEY (id);


--
-- Name: content_hashes content_hashes_pkey; Type: CONSTRAINT; Schema: dedup; Owner: claude
--

ALTER TABLE ONLY dedup.content_hashes
    ADD CONSTRAINT content_hashes_pkey PRIMARY KEY (hash);


--
-- Name: similar_pairs similar_pairs_hash1_hash2_key; Type: CONSTRAINT; Schema: dedup; Owner: claude
--

ALTER TABLE ONLY dedup.similar_pairs
    ADD CONSTRAINT similar_pairs_hash1_hash2_key UNIQUE (hash1, hash2);


--
-- Name: similar_pairs similar_pairs_pkey; Type: CONSTRAINT; Schema: dedup; Owner: claude
--

ALTER TABLE ONLY dedup.similar_pairs
    ADD CONSTRAINT similar_pairs_pkey PRIMARY KEY (id);


--
-- Name: chunks chunks_document_id_chunk_index_key; Type: CONSTRAINT; Schema: documents; Owner: sfloess
--

ALTER TABLE ONLY documents.chunks
    ADD CONSTRAINT chunks_document_id_chunk_index_key UNIQUE (document_id, chunk_index);


--
-- Name: chunks chunks_pkey; Type: CONSTRAINT; Schema: documents; Owner: sfloess
--

ALTER TABLE ONLY documents.chunks
    ADD CONSTRAINT chunks_pkey PRIMARY KEY (id);


--
-- Name: documents documents_file_hash_key; Type: CONSTRAINT; Schema: documents; Owner: sfloess
--

ALTER TABLE ONLY documents.documents
    ADD CONSTRAINT documents_file_hash_key UNIQUE (file_hash);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: documents; Owner: sfloess
--

ALTER TABLE ONLY documents.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: processing_log processing_log_pkey; Type: CONSTRAINT; Schema: documents; Owner: sfloess
--

ALTER TABLE ONLY documents.processing_log
    ADD CONSTRAINT processing_log_pkey PRIMARY KEY (id);


--
-- Name: benchmarks benchmarks_pkey; Type: CONSTRAINT; Schema: evaluation; Owner: sfloess
--

ALTER TABLE ONLY evaluation.benchmarks
    ADD CONSTRAINT benchmarks_pkey PRIMARY KEY (id);


--
-- Name: results results_pkey; Type: CONSTRAINT; Schema: evaluation; Owner: sfloess
--

ALTER TABLE ONLY evaluation.results
    ADD CONSTRAINT results_pkey PRIMARY KEY (id);


--
-- Name: registry registry_name_key; Type: CONSTRAINT; Schema: experiments; Owner: sfloess
--

ALTER TABLE ONLY experiments.registry
    ADD CONSTRAINT registry_name_key UNIQUE (name);


--
-- Name: registry registry_pkey; Type: CONSTRAINT; Schema: experiments; Owner: sfloess
--

ALTER TABLE ONLY experiments.registry
    ADD CONSTRAINT registry_pkey PRIMARY KEY (id);


--
-- Name: runs runs_pkey; Type: CONSTRAINT; Schema: experiments; Owner: sfloess
--

ALTER TABLE ONLY experiments.runs
    ADD CONSTRAINT runs_pkey PRIMARY KEY (id);


--
-- Name: command_results command_results_command_id_key; Type: CONSTRAINT; Schema: fleet; Owner: claude
--

ALTER TABLE ONLY fleet.command_results
    ADD CONSTRAINT command_results_command_id_key UNIQUE (command_id);


--
-- Name: command_results command_results_pkey; Type: CONSTRAINT; Schema: fleet; Owner: claude
--

ALTER TABLE ONLY fleet.command_results
    ADD CONSTRAINT command_results_pkey PRIMARY KEY (id);


--
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: fleet; Owner: claude
--

ALTER TABLE ONLY fleet.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (id);


--
-- Name: tasks tasks_task_id_key; Type: CONSTRAINT; Schema: fleet; Owner: claude
--

ALTER TABLE ONLY fleet.tasks
    ADD CONSTRAINT tasks_task_id_key UNIQUE (task_id);


--
-- Name: workers workers_hostname_key; Type: CONSTRAINT; Schema: fleet; Owner: claude
--

ALTER TABLE ONLY fleet.workers
    ADD CONSTRAINT workers_hostname_key UNIQUE (hostname);


--
-- Name: workers workers_pkey; Type: CONSTRAINT; Schema: fleet; Owner: claude
--

ALTER TABLE ONLY fleet.workers
    ADD CONSTRAINT workers_pkey PRIMARY KEY (id);


--
-- Name: workflows workflows_pkey; Type: CONSTRAINT; Schema: fleet; Owner: claude
--

ALTER TABLE ONLY fleet.workflows
    ADD CONSTRAINT workflows_pkey PRIMARY KEY (id);


--
-- Name: workflows workflows_workflow_id_key; Type: CONSTRAINT; Schema: fleet; Owner: claude
--

ALTER TABLE ONLY fleet.workflows
    ADD CONSTRAINT workflows_workflow_id_key UNIQUE (workflow_id);


--
-- Name: best_solutions best_solutions_pkey; Type: CONSTRAINT; Schema: ga; Owner: claude
--

ALTER TABLE ONLY ga.best_solutions
    ADD CONSTRAINT best_solutions_pkey PRIMARY KEY (use_case);


--
-- Name: convergence_metrics convergence_metrics_pkey; Type: CONSTRAINT; Schema: ga; Owner: claude
--

ALTER TABLE ONLY ga.convergence_metrics
    ADD CONSTRAINT convergence_metrics_pkey PRIMARY KEY (id);


--
-- Name: migration_log migration_log_pkey; Type: CONSTRAINT; Schema: ga; Owner: claude
--

ALTER TABLE ONLY ga.migration_log
    ADD CONSTRAINT migration_log_pkey PRIMARY KEY (id);


--
-- Name: populations populations_pkey; Type: CONSTRAINT; Schema: ga; Owner: claude
--

ALTER TABLE ONLY ga.populations
    ADD CONSTRAINT populations_pkey PRIMARY KEY (id);


--
-- Name: machines machines_hostname_key; Type: CONSTRAINT; Schema: inventory; Owner: claude
--

ALTER TABLE ONLY inventory.machines
    ADD CONSTRAINT machines_hostname_key UNIQUE (hostname);


--
-- Name: machines machines_pkey; Type: CONSTRAINT; Schema: inventory; Owner: claude
--

ALTER TABLE ONLY inventory.machines
    ADD CONSTRAINT machines_pkey PRIMARY KEY (id);


--
-- Name: chunks chunks_document_id_chunk_index_key; Type: CONSTRAINT; Schema: knowledge; Owner: sfloess
--

ALTER TABLE ONLY knowledge.chunks
    ADD CONSTRAINT chunks_document_id_chunk_index_key UNIQUE (document_id, chunk_index);


--
-- Name: chunks chunks_pkey; Type: CONSTRAINT; Schema: knowledge; Owner: sfloess
--

ALTER TABLE ONLY knowledge.chunks
    ADD CONSTRAINT chunks_pkey PRIMARY KEY (id);


--
-- Name: code_embeddings code_embeddings_file_chunk_key; Type: CONSTRAINT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.code_embeddings
    ADD CONSTRAINT code_embeddings_file_chunk_key UNIQUE (file_path, chunk_id);


--
-- Name: code_embeddings code_embeddings_pkey; Type: CONSTRAINT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.code_embeddings
    ADD CONSTRAINT code_embeddings_pkey PRIMARY KEY (id);


--
-- Name: concepts concepts_name_key; Type: CONSTRAINT; Schema: knowledge; Owner: sfloess
--

ALTER TABLE ONLY knowledge.concepts
    ADD CONSTRAINT concepts_name_key UNIQUE (name);


--
-- Name: concepts concepts_pkey; Type: CONSTRAINT; Schema: knowledge; Owner: sfloess
--

ALTER TABLE ONLY knowledge.concepts
    ADD CONSTRAINT concepts_pkey PRIMARY KEY (id);


--
-- Name: discovered_sources discovered_sources_pkey; Type: CONSTRAINT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.discovered_sources
    ADD CONSTRAINT discovered_sources_pkey PRIMARY KEY (id);


--
-- Name: discovered_sources discovered_sources_url_key; Type: CONSTRAINT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.discovered_sources
    ADD CONSTRAINT discovered_sources_url_key UNIQUE (url);


--
-- Name: discoveries discoveries_pkey; Type: CONSTRAINT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.discoveries
    ADD CONSTRAINT discoveries_pkey PRIMARY KEY (id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: embeddings embeddings_chunk_id_provider_key; Type: CONSTRAINT; Schema: knowledge; Owner: sfloess
--

ALTER TABLE ONLY knowledge.embeddings
    ADD CONSTRAINT embeddings_chunk_id_provider_key UNIQUE (chunk_id, provider);


--
-- Name: embeddings embeddings_pkey; Type: CONSTRAINT; Schema: knowledge; Owner: sfloess
--

ALTER TABLE ONLY knowledge.embeddings
    ADD CONSTRAINT embeddings_pkey PRIMARY KEY (id);


--
-- Name: entries entries_pkey; Type: CONSTRAINT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.entries
    ADD CONSTRAINT entries_pkey PRIMARY KEY (id);


--
-- Name: ingestion_queue ingestion_queue_pkey; Type: CONSTRAINT; Schema: knowledge; Owner: postgres
--

ALTER TABLE ONLY knowledge.ingestion_queue
    ADD CONSTRAINT ingestion_queue_pkey PRIMARY KEY (id);


--
-- Name: memory_chunks memory_chunks_pkey; Type: CONSTRAINT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.memory_chunks
    ADD CONSTRAINT memory_chunks_pkey PRIMARY KEY (id);


--
-- Name: provenance provenance_pkey; Type: CONSTRAINT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.provenance
    ADD CONSTRAINT provenance_pkey PRIMARY KEY (id);


--
-- Name: pubmed_articles pubmed_articles_article_id_key; Type: CONSTRAINT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.pubmed_articles
    ADD CONSTRAINT pubmed_articles_article_id_key UNIQUE (article_id);


--
-- Name: pubmed_articles pubmed_articles_pkey; Type: CONSTRAINT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.pubmed_articles
    ADD CONSTRAINT pubmed_articles_pkey PRIMARY KEY (id);


--
-- Name: relationships relationships_pkey; Type: CONSTRAINT; Schema: knowledge; Owner: sfloess
--

ALTER TABLE ONLY knowledge.relationships
    ADD CONSTRAINT relationships_pkey PRIMARY KEY (id);


--
-- Name: relationships relationships_source_id_target_id_relation_type_key; Type: CONSTRAINT; Schema: knowledge; Owner: sfloess
--

ALTER TABLE ONLY knowledge.relationships
    ADD CONSTRAINT relationships_source_id_target_id_relation_type_key UNIQUE (source_id, target_id, relation_type);


--
-- Name: research_findings research_findings_pkey; Type: CONSTRAINT; Schema: knowledge; Owner: sfloess
--

ALTER TABLE ONLY knowledge.research_findings
    ADD CONSTRAINT research_findings_pkey PRIMARY KEY (id);


--
-- Name: scraped_content scraped_content_content_hash_key; Type: CONSTRAINT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.scraped_content
    ADD CONSTRAINT scraped_content_content_hash_key UNIQUE (content_hash);


--
-- Name: scraped_content scraped_content_pkey; Type: CONSTRAINT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.scraped_content
    ADD CONSTRAINT scraped_content_pkey PRIMARY KEY (id);


--
-- Name: scraped_data scraped_data_file_hash_key; Type: CONSTRAINT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.scraped_data
    ADD CONSTRAINT scraped_data_file_hash_key UNIQUE (file_hash);


--
-- Name: scraped_data scraped_data_pkey; Type: CONSTRAINT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.scraped_data
    ADD CONSTRAINT scraped_data_pkey PRIMARY KEY (id);


--
-- Name: url_status url_status_pkey; Type: CONSTRAINT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.url_status
    ADD CONSTRAINT url_status_pkey PRIMARY KEY (id);


--
-- Name: url_status url_status_url_key; Type: CONSTRAINT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.url_status
    ADD CONSTRAINT url_status_url_key UNIQUE (url);


--
-- Name: verification_votes verification_votes_discovery_id_worker_id_key; Type: CONSTRAINT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.verification_votes
    ADD CONSTRAINT verification_votes_discovery_id_worker_id_key UNIQUE (discovery_id, worker_id);


--
-- Name: verification_votes verification_votes_pkey; Type: CONSTRAINT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.verification_votes
    ADD CONSTRAINT verification_votes_pkey PRIMARY KEY (id);


--
-- Name: web_articles web_articles_pkey; Type: CONSTRAINT; Schema: knowledge; Owner: sfloess
--

ALTER TABLE ONLY knowledge.web_articles
    ADD CONSTRAINT web_articles_pkey PRIMARY KEY (id);


--
-- Name: web_articles web_articles_url_key; Type: CONSTRAINT; Schema: knowledge; Owner: sfloess
--

ALTER TABLE ONLY knowledge.web_articles
    ADD CONSTRAINT web_articles_url_key UNIQUE (url);


--
-- Name: web_scrape web_scrape_pkey; Type: CONSTRAINT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.web_scrape
    ADD CONSTRAINT web_scrape_pkey PRIMARY KEY (id);


--
-- Name: analogical_patterns analogical_patterns_pkey; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.analogical_patterns
    ADD CONSTRAINT analogical_patterns_pkey PRIMARY KEY (pattern_id);


--
-- Name: api_models api_models_pkey; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.api_models
    ADD CONSTRAINT api_models_pkey PRIMARY KEY (id);


--
-- Name: api_models api_models_provider_model_id_key; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.api_models
    ADD CONSTRAINT api_models_provider_model_id_key UNIQUE (provider, model_id);


--
-- Name: bandit_models bandit_models_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.bandit_models
    ADD CONSTRAINT bandit_models_pkey PRIMARY KEY (model_name);


--
-- Name: claude_memory claude_memory_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.claude_memory
    ADD CONSTRAINT claude_memory_pkey PRIMARY KEY (id);


--
-- Name: codebase_analysis codebase_analysis_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.codebase_analysis
    ADD CONSTRAINT codebase_analysis_pkey PRIMARY KEY (id);


--
-- Name: comprehensive_research comprehensive_research_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.comprehensive_research
    ADD CONSTRAINT comprehensive_research_pkey PRIMARY KEY (id);


--
-- Name: concepts concepts_name_key; Type: CONSTRAINT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.concepts
    ADD CONSTRAINT concepts_name_key UNIQUE (name);


--
-- Name: concepts concepts_pkey; Type: CONSTRAINT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.concepts
    ADD CONSTRAINT concepts_pkey PRIMARY KEY (id);


--
-- Name: confidence_observations confidence_observations_pkey; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.confidence_observations
    ADD CONSTRAINT confidence_observations_pkey PRIMARY KEY (id);


--
-- Name: consciousness_research consciousness_research_original_id_key; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.consciousness_research
    ADD CONSTRAINT consciousness_research_original_id_key UNIQUE (original_id);


--
-- Name: consciousness_research consciousness_research_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.consciousness_research
    ADD CONSTRAINT consciousness_research_pkey PRIMARY KEY (id);


--
-- Name: continual_learning_roadmap continual_learning_roadmap_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.continual_learning_roadmap
    ADD CONSTRAINT continual_learning_roadmap_pkey PRIMARY KEY (id);


--
-- Name: continual_learning_roadmap continual_learning_roadmap_technique_key; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.continual_learning_roadmap
    ADD CONSTRAINT continual_learning_roadmap_technique_key UNIQUE (technique);


--
-- Name: conversation_learnings conversation_learnings_pkey; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.conversation_learnings
    ADD CONSTRAINT conversation_learnings_pkey PRIMARY KEY (id);


--
-- Name: diversity_violations diversity_violations_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.diversity_violations
    ADD CONSTRAINT diversity_violations_pkey PRIMARY KEY (id);


--
-- Name: error_logs error_logs_pkey; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.error_logs
    ADD CONSTRAINT error_logs_pkey PRIMARY KEY (id);


--
-- Name: exp3_arms exp3_arms_pkey; Type: CONSTRAINT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.exp3_arms
    ADD CONSTRAINT exp3_arms_pkey PRIMARY KEY (arm_id);


--
-- Name: exp3_state exp3_state_pkey; Type: CONSTRAINT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.exp3_state
    ADD CONSTRAINT exp3_state_pkey PRIMARY KEY (key);


--
-- Name: experiences_experiment experiences_experiment_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.experiences_experiment
    ADD CONSTRAINT experiences_experiment_pkey PRIMARY KEY (id);


--
-- Name: experiences experiences_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.experiences
    ADD CONSTRAINT experiences_pkey PRIMARY KEY (id);


--
-- Name: experiment_results experiment_results_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.experiment_results
    ADD CONSTRAINT experiment_results_pkey PRIMARY KEY (id);


--
-- Name: fine_tuning_queue fine_tuning_queue_pkey; Type: CONSTRAINT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.fine_tuning_queue
    ADD CONSTRAINT fine_tuning_queue_pkey PRIMARY KEY (id);


--
-- Name: free_models free_models_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.free_models
    ADD CONSTRAINT free_models_pkey PRIMARY KEY (id);


--
-- Name: free_models free_models_provider_model_id_key; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.free_models
    ADD CONSTRAINT free_models_provider_model_id_key UNIQUE (provider, model_id);


--
-- Name: ga_configs ga_configs_pkey; Type: CONSTRAINT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.ga_configs
    ADD CONSTRAINT ga_configs_pkey PRIMARY KEY (id);


--
-- Name: git_commits git_commits_commit_hash_key; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.git_commits
    ADD CONSTRAINT git_commits_commit_hash_key UNIQUE (commit_hash);


--
-- Name: git_commits git_commits_pkey; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.git_commits
    ADD CONSTRAINT git_commits_pkey PRIMARY KEY (id);


--
-- Name: gitlab_issues gitlab_issues_issue_id_key; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.gitlab_issues
    ADD CONSTRAINT gitlab_issues_issue_id_key UNIQUE (issue_id);


--
-- Name: gitlab_issues gitlab_issues_pkey; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.gitlab_issues
    ADD CONSTRAINT gitlab_issues_pkey PRIMARY KEY (id);


--
-- Name: icl_examples icl_examples_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.icl_examples
    ADD CONSTRAINT icl_examples_pkey PRIMARY KEY (id);


--
-- Name: improvements improvements_pkey; Type: CONSTRAINT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.improvements
    ADD CONSTRAINT improvements_pkey PRIMARY KEY (id);


--
-- Name: infrastructure_knowledge infrastructure_knowledge_pkey; Type: CONSTRAINT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.infrastructure_knowledge
    ADD CONSTRAINT infrastructure_knowledge_pkey PRIMARY KEY (id);


--
-- Name: knowledge_embeddings knowledge_embeddings_pkey; Type: CONSTRAINT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.knowledge_embeddings
    ADD CONSTRAINT knowledge_embeddings_pkey PRIMARY KEY (id);


--
-- Name: linucb_arms linucb_arms_pkey; Type: CONSTRAINT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.linucb_arms
    ADD CONSTRAINT linucb_arms_pkey PRIMARY KEY (arm_id);


--
-- Name: load_balancer_state load_balancer_state_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.load_balancer_state
    ADD CONSTRAINT load_balancer_state_pkey PRIMARY KEY (id);


--
-- Name: load_balancer_state load_balancer_state_timestamp_model_key; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.load_balancer_state
    ADD CONSTRAINT load_balancer_state_timestamp_model_key UNIQUE ("timestamp", model);


--
-- Name: massive_validations massive_validations_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.massive_validations
    ADD CONSTRAINT massive_validations_pkey PRIMARY KEY (validation_id);


--
-- Name: memories memories_name_key; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.memories
    ADD CONSTRAINT memories_name_key UNIQUE (name);


--
-- Name: memories memories_pkey; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.memories
    ADD CONSTRAINT memories_pkey PRIMARY KEY (id);


--
-- Name: memory memory_pkey; Type: CONSTRAINT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.memory
    ADD CONSTRAINT memory_pkey PRIMARY KEY (id);


--
-- Name: metadata_schema_test metadata_schema_test_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.metadata_schema_test
    ADD CONSTRAINT metadata_schema_test_pkey PRIMARY KEY (id);


--
-- Name: model_capabilities model_capabilities_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.model_capabilities
    ADD CONSTRAINT model_capabilities_pkey PRIMARY KEY (model_id);


--
-- Name: model_censorship model_censorship_model_name_provider_location_key; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.model_censorship
    ADD CONSTRAINT model_censorship_model_name_provider_location_key UNIQUE (model_name, provider, location);


--
-- Name: model_censorship model_censorship_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.model_censorship
    ADD CONSTRAINT model_censorship_pkey PRIMARY KEY (id);


--
-- Name: model_quotas model_quotas_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.model_quotas
    ADD CONSTRAINT model_quotas_pkey PRIMARY KEY (model);


--
-- Name: pdf_knowledge pdf_knowledge_pkey; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.pdf_knowledge
    ADD CONSTRAINT pdf_knowledge_pkey PRIMARY KEY (id);


--
-- Name: pdf_metadata pdf_metadata_pdf_path_key; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.pdf_metadata
    ADD CONSTRAINT pdf_metadata_pdf_path_key UNIQUE (pdf_path);


--
-- Name: pdf_metadata pdf_metadata_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.pdf_metadata
    ADD CONSTRAINT pdf_metadata_pkey PRIMARY KEY (id);


--
-- Name: policy_performance policy_performance_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.policy_performance
    ADD CONSTRAINT policy_performance_pkey PRIMARY KEY (policy_id);


--
-- Name: preference_learner_stats preference_learner_stats_pkey; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.preference_learner_stats
    ADD CONSTRAINT preference_learner_stats_pkey PRIMARY KEY (model_name);


--
-- Name: procedural_rules procedural_rules_condition_hash_action_key; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.procedural_rules
    ADD CONSTRAINT procedural_rules_condition_hash_action_key UNIQUE (condition_hash, action);


--
-- Name: procedural_rules procedural_rules_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.procedural_rules
    ADD CONSTRAINT procedural_rules_pkey PRIMARY KEY (id);


--
-- Name: queue_failure_patterns queue_failure_patterns_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.queue_failure_patterns
    ADD CONSTRAINT queue_failure_patterns_pkey PRIMARY KEY (id);


--
-- Name: queue_health_metrics queue_health_metrics_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.queue_health_metrics
    ADD CONSTRAINT queue_health_metrics_pkey PRIMARY KEY (id);


--
-- Name: queue_predictions queue_predictions_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.queue_predictions
    ADD CONSTRAINT queue_predictions_pkey PRIMARY KEY (id);


--
-- Name: reasoning_patterns reasoning_patterns_pkey; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.reasoning_patterns
    ADD CONSTRAINT reasoning_patterns_pkey PRIMARY KEY (id);


--
-- Name: relationships relationships_pkey; Type: CONSTRAINT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.relationships
    ADD CONSTRAINT relationships_pkey PRIMARY KEY (id);


--
-- Name: request_history request_history_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.request_history
    ADD CONSTRAINT request_history_pkey PRIMARY KEY (id);


--
-- Name: request_history request_history_request_id_key; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.request_history
    ADD CONSTRAINT request_history_request_id_key UNIQUE (request_id);


--
-- Name: research_chunks research_chunks_doc_id_chunk_index_key; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.research_chunks
    ADD CONSTRAINT research_chunks_doc_id_chunk_index_key UNIQUE (doc_id, chunk_index);


--
-- Name: research_chunks research_chunks_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.research_chunks
    ADD CONSTRAINT research_chunks_pkey PRIMARY KEY (id);


--
-- Name: research_documents research_documents_doc_id_key; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.research_documents
    ADD CONSTRAINT research_documents_doc_id_key UNIQUE (doc_id);


--
-- Name: research_documents research_documents_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.research_documents
    ADD CONSTRAINT research_documents_pkey PRIMARY KEY (id);


--
-- Name: research_findings research_findings_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.research_findings
    ADD CONSTRAINT research_findings_pkey PRIMARY KEY (id);


--
-- Name: research_full research_full_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.research_full
    ADD CONSTRAINT research_full_pkey PRIMARY KEY (id);


--
-- Name: scraping_queue scraping_queue_pkey; Type: CONSTRAINT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.scraping_queue
    ADD CONSTRAINT scraping_queue_pkey PRIMARY KEY (id);


--
-- Name: scraping_queue scraping_queue_topic_key; Type: CONSTRAINT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.scraping_queue
    ADD CONSTRAINT scraping_queue_topic_key UNIQUE (topic);


--
-- Name: security_policies security_policies_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.security_policies
    ADD CONSTRAINT security_policies_pkey PRIMARY KEY (id);


--
-- Name: security_policies security_policies_policy_id_key; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.security_policies
    ADD CONSTRAINT security_policies_policy_id_key UNIQUE (policy_id);


--
-- Name: security_violations security_violations_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.security_violations
    ADD CONSTRAINT security_violations_pkey PRIMARY KEY (id);


--
-- Name: security_violations security_violations_violation_id_key; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.security_violations
    ADD CONSTRAINT security_violations_violation_id_key UNIQUE (violation_id);


--
-- Name: self_discoveries self_discoveries_pkey; Type: CONSTRAINT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.self_discoveries
    ADD CONSTRAINT self_discoveries_pkey PRIMARY KEY (id);


--
-- Name: service_mesh_models service_mesh_models_pkey; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.service_mesh_models
    ADD CONSTRAINT service_mesh_models_pkey PRIMARY KEY (model_name);


--
-- Name: session_chunks session_chunks_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.session_chunks
    ADD CONSTRAINT session_chunks_pkey PRIMARY KEY (id);


--
-- Name: session_chunks session_chunks_session_id_chunk_index_key; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.session_chunks
    ADD CONSTRAINT session_chunks_session_id_chunk_index_key UNIQUE (session_id, chunk_index);


--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (id);


--
-- Name: sessions sessions_session_id_key; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.sessions
    ADD CONSTRAINT sessions_session_id_key UNIQUE (session_id);


--
-- Name: specialist_models specialist_models_pkey; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.specialist_models
    ADD CONSTRAINT specialist_models_pkey PRIMARY KEY (model_name);


--
-- Name: strategy_performance_multi strategy_performance_multi_capability_task_type_strategy_key; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.strategy_performance_multi
    ADD CONSTRAINT strategy_performance_multi_capability_task_type_strategy_key UNIQUE (capability, task_type, strategy);


--
-- Name: strategy_performance_multi strategy_performance_multi_pkey; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.strategy_performance_multi
    ADD CONSTRAINT strategy_performance_multi_pkey PRIMARY KEY (id);


--
-- Name: strategy_performance strategy_performance_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.strategy_performance
    ADD CONSTRAINT strategy_performance_pkey PRIMARY KEY (strategy);


--
-- Name: test_results test_results_pkey; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.test_results
    ADD CONSTRAINT test_results_pkey PRIMARY KEY (id);


--
-- Name: ucb1_arms ucb1_arms_pkey; Type: CONSTRAINT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.ucb1_arms
    ADD CONSTRAINT ucb1_arms_pkey PRIMARY KEY (arm_id);


--
-- Name: ucb1_state ucb1_state_pkey; Type: CONSTRAINT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.ucb1_state
    ADD CONSTRAINT ucb1_state_pkey PRIMARY KEY (key);


--
-- Name: session_chunks unique_content_hash; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.session_chunks
    ADD CONSTRAINT unique_content_hash UNIQUE (content_hash);


--
-- Name: vec_claude_memory vec_claude_memory_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.vec_claude_memory
    ADD CONSTRAINT vec_claude_memory_pkey PRIMARY KEY (id);


--
-- Name: vec_scale_test_1783055901 vec_scale_test_1783055901_pkey; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.vec_scale_test_1783055901
    ADD CONSTRAINT vec_scale_test_1783055901_pkey PRIMARY KEY (id);


--
-- Name: vec_scale_test_1783055962 vec_scale_test_1783055962_pkey; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.vec_scale_test_1783055962
    ADD CONSTRAINT vec_scale_test_1783055962_pkey PRIMARY KEY (id);


--
-- Name: vec_scale_test_1783055991 vec_scale_test_1783055991_pkey; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.vec_scale_test_1783055991
    ADD CONSTRAINT vec_scale_test_1783055991_pkey PRIMARY KEY (id);


--
-- Name: vec_scale_test_1783056573 vec_scale_test_1783056573_pkey; Type: CONSTRAINT; Schema: learning; Owner: sfloess
--

ALTER TABLE ONLY learning.vec_scale_test_1783056573
    ADD CONSTRAINT vec_scale_test_1783056573_pkey PRIMARY KEY (id);


--
-- Name: weak_topics weak_topics_pkey; Type: CONSTRAINT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.weak_topics
    ADD CONSTRAINT weak_topics_pkey PRIMARY KEY (topic);


--
-- Name: web_synthesis web_synthesis_pkey; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.web_synthesis
    ADD CONSTRAINT web_synthesis_pkey PRIMARY KEY (id);


--
-- Name: web_synthesis web_synthesis_source_line_batch_id_key; Type: CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.web_synthesis
    ADD CONSTRAINT web_synthesis_source_line_batch_id_key UNIQUE (source_line, batch_id);


--
-- Name: api_health_checks api_health_checks_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.api_health_checks
    ADD CONSTRAINT api_health_checks_pkey PRIMARY KEY (id);


--
-- Name: api_health_status api_health_status_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.api_health_status
    ADD CONSTRAINT api_health_status_pkey PRIMARY KEY (provider);


--
-- Name: api_usage api_usage_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.api_usage
    ADD CONSTRAINT api_usage_pkey PRIMARY KEY (id);


--
-- Name: arbiter_decisions arbiter_decisions_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: postgres
--

ALTER TABLE ONLY monitoring.arbiter_decisions
    ADD CONSTRAINT arbiter_decisions_pkey PRIMARY KEY (id);


--
-- Name: circuit_breaker_events circuit_breaker_events_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.circuit_breaker_events
    ADD CONSTRAINT circuit_breaker_events_pkey PRIMARY KEY (id);


--
-- Name: compliance_alerts compliance_alerts_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.compliance_alerts
    ADD CONSTRAINT compliance_alerts_pkey PRIMARY KEY (id);


--
-- Name: confidence_calibration confidence_calibration_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.confidence_calibration
    ADD CONSTRAINT confidence_calibration_pkey PRIMARY KEY (id);


--
-- Name: diversity_alerts diversity_alerts_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.diversity_alerts
    ADD CONSTRAINT diversity_alerts_pkey PRIMARY KEY (id);


--
-- Name: dual_review_results dual_review_results_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: postgres
--

ALTER TABLE ONLY monitoring.dual_review_results
    ADD CONSTRAINT dual_review_results_pkey PRIMARY KEY (id);


--
-- Name: embedding_provider_usage embedding_provider_usage_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: postgres
--

ALTER TABLE ONLY monitoring.embedding_provider_usage
    ADD CONSTRAINT embedding_provider_usage_pkey PRIMARY KEY (id);


--
-- Name: execution_log execution_log_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.execution_log
    ADD CONSTRAINT execution_log_pkey PRIMARY KEY (id);


--
-- Name: execution_summary execution_summary_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.execution_summary
    ADD CONSTRAINT execution_summary_pkey PRIMARY KEY (id);


--
-- Name: external_api_calls external_api_calls_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.external_api_calls
    ADD CONSTRAINT external_api_calls_pkey PRIMARY KEY (id);


--
-- Name: fleet_health fleet_health_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.fleet_health
    ADD CONSTRAINT fleet_health_pkey PRIMARY KEY (id);


--
-- Name: health_checks health_checks_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.health_checks
    ADD CONSTRAINT health_checks_pkey PRIMARY KEY (id);


--
-- Name: health_predictions health_predictions_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.health_predictions
    ADD CONSTRAINT health_predictions_pkey PRIMARY KEY (id);


--
-- Name: human_corrections human_corrections_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.human_corrections
    ADD CONSTRAINT human_corrections_pkey PRIMARY KEY (id);


--
-- Name: llm_provider_usage llm_provider_usage_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: postgres
--

ALTER TABLE ONLY monitoring.llm_provider_usage
    ADD CONSTRAINT llm_provider_usage_pkey PRIMARY KEY (id);


--
-- Name: model_capabilities model_capabilities_model_task_type_key; Type: CONSTRAINT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.model_capabilities
    ADD CONSTRAINT model_capabilities_model_task_type_key UNIQUE (model, task_type);


--
-- Name: model_capabilities model_capabilities_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.model_capabilities
    ADD CONSTRAINT model_capabilities_pkey PRIMARY KEY (id);


--
-- Name: model_retraining model_retraining_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.model_retraining
    ADD CONSTRAINT model_retraining_pkey PRIMARY KEY (id);


--
-- Name: model_selections model_selections_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.model_selections
    ADD CONSTRAINT model_selections_pkey PRIMARY KEY (id);


--
-- Name: model_tuning model_tuning_model_task_type_key; Type: CONSTRAINT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.model_tuning
    ADD CONSTRAINT model_tuning_model_task_type_key UNIQUE (model, task_type);


--
-- Name: model_tuning model_tuning_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.model_tuning
    ADD CONSTRAINT model_tuning_pkey PRIMARY KEY (id);


--
-- Name: model_usage model_usage_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.model_usage
    ADD CONSTRAINT model_usage_pkey PRIMARY KEY (id);


--
-- Name: network_latency_matrix network_latency_matrix_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.network_latency_matrix
    ADD CONSTRAINT network_latency_matrix_pkey PRIMARY KEY (id);


--
-- Name: network_measurements network_measurements_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.network_measurements
    ADD CONSTRAINT network_measurements_pkey PRIMARY KEY (id);


--
-- Name: network_predictions network_predictions_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.network_predictions
    ADD CONSTRAINT network_predictions_pkey PRIMARY KEY (id);


--
-- Name: prediction_accuracy prediction_accuracy_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: postgres
--

ALTER TABLE ONLY monitoring.prediction_accuracy
    ADD CONSTRAINT prediction_accuracy_pkey PRIMARY KEY (id);


--
-- Name: queue_health queue_health_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.queue_health
    ADD CONSTRAINT queue_health_pkey PRIMARY KEY (id);


--
-- Name: rate_limit_hits rate_limit_hits_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.rate_limit_hits
    ADD CONSTRAINT rate_limit_hits_pkey PRIMARY KEY (id);


--
-- Name: rate_limit_requests rate_limit_requests_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.rate_limit_requests
    ADD CONSTRAINT rate_limit_requests_pkey PRIMARY KEY (id);


--
-- Name: rate_limit_state rate_limit_state_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.rate_limit_state
    ADD CONSTRAINT rate_limit_state_pkey PRIMARY KEY (api_key_id);


--
-- Name: rate_limits rate_limits_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.rate_limits
    ADD CONSTRAINT rate_limits_pkey PRIMARY KEY (provider);


--
-- Name: resource_estimation_coefficients resource_estimation_coefficients_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.resource_estimation_coefficients
    ADD CONSTRAINT resource_estimation_coefficients_pkey PRIMARY KEY (id);


--
-- Name: resource_estimation_log resource_estimation_log_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.resource_estimation_log
    ADD CONSTRAINT resource_estimation_log_pkey PRIMARY KEY (id);


--
-- Name: resource_usage resource_usage_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.resource_usage
    ADD CONSTRAINT resource_usage_pkey PRIMARY KEY (id);


--
-- Name: scraping_metrics scraping_metrics_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.scraping_metrics
    ADD CONSTRAINT scraping_metrics_pkey PRIMARY KEY (id);


--
-- Name: scraping_output scraping_output_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.scraping_output
    ADD CONSTRAINT scraping_output_pkey PRIMARY KEY (id);


--
-- Name: session_learnings session_learnings_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.session_learnings
    ADD CONSTRAINT session_learnings_pkey PRIMARY KEY (id);


--
-- Name: task_attribution task_attribution_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.task_attribution
    ADD CONSTRAINT task_attribution_pkey PRIMARY KEY (id);


--
-- Name: training_jobs training_jobs_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.training_jobs
    ADD CONSTRAINT training_jobs_pkey PRIMARY KEY (id);


--
-- Name: worker_assignments worker_assignments_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: postgres
--

ALTER TABLE ONLY monitoring.worker_assignments
    ADD CONSTRAINT worker_assignments_pkey PRIMARY KEY (id);


--
-- Name: workers workers_hostname_key; Type: CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.workers
    ADD CONSTRAINT workers_hostname_key UNIQUE (hostname);


--
-- Name: workers workers_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.workers
    ADD CONSTRAINT workers_pkey PRIMARY KEY (id);


--
-- Name: auto_storage auto_storage_pkey; Type: CONSTRAINT; Schema: orchestration; Owner: sfloess
--

ALTER TABLE ONLY orchestration.auto_storage
    ADD CONSTRAINT auto_storage_pkey PRIMARY KEY (id);


--
-- Name: conversation_history conversation_history_pkey; Type: CONSTRAINT; Schema: orchestration; Owner: sfloess
--

ALTER TABLE ONLY orchestration.conversation_history
    ADD CONSTRAINT conversation_history_pkey PRIMARY KEY (id);


--
-- Name: conversation_history conversation_history_session_id_turn_number_key; Type: CONSTRAINT; Schema: orchestration; Owner: sfloess
--

ALTER TABLE ONLY orchestration.conversation_history
    ADD CONSTRAINT conversation_history_session_id_turn_number_key UNIQUE (session_id, turn_number);


--
-- Name: gitlab_issues gitlab_issues_issue_id_key; Type: CONSTRAINT; Schema: orchestration; Owner: sfloess
--

ALTER TABLE ONLY orchestration.gitlab_issues
    ADD CONSTRAINT gitlab_issues_issue_id_key UNIQUE (issue_id);


--
-- Name: gitlab_issues gitlab_issues_pkey; Type: CONSTRAINT; Schema: orchestration; Owner: sfloess
--

ALTER TABLE ONLY orchestration.gitlab_issues
    ADD CONSTRAINT gitlab_issues_pkey PRIMARY KEY (id);


--
-- Name: task_dependencies task_dependencies_from_task_id_to_task_id_dependency_type_key; Type: CONSTRAINT; Schema: orchestration; Owner: sfloess
--

ALTER TABLE ONLY orchestration.task_dependencies
    ADD CONSTRAINT task_dependencies_from_task_id_to_task_id_dependency_type_key UNIQUE (from_task_id, to_task_id, dependency_type);


--
-- Name: task_dependencies task_dependencies_pkey; Type: CONSTRAINT; Schema: orchestration; Owner: sfloess
--

ALTER TABLE ONLY orchestration.task_dependencies
    ADD CONSTRAINT task_dependencies_pkey PRIMARY KEY (id);


--
-- Name: task_progress_log task_progress_log_pkey; Type: CONSTRAINT; Schema: orchestration; Owner: sfloess
--

ALTER TABLE ONLY orchestration.task_progress_log
    ADD CONSTRAINT task_progress_log_pkey PRIMARY KEY (id);


--
-- Name: task_queue task_queue_pkey; Type: CONSTRAINT; Schema: orchestration; Owner: sfloess
--

ALTER TABLE ONLY orchestration.task_queue
    ADD CONSTRAINT task_queue_pkey PRIMARY KEY (id);


--
-- Name: task_queue task_queue_task_id_key; Type: CONSTRAINT; Schema: orchestration; Owner: sfloess
--

ALTER TABLE ONLY orchestration.task_queue
    ADD CONSTRAINT task_queue_task_id_key UNIQUE (task_id);


--
-- Name: worker_heartbeats worker_heartbeats_pkey; Type: CONSTRAINT; Schema: orchestration; Owner: sfloess
--

ALTER TABLE ONLY orchestration.worker_heartbeats
    ADD CONSTRAINT worker_heartbeats_pkey PRIMARY KEY (worker_id);


--
-- Name: file_locks file_locks_pkey; Type: CONSTRAINT; Schema: orchestrator; Owner: sfloess
--

ALTER TABLE ONLY orchestrator.file_locks
    ADD CONSTRAINT file_locks_pkey PRIMARY KEY (file_path);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: orchestrator; Owner: sfloess
--

ALTER TABLE ONLY orchestrator.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (message_id);


--
-- Name: node_performance node_performance_pkey; Type: CONSTRAINT; Schema: orchestrator; Owner: sfloess
--

ALTER TABLE ONLY orchestrator.node_performance
    ADD CONSTRAINT node_performance_pkey PRIMARY KEY (node_id, task_type);


--
-- Name: schema_version schema_version_pkey; Type: CONSTRAINT; Schema: orchestrator; Owner: sfloess
--

ALTER TABLE ONLY orchestrator.schema_version
    ADD CONSTRAINT schema_version_pkey PRIMARY KEY (version);


--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: orchestrator; Owner: sfloess
--

ALTER TABLE ONLY orchestrator.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (session_id);


--
-- Name: work_queue work_queue_pkey; Type: CONSTRAINT; Schema: orchestrator; Owner: sfloess
--

ALTER TABLE ONLY orchestrator.work_queue
    ADD CONSTRAINT work_queue_pkey PRIMARY KEY (work_id);


--
-- Name: chunks chunks_chunk_id_key; Type: CONSTRAINT; Schema: processing; Owner: sfloess
--

ALTER TABLE ONLY processing.chunks
    ADD CONSTRAINT chunks_chunk_id_key UNIQUE (chunk_id);


--
-- Name: chunks chunks_pkey; Type: CONSTRAINT; Schema: processing; Owner: sfloess
--

ALTER TABLE ONLY processing.chunks
    ADD CONSTRAINT chunks_pkey PRIMARY KEY (id);


--
-- Name: processing_stats processing_stats_pkey; Type: CONSTRAINT; Schema: processing; Owner: sfloess
--

ALTER TABLE ONLY processing.processing_stats
    ADD CONSTRAINT processing_stats_pkey PRIMARY KEY (id);


--
-- Name: source_files source_files_file_path_key; Type: CONSTRAINT; Schema: processing; Owner: sfloess
--

ALTER TABLE ONLY processing.source_files
    ADD CONSTRAINT source_files_file_path_key UNIQUE (file_path);


--
-- Name: source_files source_files_pkey; Type: CONSTRAINT; Schema: processing; Owner: sfloess
--

ALTER TABLE ONLY processing.source_files
    ADD CONSTRAINT source_files_pkey PRIMARY KEY (id);


--
-- Name: chunks unique_file_chunk; Type: CONSTRAINT; Schema: processing; Owner: sfloess
--

ALTER TABLE ONLY processing.chunks
    ADD CONSTRAINT unique_file_chunk UNIQUE (source_file_id, chunk_index);


--
-- Name: work_queue work_queue_pkey; Type: CONSTRAINT; Schema: processing; Owner: sfloess
--

ALTER TABLE ONLY processing.work_queue
    ADD CONSTRAINT work_queue_pkey PRIMARY KEY (id);


--
-- Name: workers workers_pkey; Type: CONSTRAINT; Schema: processing; Owner: sfloess
--

ALTER TABLE ONLY processing.workers
    ADD CONSTRAINT workers_pkey PRIMARY KEY (worker_id);


--
-- Name: api_cache api_cache_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.api_cache
    ADD CONSTRAINT api_cache_pkey PRIMARY KEY (request_hash);


--
-- Name: api_embedding_usage api_embedding_usage_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.api_embedding_usage
    ADD CONSTRAINT api_embedding_usage_pkey PRIMARY KEY (id);


--
-- Name: api_failures api_failures_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.api_failures
    ADD CONSTRAINT api_failures_pkey PRIMARY KEY (id);


--
-- Name: api_models api_models_model_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.api_models
    ADD CONSTRAINT api_models_model_name_key UNIQUE (model_name);


--
-- Name: api_models api_models_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.api_models
    ADD CONSTRAINT api_models_pkey PRIMARY KEY (id);


--
-- Name: api_usage api_usage_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.api_usage
    ADD CONSTRAINT api_usage_pkey PRIMARY KEY (id);


--
-- Name: pdf_knowledge pdf_knowledge_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pdf_knowledge
    ADD CONSTRAINT pdf_knowledge_pkey PRIMARY KEY (id);


--
-- Name: session_context session_context_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.session_context
    ADD CONSTRAINT session_context_pkey PRIMARY KEY (session_id);


--
-- Name: batch_test batch_test_pkey; Type: CONSTRAINT; Schema: queue; Owner: sfloess
--

ALTER TABLE ONLY queue.batch_test
    ADD CONSTRAINT batch_test_pkey PRIMARY KEY (id);


--
-- Name: chunk chunk_pkey; Type: CONSTRAINT; Schema: queue; Owner: postgres
--

ALTER TABLE ONLY queue.chunk
    ADD CONSTRAINT chunk_pkey PRIMARY KEY (id);


--
-- Name: embed embed_pkey; Type: CONSTRAINT; Schema: queue; Owner: postgres
--

ALTER TABLE ONLY queue.embed
    ADD CONSTRAINT embed_pkey PRIMARY KEY (id);


--
-- Name: graph graph_pkey; Type: CONSTRAINT; Schema: queue; Owner: postgres
--

ALTER TABLE ONLY queue.graph
    ADD CONSTRAINT graph_pkey PRIMARY KEY (id);


--
-- Name: store store_pkey; Type: CONSTRAINT; Schema: queue; Owner: postgres
--

ALTER TABLE ONLY queue.store
    ADD CONSTRAINT store_pkey PRIMARY KEY (id);


--
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: queue; Owner: claude
--

ALTER TABLE ONLY queue.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (id);


--
-- Name: worker_heartbeat worker_heartbeat_pkey; Type: CONSTRAINT; Schema: queue; Owner: sfloess
--

ALTER TABLE ONLY queue.worker_heartbeat
    ADD CONSTRAINT worker_heartbeat_pkey PRIMARY KEY (worker_id);


--
-- Name: evidence evidence_pkey; Type: CONSTRAINT; Schema: reasoning; Owner: claude
--

ALTER TABLE ONLY reasoning.evidence
    ADD CONSTRAINT evidence_pkey PRIMARY KEY (id);


--
-- Name: explanations explanations_evidence_id_hypothesis_id_key; Type: CONSTRAINT; Schema: reasoning; Owner: claude
--

ALTER TABLE ONLY reasoning.explanations
    ADD CONSTRAINT explanations_evidence_id_hypothesis_id_key UNIQUE (evidence_id, hypothesis_id);


--
-- Name: explanations explanations_pkey; Type: CONSTRAINT; Schema: reasoning; Owner: claude
--

ALTER TABLE ONLY reasoning.explanations
    ADD CONSTRAINT explanations_pkey PRIMARY KEY (id);


--
-- Name: hypotheses hypotheses_pkey; Type: CONSTRAINT; Schema: reasoning; Owner: claude
--

ALTER TABLE ONLY reasoning.hypotheses
    ADD CONSTRAINT hypotheses_pkey PRIMARY KEY (id);


--
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: scraping; Owner: sfloess
--

ALTER TABLE ONLY scraping.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (id);


--
-- Name: tasks tasks_url_key; Type: CONSTRAINT; Schema: scraping; Owner: sfloess
--

ALTER TABLE ONLY scraping.tasks
    ADD CONSTRAINT tasks_url_key UNIQUE (url);


--
-- Name: knowledge_base knowledge_base_pkey; Type: CONSTRAINT; Schema: search; Owner: postgres
--

ALTER TABLE ONLY search.knowledge_base
    ADD CONSTRAINT knowledge_base_pkey PRIMARY KEY (id);


--
-- Name: api_calls api_calls_pkey; Type: CONSTRAINT; Schema: storage; Owner: claude
--

ALTER TABLE ONLY storage.api_calls
    ADD CONSTRAINT api_calls_pkey PRIMARY KEY (id);


--
-- Name: ab_test_plans ab_test_plans_name_created_at_key; Type: CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.ab_test_plans
    ADD CONSTRAINT ab_test_plans_name_created_at_key UNIQUE (name, created_at);


--
-- Name: ab_test_plans ab_test_plans_pkey; Type: CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.ab_test_plans
    ADD CONSTRAINT ab_test_plans_pkey PRIMARY KEY (id);


--
-- Name: ab_test_rollbacks ab_test_rollbacks_pkey; Type: CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.ab_test_rollbacks
    ADD CONSTRAINT ab_test_rollbacks_pkey PRIMARY KEY (id);


--
-- Name: ab_test_rollout_plans ab_test_rollout_plans_pkey; Type: CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.ab_test_rollout_plans
    ADD CONSTRAINT ab_test_rollout_plans_pkey PRIMARY KEY (id);


--
-- Name: ab_test_traffic ab_test_traffic_pkey; Type: CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.ab_test_traffic
    ADD CONSTRAINT ab_test_traffic_pkey PRIMARY KEY (test_name, variant);


--
-- Name: arbiter_decisions arbiter_decisions_pkey; Type: CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.arbiter_decisions
    ADD CONSTRAINT arbiter_decisions_pkey PRIMARY KEY (id);


--
-- Name: circuit_breaker_state circuit_breaker_state_pkey; Type: CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.circuit_breaker_state
    ADD CONSTRAINT circuit_breaker_state_pkey PRIMARY KEY (model);


--
-- Name: confidence_calibration confidence_calibration_pkey; Type: CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.confidence_calibration
    ADD CONSTRAINT confidence_calibration_pkey PRIMARY KEY (id);


--
-- Name: consensus_cache consensus_cache_cache_key_key; Type: CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.consensus_cache
    ADD CONSTRAINT consensus_cache_cache_key_key UNIQUE (cache_key);


--
-- Name: consensus_cache consensus_cache_pkey; Type: CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.consensus_cache
    ADD CONSTRAINT consensus_cache_pkey PRIMARY KEY (id);


--
-- Name: consensus_cache_stats consensus_cache_stats_date_key; Type: CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.consensus_cache_stats
    ADD CONSTRAINT consensus_cache_stats_date_key UNIQUE (date);


--
-- Name: consensus_cache_stats consensus_cache_stats_pkey; Type: CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.consensus_cache_stats
    ADD CONSTRAINT consensus_cache_stats_pkey PRIMARY KEY (id);


--
-- Name: executions executions_pkey; Type: CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.executions
    ADD CONSTRAINT executions_pkey PRIMARY KEY (id);


--
-- Name: executions executions_workflow_id_key; Type: CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.executions
    ADD CONSTRAINT executions_workflow_id_key UNIQUE (workflow_id);


--
-- Name: experiments experiments_pkey; Type: CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.experiments
    ADD CONSTRAINT experiments_pkey PRIMARY KEY (id);


--
-- Name: feedback feedback_pkey; Type: CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.feedback
    ADD CONSTRAINT feedback_pkey PRIMARY KEY (id);


--
-- Name: learnings learnings_pkey; Type: CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.learnings
    ADD CONSTRAINT learnings_pkey PRIMARY KEY (id);


--
-- Name: model_rotation_schedule model_rotation_schedule_pkey; Type: CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.model_rotation_schedule
    ADD CONSTRAINT model_rotation_schedule_pkey PRIMARY KEY (id);


--
-- Name: phases phases_pkey; Type: CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.phases
    ADD CONSTRAINT phases_pkey PRIMARY KEY (id);


--
-- Name: prediction_accuracy prediction_accuracy_pkey; Type: CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.prediction_accuracy
    ADD CONSTRAINT prediction_accuracy_pkey PRIMARY KEY (id);


--
-- Name: replays replays_pkey; Type: CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.replays
    ADD CONSTRAINT replays_pkey PRIMARY KEY (id);


--
-- Name: response_cache response_cache_pkey; Type: CONSTRAINT; Schema: workflow; Owner: postgres
--

ALTER TABLE ONLY workflow.response_cache
    ADD CONSTRAINT response_cache_pkey PRIMARY KEY (request_hash);


--
-- Name: training_system_build training_system_build_pkey; Type: CONSTRAINT; Schema: workflow; Owner: claude
--

ALTER TABLE ONLY workflow.training_system_build
    ADD CONSTRAINT training_system_build_pkey PRIMARY KEY (id);


--
-- Name: worker_results worker_results_pkey; Type: CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.worker_results
    ADD CONSTRAINT worker_results_pkey PRIMARY KEY (id);


--
-- Name: arbiter_decisions arbiter_decisions_pkey; Type: CONSTRAINT; Schema: workflows; Owner: sfloess
--

ALTER TABLE ONLY workflows.arbiter_decisions
    ADD CONSTRAINT arbiter_decisions_pkey PRIMARY KEY (decision_id);


--
-- Name: execution_embeddings execution_embeddings_pkey; Type: CONSTRAINT; Schema: workflows; Owner: sfloess
--

ALTER TABLE ONLY workflows.execution_embeddings
    ADD CONSTRAINT execution_embeddings_pkey PRIMARY KEY (execution_id);


--
-- Name: execution_phases execution_phases_pkey; Type: CONSTRAINT; Schema: workflows; Owner: sfloess
--

ALTER TABLE ONLY workflows.execution_phases
    ADD CONSTRAINT execution_phases_pkey PRIMARY KEY (phase_id);


--
-- Name: executions executions_pkey; Type: CONSTRAINT; Schema: workflows; Owner: sfloess
--

ALTER TABLE ONLY workflows.executions
    ADD CONSTRAINT executions_pkey PRIMARY KEY (execution_id);


--
-- Name: feedback feedback_pkey; Type: CONSTRAINT; Schema: workflows; Owner: sfloess
--

ALTER TABLE ONLY workflows.feedback
    ADD CONSTRAINT feedback_pkey PRIMARY KEY (feedback_id);


--
-- Name: learnings learnings_pkey; Type: CONSTRAINT; Schema: workflows; Owner: sfloess
--

ALTER TABLE ONLY workflows.learnings
    ADD CONSTRAINT learnings_pkey PRIMARY KEY (learning_id);


--
-- Name: model_combinations model_combinations_pkey; Type: CONSTRAINT; Schema: workflows; Owner: sfloess
--

ALTER TABLE ONLY workflows.model_combinations
    ADD CONSTRAINT model_combinations_pkey PRIMARY KEY (combination_id);


--
-- Name: model_combinations model_combinations_workflow_name_worker_models_arbiter_mode_key; Type: CONSTRAINT; Schema: workflows; Owner: sfloess
--

ALTER TABLE ONLY workflows.model_combinations
    ADD CONSTRAINT model_combinations_workflow_name_worker_models_arbiter_mode_key UNIQUE (workflow_name, worker_models, arbiter_model);


--
-- Name: worker_results worker_results_pkey; Type: CONSTRAINT; Schema: workflows; Owner: sfloess
--

ALTER TABLE ONLY workflows.worker_results
    ADD CONSTRAINT worker_results_pkey PRIMARY KEY (result_id);


--
-- Name: idx_background_tasks_started; Type: INDEX; Schema: admin; Owner: claude
--

CREATE INDEX idx_background_tasks_started ON admin.background_tasks USING btree (started_at DESC);


--
-- Name: idx_background_tasks_status; Type: INDEX; Schema: admin; Owner: claude
--

CREATE INDEX idx_background_tasks_status ON admin.background_tasks USING btree (status);


--
-- Name: idx_config_updated_at; Type: INDEX; Schema: admin; Owner: sfloess
--

CREATE INDEX idx_config_updated_at ON admin.config USING btree (updated_at DESC);


--
-- Name: idx_api_keys_active; Type: INDEX; Schema: auth; Owner: sfloess
--

CREATE INDEX idx_api_keys_active ON auth.api_keys USING btree (is_active);


--
-- Name: idx_api_keys_prefix; Type: INDEX; Schema: auth; Owner: sfloess
--

CREATE INDEX idx_api_keys_prefix ON auth.api_keys USING btree (key_prefix) WHERE (is_active = true);


--
-- Name: idx_api_calls_created; Type: INDEX; Schema: auto_storage; Owner: claude
--

CREATE INDEX idx_api_calls_created ON auto_storage.api_calls USING btree (created_at);


--
-- Name: idx_api_calls_model; Type: INDEX; Schema: auto_storage; Owner: claude
--

CREATE INDEX idx_api_calls_model ON auto_storage.api_calls USING btree (model);


--
-- Name: idx_api_calls_timestamp; Type: INDEX; Schema: auto_storage; Owner: claude
--

CREATE INDEX idx_api_calls_timestamp ON auto_storage.api_calls USING btree (request_timestamp);


--
-- Name: idx_api_calls_worker; Type: INDEX; Schema: auto_storage; Owner: claude
--

CREATE INDEX idx_api_calls_worker ON auto_storage.api_calls USING btree (worker_id);


--
-- Name: idx_auto_storage_api_calls_created; Type: INDEX; Schema: auto_storage; Owner: claude
--

CREATE INDEX idx_auto_storage_api_calls_created ON auto_storage.api_calls USING btree (created_at);


--
-- Name: idx_auto_storage_api_calls_worker; Type: INDEX; Schema: auto_storage; Owner: claude
--

CREATE INDEX idx_auto_storage_api_calls_worker ON auto_storage.api_calls USING btree (worker_id);


--
-- Name: idx_api_keys_active; Type: INDEX; Schema: config; Owner: claude
--

CREATE INDEX idx_api_keys_active ON config.api_keys USING btree (is_active);


--
-- Name: idx_api_keys_service; Type: INDEX; Schema: config; Owner: claude
--

CREATE INDEX idx_api_keys_service ON config.api_keys USING btree (service);


--
-- Name: idx_api_keys_tags; Type: INDEX; Schema: config; Owner: claude
--

CREATE INDEX idx_api_keys_tags ON config.api_keys USING gin (tags);


--
-- Name: idx_key_usage_log_key_id; Type: INDEX; Schema: config; Owner: claude
--

CREATE INDEX idx_key_usage_log_key_id ON config.key_usage_log USING btree (key_id);


--
-- Name: idx_key_usage_log_timestamp; Type: INDEX; Schema: config; Owner: claude
--

CREATE INDEX idx_key_usage_log_timestamp ON config.key_usage_log USING btree ("timestamp" DESC);


--
-- Name: idx_costs_model; Type: INDEX; Schema: costs; Owner: sfloess
--

CREATE INDEX idx_costs_model ON costs.entries USING btree (model);


--
-- Name: idx_similar_hash1; Type: INDEX; Schema: dedup; Owner: claude
--

CREATE INDEX idx_similar_hash1 ON dedup.similar_pairs USING btree (hash1, similarity_score DESC);


--
-- Name: idx_chunks_document; Type: INDEX; Schema: documents; Owner: sfloess
--

CREATE INDEX idx_chunks_document ON documents.chunks USING btree (document_id);


--
-- Name: idx_chunks_embedding; Type: INDEX; Schema: documents; Owner: sfloess
--

CREATE INDEX idx_chunks_embedding ON documents.chunks USING hnsw (embedding public.vector_cosine_ops) WITH (m='16', ef_construction='64');


--
-- Name: idx_chunks_hash; Type: INDEX; Schema: documents; Owner: sfloess
--

CREATE INDEX idx_chunks_hash ON documents.chunks USING btree (content_hash);


--
-- Name: idx_documents_created; Type: INDEX; Schema: documents; Owner: sfloess
--

CREATE INDEX idx_documents_created ON documents.documents USING btree (created_at DESC);


--
-- Name: idx_documents_hash; Type: INDEX; Schema: documents; Owner: sfloess
--

CREATE INDEX idx_documents_hash ON documents.documents USING btree (file_hash);


--
-- Name: idx_documents_status; Type: INDEX; Schema: documents; Owner: sfloess
--

CREATE INDEX idx_documents_status ON documents.documents USING btree (status);


--
-- Name: idx_documents_tags; Type: INDEX; Schema: documents; Owner: sfloess
--

CREATE INDEX idx_documents_tags ON documents.documents USING gin (tags);


--
-- Name: idx_documents_type; Type: INDEX; Schema: documents; Owner: sfloess
--

CREATE INDEX idx_documents_type ON documents.documents USING btree (file_type);


--
-- Name: idx_processing_log_created; Type: INDEX; Schema: documents; Owner: sfloess
--

CREATE INDEX idx_processing_log_created ON documents.processing_log USING btree (created_at DESC);


--
-- Name: idx_processing_log_document; Type: INDEX; Schema: documents; Owner: sfloess
--

CREATE INDEX idx_processing_log_document ON documents.processing_log USING btree (document_id);


--
-- Name: idx_processing_log_stage; Type: INDEX; Schema: documents; Owner: sfloess
--

CREATE INDEX idx_processing_log_stage ON documents.processing_log USING btree (stage);


--
-- Name: idx_benchmarks_category; Type: INDEX; Schema: evaluation; Owner: sfloess
--

CREATE INDEX idx_benchmarks_category ON evaluation.benchmarks USING btree (category);


--
-- Name: idx_benchmarks_difficulty; Type: INDEX; Schema: evaluation; Owner: sfloess
--

CREATE INDEX idx_benchmarks_difficulty ON evaluation.benchmarks USING btree (difficulty);


--
-- Name: idx_benchmarks_task_type; Type: INDEX; Schema: evaluation; Owner: sfloess
--

CREATE INDEX idx_benchmarks_task_type ON evaluation.benchmarks USING btree (task_type);


--
-- Name: idx_model_performance_unique; Type: INDEX; Schema: evaluation; Owner: sfloess
--

CREATE UNIQUE INDEX idx_model_performance_unique ON evaluation.model_performance USING btree (model);


--
-- Name: idx_results_benchmark_id; Type: INDEX; Schema: evaluation; Owner: sfloess
--

CREATE INDEX idx_results_benchmark_id ON evaluation.results USING btree (benchmark_id);


--
-- Name: idx_results_benchmark_model; Type: INDEX; Schema: evaluation; Owner: sfloess
--

CREATE INDEX idx_results_benchmark_model ON evaluation.results USING btree (benchmark_id, model);


--
-- Name: idx_results_created_at; Type: INDEX; Schema: evaluation; Owner: sfloess
--

CREATE INDEX idx_results_created_at ON evaluation.results USING btree (created_at);


--
-- Name: idx_results_model; Type: INDEX; Schema: evaluation; Owner: sfloess
--

CREATE INDEX idx_results_model ON evaluation.results USING btree (model);


--
-- Name: idx_results_overall_score; Type: INDEX; Schema: evaluation; Owner: sfloess
--

CREATE INDEX idx_results_overall_score ON evaluation.results USING btree (overall_score DESC);


--
-- Name: idx_results_worker_id; Type: INDEX; Schema: evaluation; Owner: sfloess
--

CREATE INDEX idx_results_worker_id ON evaluation.results USING btree (worker_id);


--
-- Name: idx_task_model_performance_unique; Type: INDEX; Schema: evaluation; Owner: sfloess
--

CREATE UNIQUE INDEX idx_task_model_performance_unique ON evaluation.task_model_performance USING btree (task_type, model);


--
-- Name: idx_registry_created_at; Type: INDEX; Schema: experiments; Owner: sfloess
--

CREATE INDEX idx_registry_created_at ON experiments.registry USING btree (created_at DESC);


--
-- Name: idx_registry_name; Type: INDEX; Schema: experiments; Owner: sfloess
--

CREATE INDEX idx_registry_name ON experiments.registry USING btree (name);


--
-- Name: idx_registry_status; Type: INDEX; Schema: experiments; Owner: sfloess
--

CREATE INDEX idx_registry_status ON experiments.registry USING btree (status);


--
-- Name: idx_runs_experiment_date; Type: INDEX; Schema: experiments; Owner: sfloess
--

CREATE INDEX idx_runs_experiment_date ON experiments.runs USING btree (experiment_id, run_date DESC);


--
-- Name: idx_runs_experiment_id; Type: INDEX; Schema: experiments; Owner: sfloess
--

CREATE INDEX idx_runs_experiment_id ON experiments.runs USING btree (experiment_id);


--
-- Name: idx_runs_run_date; Type: INDEX; Schema: experiments; Owner: sfloess
--

CREATE INDEX idx_runs_run_date ON experiments.runs USING btree (run_date DESC);


--
-- Name: idx_runs_verdict; Type: INDEX; Schema: experiments; Owner: sfloess
--

CREATE INDEX idx_runs_verdict ON experiments.runs USING btree (verdict);


--
-- Name: idx_workers_failures; Type: INDEX; Schema: fleet; Owner: claude
--

CREATE INDEX idx_workers_failures ON fleet.workers USING btree (failure_count) WHERE ((status)::text = 'active'::text);


--
-- Name: idx_workers_heartbeat; Type: INDEX; Schema: fleet; Owner: claude
--

CREATE INDEX idx_workers_heartbeat ON fleet.workers USING btree (last_heartbeat) WHERE ((status)::text = ANY ((ARRAY['active'::character varying, 'degraded'::character varying])::text[]));


--
-- Name: idx_workers_last_seen; Type: INDEX; Schema: fleet; Owner: claude
--

CREATE INDEX idx_workers_last_seen ON fleet.workers USING btree (last_seen) WHERE ((status)::text = 'active'::text);


--
-- Name: idx_ga_populations_usecase_gen; Type: INDEX; Schema: ga; Owner: claude
--

CREATE INDEX idx_ga_populations_usecase_gen ON ga.populations USING btree (use_case, generation);


--
-- Name: idx_machines_always_on; Type: INDEX; Schema: inventory; Owner: claude
--

CREATE INDEX idx_machines_always_on ON inventory.machines USING btree (always_on);


--
-- Name: idx_machines_hostname; Type: INDEX; Schema: inventory; Owner: claude
--

CREATE INDEX idx_machines_hostname ON inventory.machines USING btree (hostname);


--
-- Name: idx_machines_type; Type: INDEX; Schema: inventory; Owner: claude
--

CREATE INDEX idx_machines_type ON inventory.machines USING btree (device_type);


--
-- Name: code_embeddings_embedding_idx; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX code_embeddings_embedding_idx ON knowledge.code_embeddings USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: code_embeddings_type_idx; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX code_embeddings_type_idx ON knowledge.code_embeddings USING btree (file_type);


--
-- Name: entries_embedding_idx; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX entries_embedding_idx ON knowledge.entries USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_chunks_content_hash; Type: INDEX; Schema: knowledge; Owner: sfloess
--

CREATE INDEX idx_chunks_content_hash ON knowledge.chunks USING btree (content_hash);


--
-- Name: idx_chunks_created_at; Type: INDEX; Schema: knowledge; Owner: sfloess
--

CREATE INDEX idx_chunks_created_at ON knowledge.chunks USING btree (created_at);


--
-- Name: idx_chunks_document_id; Type: INDEX; Schema: knowledge; Owner: sfloess
--

CREATE INDEX idx_chunks_document_id ON knowledge.chunks USING btree (document_id);


--
-- Name: idx_code_embedding; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX idx_code_embedding ON knowledge.code_embeddings USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_code_file_path; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX idx_code_file_path ON knowledge.code_embeddings USING btree (file_path);


--
-- Name: idx_concept_embedding; Type: INDEX; Schema: knowledge; Owner: sfloess
--

CREATE INDEX idx_concept_embedding ON knowledge.concepts USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_concept_type; Type: INDEX; Schema: knowledge; Owner: sfloess
--

CREATE INDEX idx_concept_type ON knowledge.concepts USING btree (type);


--
-- Name: idx_discovered_domain; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX idx_discovered_domain ON knowledge.discovered_sources USING btree (domain);


--
-- Name: idx_discovered_score; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX idx_discovered_score ON knowledge.discovered_sources USING btree (quality_score DESC);


--
-- Name: idx_discovered_tier; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX idx_discovered_tier ON knowledge.discovered_sources USING btree (tier);


--
-- Name: idx_discoveries_status; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX idx_discoveries_status ON knowledge.discoveries USING btree (status, confidence DESC);


--
-- Name: idx_discoveries_worker; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX idx_discoveries_worker ON knowledge.discoveries USING btree (worker_id, created_at DESC);


--
-- Name: idx_documents_category; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX idx_documents_category ON knowledge.documents USING btree (category);


--
-- Name: idx_documents_content_hash; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE UNIQUE INDEX idx_documents_content_hash ON knowledge.documents USING btree (content_hash);


--
-- Name: idx_documents_embedding; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX idx_documents_embedding ON knowledge.documents USING ivfflat (embedding public.vector_cosine_ops) WITH (lists='100');


--
-- Name: idx_documents_fetched_at; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX idx_documents_fetched_at ON knowledge.documents USING btree (fetched_at);


--
-- Name: idx_documents_url; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX idx_documents_url ON knowledge.documents USING btree (url);


--
-- Name: idx_embeddings_chunk_id; Type: INDEX; Schema: knowledge; Owner: sfloess
--

CREATE INDEX idx_embeddings_chunk_id ON knowledge.embeddings USING btree (chunk_id);


--
-- Name: idx_embeddings_created_at; Type: INDEX; Schema: knowledge; Owner: sfloess
--

CREATE INDEX idx_embeddings_created_at ON knowledge.embeddings USING btree (created_at);


--
-- Name: idx_embeddings_provider; Type: INDEX; Schema: knowledge; Owner: sfloess
--

CREATE INDEX idx_embeddings_provider ON knowledge.embeddings USING btree (provider);


--
-- Name: idx_ingestion_status; Type: INDEX; Schema: knowledge; Owner: postgres
--

CREATE INDEX idx_ingestion_status ON knowledge.ingestion_queue USING btree (status, queued_at);


--
-- Name: idx_pubmed_embedding; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX idx_pubmed_embedding ON knowledge.pubmed_articles USING ivfflat (embedding public.vector_cosine_ops) WITH (lists='100');


--
-- Name: idx_rel_source; Type: INDEX; Schema: knowledge; Owner: sfloess
--

CREATE INDEX idx_rel_source ON knowledge.relationships USING btree (source_id);


--
-- Name: idx_rel_target; Type: INDEX; Schema: knowledge; Owner: sfloess
--

CREATE INDEX idx_rel_target ON knowledge.relationships USING btree (target_id);


--
-- Name: idx_research_findings_embedding; Type: INDEX; Schema: knowledge; Owner: sfloess
--

CREATE INDEX idx_research_findings_embedding ON knowledge.research_findings USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_research_findings_workflow; Type: INDEX; Schema: knowledge; Owner: sfloess
--

CREATE INDEX idx_research_findings_workflow ON knowledge.research_findings USING btree (workflow_id);


--
-- Name: idx_scraped_category; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX idx_scraped_category ON knowledge.scraped_data USING btree (category);


--
-- Name: idx_scraped_content_category; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX idx_scraped_content_category ON knowledge.scraped_content USING btree (category);


--
-- Name: idx_scraped_content_embedding; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX idx_scraped_content_embedding ON knowledge.scraped_content USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_scraped_embedding; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX idx_scraped_embedding ON knowledge.scraped_data USING ivfflat (embedding public.vector_cosine_ops) WITH (lists='100');


--
-- Name: idx_url_status_category; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX idx_url_status_category ON knowledge.url_status USING btree (category);


--
-- Name: idx_url_status_http; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX idx_url_status_http ON knowledge.url_status USING btree (http_status);


--
-- Name: idx_url_status_stored; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX idx_url_status_stored ON knowledge.url_status USING btree (stored);


--
-- Name: idx_web_articles_category; Type: INDEX; Schema: knowledge; Owner: sfloess
--

CREATE INDEX idx_web_articles_category ON knowledge.web_articles USING btree (category);


--
-- Name: idx_web_articles_embedding; Type: INDEX; Schema: knowledge; Owner: sfloess
--

CREATE INDEX idx_web_articles_embedding ON knowledge.web_articles USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_web_articles_source; Type: INDEX; Schema: knowledge; Owner: sfloess
--

CREATE INDEX idx_web_articles_source ON knowledge.web_articles USING btree (source);


--
-- Name: web_scrape_embedding_idx; Type: INDEX; Schema: knowledge; Owner: claude
--

CREATE INDEX web_scrape_embedding_idx ON knowledge.web_scrape USING ivfflat (embedding public.vector_cosine_ops) WITH (lists='100');


--
-- Name: comprehensive_research_embedding_idx; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX comprehensive_research_embedding_idx ON learning.comprehensive_research USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: conv_learnings_session_idx; Type: INDEX; Schema: learning; Owner: sfloess
--

CREATE INDEX conv_learnings_session_idx ON learning.conversation_learnings USING btree (session_id);


--
-- Name: conv_learnings_type_idx; Type: INDEX; Schema: learning; Owner: sfloess
--

CREATE INDEX conv_learnings_type_idx ON learning.conversation_learnings USING btree (learning_type);


--
-- Name: idx_api_models_provider; Type: INDEX; Schema: learning; Owner: sfloess
--

CREATE INDEX idx_api_models_provider ON learning.api_models USING btree (provider);


--
-- Name: idx_capabilities_code; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_capabilities_code ON learning.model_capabilities USING btree (code_generation DESC);


--
-- Name: idx_capabilities_provider; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_capabilities_provider ON learning.model_capabilities USING btree (provider);


--
-- Name: idx_category; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_category ON learning.model_censorship USING btree (category);


--
-- Name: idx_censorship_level; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_censorship_level ON learning.model_censorship USING btree (censorship_level DESC);


--
-- Name: idx_chunk_text_gin_trgm; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunk_text_gin_trgm ON learning.research_chunks USING gin (chunk_text public.gin_trgm_ops);


--
-- Name: idx_chunk_type; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunk_type ON learning.research_chunks USING btree (chunk_type);


--
-- Name: idx_chunks_anonymization; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_anonymization ON learning.session_chunks USING btree (anonymization_applied);


--
-- Name: idx_chunks_business_process; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_business_process ON learning.session_chunks USING btree (business_process_id);


--
-- Name: idx_chunks_char_count; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_char_count ON learning.session_chunks USING btree (char_count);


--
-- Name: idx_chunks_client_ip; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_client_ip ON learning.session_chunks USING btree (client_ip_address);


--
-- Name: idx_chunks_cost_usd; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_cost_usd ON learning.session_chunks USING btree (cost_usd);


--
-- Name: idx_chunks_data_classification; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_data_classification ON learning.session_chunks USING btree (data_classification);


--
-- Name: idx_chunks_data_retention; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_data_retention ON learning.session_chunks USING btree (data_retention_days);


--
-- Name: idx_chunks_deletion_status; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_deletion_status ON learning.session_chunks USING btree (data_deletion_status);


--
-- Name: idx_chunks_document_type; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_document_type ON learning.session_chunks USING btree (document_type);


--
-- Name: idx_chunks_experiment; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_experiment ON learning.session_chunks USING btree (experiment_id);


--
-- Name: idx_chunks_gdpr; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_gdpr ON learning.session_chunks USING btree (gdpr_compliant);


--
-- Name: idx_chunks_hipaa; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_hipaa ON learning.session_chunks USING btree (hipaa_compliant);


--
-- Name: idx_chunks_incident_status; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_incident_status ON learning.session_chunks USING btree (incident_resolution_status);


--
-- Name: idx_chunks_input_hash; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_input_hash ON learning.session_chunks USING btree (input_data_hash);


--
-- Name: idx_chunks_keywords; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_keywords ON learning.session_chunks USING gin (keywords);


--
-- Name: idx_chunks_language; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_language ON learning.session_chunks USING btree (language);


--
-- Name: idx_chunks_log_level; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_log_level ON learning.session_chunks USING btree (log_level);


--
-- Name: idx_chunks_message_role; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_message_role ON learning.session_chunks USING btree (message_role);


--
-- Name: idx_chunks_model_drift; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_model_drift ON learning.session_chunks USING btree (model_drift_score);


--
-- Name: idx_chunks_output_hash; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_output_hash ON learning.session_chunks USING btree (output_data_hash);


--
-- Name: idx_chunks_parent; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_parent ON learning.session_chunks USING btree (parent_chunk_id);


--
-- Name: idx_chunks_relevance_score; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_relevance_score ON learning.session_chunks USING btree (relevance_score);


--
-- Name: idx_chunks_request_id; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_request_id ON learning.session_chunks USING btree (request_id);


--
-- Name: idx_chunks_request_start; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_request_start ON learning.session_chunks USING btree (request_start_timestamp);


--
-- Name: idx_chunks_retrieval_rank; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_retrieval_rank ON learning.session_chunks USING btree (retrieval_rank);


--
-- Name: idx_chunks_retrieval_strategy; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_retrieval_strategy ON learning.session_chunks USING btree (retrieval_strategy_used);


--
-- Name: idx_chunks_retrieval_ts; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_retrieval_ts ON learning.session_chunks USING btree (retrieval_timestamp);


--
-- Name: idx_chunks_similarity_score; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_similarity_score ON learning.session_chunks USING btree (similarity_score);


--
-- Name: idx_chunks_tenant_id; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_tenant_id ON learning.session_chunks USING btree (tenant_id);


--
-- Name: idx_chunks_thread; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_thread ON learning.session_chunks USING btree (conversation_thread_id);


--
-- Name: idx_chunks_trace_id; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_trace_id ON learning.session_chunks USING btree (trace_id);


--
-- Name: idx_chunks_user_id; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_user_id ON learning.session_chunks USING btree (user_id);


--
-- Name: idx_chunks_vector_store; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_chunks_vector_store ON learning.session_chunks USING btree (vector_store_id);


--
-- Name: idx_claude_memory_embedding; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_claude_memory_embedding ON learning.claude_memory USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_codebase_confidence; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_codebase_confidence ON learning.codebase_analysis USING btree (confidence);


--
-- Name: idx_codebase_created_at; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_codebase_created_at ON learning.codebase_analysis USING btree (created_at);


--
-- Name: idx_codebase_embedding; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_codebase_embedding ON learning.codebase_analysis USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_codebase_extension; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_codebase_extension ON learning.codebase_analysis USING btree (extension);


--
-- Name: idx_codebase_file_path; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_codebase_file_path ON learning.codebase_analysis USING btree (file_path);


--
-- Name: idx_codebase_git_author; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_codebase_git_author ON learning.codebase_analysis USING btree (git_introduced_by);


--
-- Name: idx_codebase_model; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_codebase_model ON learning.codebase_analysis USING btree (model);


--
-- Name: idx_codebase_quality; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_codebase_quality ON learning.codebase_analysis USING btree (quality_score);


--
-- Name: idx_components_gin; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_components_gin ON learning.research_chunks USING gin (components_used);


--
-- Name: idx_confidence_model; Type: INDEX; Schema: learning; Owner: sfloess
--

CREATE INDEX idx_confidence_model ON learning.confidence_observations USING btree (model);


--
-- Name: idx_confidence_score; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_confidence_score ON learning.research_chunks USING btree (confidence_score) WHERE (confidence_score > (0.75)::double precision);


--
-- Name: idx_confidence_task_type; Type: INDEX; Schema: learning; Owner: sfloess
--

CREATE INDEX idx_confidence_task_type ON learning.confidence_observations USING btree (task_type);


--
-- Name: idx_consciousness_research_embedding; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_consciousness_research_embedding ON learning.consciousness_research USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_cost_usd; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_cost_usd ON learning.research_chunks USING btree (cost_usd);


--
-- Name: idx_discovery_method; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_discovery_method ON learning.research_chunks USING btree (discovery_method);


--
-- Name: idx_diversity_violations_model; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_diversity_violations_model ON learning.diversity_violations USING btree (model);


--
-- Name: idx_diversity_violations_timestamp; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_diversity_violations_timestamp ON learning.diversity_violations USING btree ("timestamp" DESC);


--
-- Name: idx_diversity_violations_type; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_diversity_violations_type ON learning.diversity_violations USING btree (violation_type);


--
-- Name: idx_domain_tags_gin; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_domain_tags_gin ON learning.research_chunks USING gin (domain_tags);


--
-- Name: idx_duration_ms; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_duration_ms ON learning.research_chunks USING btree (duration_ms);


--
-- Name: idx_entity_mentions_gin; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_entity_mentions_gin ON learning.research_chunks USING gin (entity_mentions);


--
-- Name: idx_exp_embedding_384; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_exp_embedding_384 ON learning.experiences USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_exp_problem_hash; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_exp_problem_hash ON learning.experiences USING btree (problem_hash);


--
-- Name: idx_exp_problem_type; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_exp_problem_type ON learning.experiences USING btree (problem_type);


--
-- Name: idx_exp_success; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_exp_success ON learning.experiences USING btree (success) WHERE (success = true);


--
-- Name: idx_exp_timestamp; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_exp_timestamp ON learning.experiences USING btree ("timestamp" DESC);


--
-- Name: idx_experiences_experiment_embedding; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_experiences_experiment_embedding ON learning.experiences_experiment USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_fine_tuning_queue_status; Type: INDEX; Schema: learning; Owner: postgres
--

CREATE INDEX idx_fine_tuning_queue_status ON learning.fine_tuning_queue USING btree (status, "timestamp");


--
-- Name: idx_free_models_last_seen; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_free_models_last_seen ON learning.free_models USING btree (last_seen);


--
-- Name: idx_free_models_provider; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_free_models_provider ON learning.free_models USING btree (provider);


--
-- Name: idx_ga_configs_type_fitness; Type: INDEX; Schema: learning; Owner: postgres
--

CREATE INDEX idx_ga_configs_type_fitness ON learning.ga_configs USING btree (config_type, fitness_score DESC);


--
-- Name: idx_icl_embedding; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_icl_embedding ON learning.icl_examples USING ivfflat (embedding public.vector_cosine_ops) WITH (lists='100');


--
-- Name: idx_icl_quality; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_icl_quality ON learning.icl_examples USING btree (quality_score);


--
-- Name: idx_icl_task_type; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_icl_task_type ON learning.icl_examples USING btree (task_type);


--
-- Name: idx_knowledge_embeddings_vector; Type: INDEX; Schema: learning; Owner: postgres
--

CREATE INDEX idx_knowledge_embeddings_vector ON learning.knowledge_embeddings USING ivfflat (embedding public.vector_cosine_ops) WITH (lists='100');


--
-- Name: idx_memory_content_fts; Type: INDEX; Schema: learning; Owner: postgres
--

CREATE INDEX idx_memory_content_fts ON learning.memory USING gin (to_tsvector('english'::regconfig, content));


--
-- Name: idx_memory_created; Type: INDEX; Schema: learning; Owner: postgres
--

CREATE INDEX idx_memory_created ON learning.memory USING btree (created_at DESC);


--
-- Name: idx_memory_embedding; Type: INDEX; Schema: learning; Owner: postgres
--

CREATE INDEX idx_memory_embedding ON learning.memory USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_memory_type; Type: INDEX; Schema: learning; Owner: postgres
--

CREATE INDEX idx_memory_type ON learning.memory USING btree (memory_type);


--
-- Name: idx_metadata_chunk_type; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_metadata_chunk_type ON learning.metadata_schema_test USING btree (chunk_type);


--
-- Name: idx_metadata_components_gin; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_metadata_components_gin ON learning.metadata_schema_test USING gin (components_used);


--
-- Name: idx_metadata_content_hash; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_metadata_content_hash ON learning.metadata_schema_test USING btree (content_hash);


--
-- Name: idx_metadata_dedup; Type: INDEX; Schema: learning; Owner: claude
--

CREATE UNIQUE INDEX idx_metadata_dedup ON learning.metadata_schema_test USING btree (content_hash);


--
-- Name: idx_metadata_domains_gin; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_metadata_domains_gin ON learning.metadata_schema_test USING gin (domain_tags);


--
-- Name: idx_metadata_embedding; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_metadata_embedding ON learning.metadata_schema_test USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_metadata_entities_gin; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_metadata_entities_gin ON learning.metadata_schema_test USING gin (entity_mentions);


--
-- Name: idx_metadata_models_gin; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_metadata_models_gin ON learning.metadata_schema_test USING gin (models_involved);


--
-- Name: idx_metadata_outcome; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_metadata_outcome ON learning.metadata_schema_test USING btree (outcome_status);


--
-- Name: idx_metadata_priority; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_metadata_priority ON learning.metadata_schema_test USING btree (priority_level);


--
-- Name: idx_metadata_quality; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_metadata_quality ON learning.metadata_schema_test USING btree (quality_score) WHERE (quality_score > (0.75)::double precision);


--
-- Name: idx_metadata_timestamp; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_metadata_timestamp ON learning.metadata_schema_test USING btree ("timestamp" DESC);


--
-- Name: idx_metadata_topics_gin; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_metadata_topics_gin ON learning.metadata_schema_test USING gin (semantic_topics);


--
-- Name: idx_metadata_verification; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_metadata_verification ON learning.metadata_schema_test USING btree (verification_status);


--
-- Name: idx_models_gin; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_models_gin ON learning.research_chunks USING gin (models_involved);


--
-- Name: idx_parent_chunk; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_parent_chunk ON learning.research_chunks USING btree (parent_chunk_id);


--
-- Name: idx_priority; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_priority ON learning.research_chunks USING btree (priority);


--
-- Name: idx_proc_condition_hash; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_proc_condition_hash ON learning.procedural_rules USING btree (condition_hash);


--
-- Name: idx_provider; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_provider ON learning.model_censorship USING btree (provider);


--
-- Name: idx_qfp_error_type; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_qfp_error_type ON learning.queue_failure_patterns USING btree (error_type);


--
-- Name: idx_qfp_fingerprint; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_qfp_fingerprint ON learning.queue_failure_patterns USING btree (error_fingerprint);


--
-- Name: idx_qfp_queue_type; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_qfp_queue_type ON learning.queue_failure_patterns USING btree (queue_type);


--
-- Name: idx_qhm_health; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_qhm_health ON learning.queue_health_metrics USING btree (health_score, alert_level);


--
-- Name: idx_qhm_queue_type; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_qhm_queue_type ON learning.queue_health_metrics USING btree (queue_type, "timestamp" DESC);


--
-- Name: idx_qhm_timestamp; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_qhm_timestamp ON learning.queue_health_metrics USING btree ("timestamp" DESC);


--
-- Name: idx_qp_accuracy; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_qp_accuracy ON learning.queue_predictions USING btree (predicted_success_prob, actual_outcome);


--
-- Name: idx_qp_document; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_qp_document ON learning.queue_predictions USING btree (document_id);


--
-- Name: idx_qp_queue_item; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_qp_queue_item ON learning.queue_predictions USING btree (queue_type, queue_item_id);


--
-- Name: idx_reasoning_patterns_category; Type: INDEX; Schema: learning; Owner: sfloess
--

CREATE INDEX idx_reasoning_patterns_category ON learning.reasoning_patterns USING btree (problem_category);


--
-- Name: idx_reasoning_patterns_confidence; Type: INDEX; Schema: learning; Owner: sfloess
--

CREATE INDEX idx_reasoning_patterns_confidence ON learning.reasoning_patterns USING btree (pattern_confidence DESC);


--
-- Name: idx_request_history_ab_analysis; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_request_history_ab_analysis ON learning.request_history USING btree (ab_bucket, "timestamp" DESC) WHERE (ab_bucket IS NOT NULL);


--
-- Name: idx_request_history_ab_bucket; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_request_history_ab_bucket ON learning.request_history USING btree (ab_bucket);


--
-- Name: idx_request_history_model; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_request_history_model ON learning.request_history USING btree (model);


--
-- Name: idx_request_history_recent; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_request_history_recent ON learning.request_history USING btree ("timestamp" DESC, model);


--
-- Name: idx_request_history_timestamp; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_request_history_timestamp ON learning.request_history USING btree ("timestamp" DESC);


--
-- Name: idx_research_chunks_claim_assertions; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_research_chunks_claim_assertions ON learning.research_chunks USING gin (claim_assertions);


--
-- Name: idx_research_chunks_claim_assertions_gin; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_research_chunks_claim_assertions_gin ON learning.research_chunks USING gin (claim_assertions jsonb_path_ops);


--
-- Name: idx_research_chunks_information_density; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_research_chunks_information_density ON learning.research_chunks USING btree (information_density) WHERE (information_density IS NOT NULL);


--
-- Name: idx_research_chunks_retrieval_usefulness; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_research_chunks_retrieval_usefulness ON learning.research_chunks USING btree ((((((retrieval_feedback ->> 'times_useful'::text))::integer)::double precision / (NULLIF(((retrieval_feedback ->> 'times_retrieved'::text))::integer, 0))::double precision))) WHERE (((retrieval_feedback ->> 'times_retrieved'::text))::integer > 0);


--
-- Name: idx_research_chunks_source_document; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_research_chunks_source_document ON learning.research_chunks USING btree (source_document_id) WHERE (source_document_id IS NOT NULL);


--
-- Name: idx_research_chunks_structural_position; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_research_chunks_structural_position ON learning.research_chunks USING gin (structural_position);


--
-- Name: idx_research_chunks_structural_position_section; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_research_chunks_structural_position_section ON learning.research_chunks USING btree (((structural_position ->> 'section_type'::text)));


--
-- Name: idx_research_chunks_temporal_context; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_research_chunks_temporal_context ON learning.research_chunks USING gin (temporal_context);


--
-- Name: idx_research_chunks_temporal_pub_date; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_research_chunks_temporal_pub_date ON learning.research_chunks USING btree (((temporal_context ->> 'publication_date'::text)));


--
-- Name: idx_research_chunks_temporal_year; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_research_chunks_temporal_year ON learning.research_chunks USING btree ((((temporal_context ->> 'publication_year'::text))::integer)) WHERE ((temporal_context ->> 'publication_year'::text) IS NOT NULL);


--
-- Name: idx_retry_count; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_retry_count ON learning.research_chunks USING btree (retry_count) WHERE (retry_count > 0);


--
-- Name: idx_roadmap_priority; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_roadmap_priority ON learning.continual_learning_roadmap USING btree (priority);


--
-- Name: idx_roadmap_roi; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_roadmap_roi ON learning.continual_learning_roadmap USING btree (roi DESC);


--
-- Name: idx_scraping_queue_status; Type: INDEX; Schema: learning; Owner: postgres
--

CREATE INDEX idx_scraping_queue_status ON learning.scraping_queue USING btree (status, priority DESC);


--
-- Name: idx_security_policies_embedding; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_security_policies_embedding ON learning.security_policies USING ivfflat (embedding public.vector_cosine_ops) WITH (lists='100');


--
-- Name: idx_security_policies_owasp; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_security_policies_owasp ON learning.security_policies USING btree (owasp_category);


--
-- Name: idx_security_violations_embedding; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_security_violations_embedding ON learning.security_violations USING ivfflat (embedding public.vector_cosine_ops) WITH (lists='100');


--
-- Name: idx_security_violations_policy; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_security_violations_policy ON learning.security_violations USING btree (policy_id);


--
-- Name: idx_semantic_topics_gin; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_semantic_topics_gin ON learning.research_chunks USING gin (semantic_topics);


--
-- Name: idx_session_chunks_claim_assertions; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_session_chunks_claim_assertions ON learning.session_chunks USING gin (claim_assertions);


--
-- Name: idx_session_chunks_content_hash; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_session_chunks_content_hash ON learning.session_chunks USING btree (content_hash);


--
-- Name: idx_session_chunks_date; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_session_chunks_date ON learning.session_chunks USING btree (session_date);


--
-- Name: idx_session_chunks_hash; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_session_chunks_hash ON learning.session_chunks USING btree (content_hash);


--
-- Name: idx_session_chunks_information_density; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_session_chunks_information_density ON learning.session_chunks USING btree (information_density) WHERE (information_density IS NOT NULL);


--
-- Name: idx_session_chunks_metadata; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_session_chunks_metadata ON learning.session_chunks USING gin (metadata);


--
-- Name: idx_session_chunks_quality; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_session_chunks_quality ON learning.session_chunks USING btree (quality_score) WHERE (quality_score > (0.75)::double precision);


--
-- Name: idx_session_chunks_retrieval_usefulness; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_session_chunks_retrieval_usefulness ON learning.session_chunks USING btree ((((((retrieval_feedback ->> 'times_useful'::text))::integer)::double precision / (NULLIF(((retrieval_feedback ->> 'times_retrieved'::text))::integer, 0))::double precision))) WHERE (((retrieval_feedback ->> 'times_retrieved'::text))::integer > 0);


--
-- Name: idx_session_chunks_source_document; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_session_chunks_source_document ON learning.session_chunks USING btree (source_document_id) WHERE (source_document_id IS NOT NULL);


--
-- Name: idx_session_chunks_structural_position; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_session_chunks_structural_position ON learning.session_chunks USING gin (structural_position);


--
-- Name: idx_session_chunks_temporal_context; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_session_chunks_temporal_context ON learning.session_chunks USING gin (temporal_context);


--
-- Name: idx_session_chunks_temporal_year; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_session_chunks_temporal_year ON learning.session_chunks USING btree ((((temporal_context ->> 'publication_year'::text))::integer)) WHERE ((temporal_context ->> 'publication_year'::text) IS NOT NULL);


--
-- Name: idx_session_chunks_topics; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_session_chunks_topics ON learning.session_chunks USING gin (topics);


--
-- Name: idx_status; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_status ON learning.model_censorship USING btree (status);


--
-- Name: idx_strategy_perf_lookup; Type: INDEX; Schema: learning; Owner: sfloess
--

CREATE INDEX idx_strategy_perf_lookup ON learning.strategy_performance_multi USING btree (capability, task_type, strategy);


--
-- Name: idx_vec_claude_memory_emb; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_vec_claude_memory_emb ON learning.vec_claude_memory USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_vec_scale_test_1783055901_emb; Type: INDEX; Schema: learning; Owner: sfloess
--

CREATE INDEX idx_vec_scale_test_1783055901_emb ON learning.vec_scale_test_1783055901 USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_vec_scale_test_1783055962_emb; Type: INDEX; Schema: learning; Owner: sfloess
--

CREATE INDEX idx_vec_scale_test_1783055962_emb ON learning.vec_scale_test_1783055962 USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_vec_scale_test_1783055991_emb; Type: INDEX; Schema: learning; Owner: sfloess
--

CREATE INDEX idx_vec_scale_test_1783055991_emb ON learning.vec_scale_test_1783055991 USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_vec_scale_test_1783056573_emb; Type: INDEX; Schema: learning; Owner: sfloess
--

CREATE INDEX idx_vec_scale_test_1783056573_emb ON learning.vec_scale_test_1783056573 USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_verification_status; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_verification_status ON learning.research_chunks USING btree (verification_status);


--
-- Name: idx_web_synthesis_batch; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX idx_web_synthesis_batch ON learning.web_synthesis USING btree (batch_id, worker_id);


--
-- Name: infrastructure_knowledge_embedding_idx; Type: INDEX; Schema: learning; Owner: postgres
--

CREATE INDEX infrastructure_knowledge_embedding_idx ON learning.infrastructure_knowledge USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: pdf_embedding_idx; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX pdf_embedding_idx ON learning.pdf_metadata USING ivfflat (embedding public.vector_cosine_ops);


--
-- Name: pdf_knowledge_category_idx; Type: INDEX; Schema: learning; Owner: sfloess
--

CREATE INDEX pdf_knowledge_category_idx ON learning.pdf_knowledge USING btree (category);


--
-- Name: pdf_knowledge_confidence_idx; Type: INDEX; Schema: learning; Owner: sfloess
--

CREATE INDEX pdf_knowledge_confidence_idx ON learning.pdf_knowledge USING btree (confidence DESC);


--
-- Name: pdf_knowledge_embedding_idx; Type: INDEX; Schema: learning; Owner: sfloess
--

CREATE INDEX pdf_knowledge_embedding_idx ON learning.pdf_knowledge USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: queue_status_summary_queue_type_idx; Type: INDEX; Schema: learning; Owner: claude
--

CREATE UNIQUE INDEX queue_status_summary_queue_type_idx ON learning.queue_status_summary USING btree (queue_type);


--
-- Name: research_chunks_doc_id_idx; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX research_chunks_doc_id_idx ON learning.research_chunks USING btree (doc_id);


--
-- Name: research_chunks_embedding_idx; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX research_chunks_embedding_idx ON learning.research_chunks USING hnsw (chunk_embedding public.vector_cosine_ops);


--
-- Name: research_findings_embedding_idx; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX research_findings_embedding_idx ON learning.research_findings USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: research_full_chunk_idx; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX research_full_chunk_idx ON learning.research_full USING btree (chunk_index);


--
-- Name: research_full_created_idx; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX research_full_created_idx ON learning.research_full USING btree (created_at);


--
-- Name: research_full_embedding_idx; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX research_full_embedding_idx ON learning.research_full USING hnsw (embedding public.vector_cosine_ops) WITH (m='16', ef_construction='64');


--
-- Name: research_full_finding_idx; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX research_full_finding_idx ON learning.research_full USING btree (finding_id);


--
-- Name: research_full_query_idx; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX research_full_query_idx ON learning.research_full USING btree (query);


--
-- Name: research_full_relevance_idx; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX research_full_relevance_idx ON learning.research_full USING btree (relevance_score);


--
-- Name: research_full_timestamp_idx; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX research_full_timestamp_idx ON learning.research_full USING btree ("timestamp");


--
-- Name: session_chunks_embedding_idx; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX session_chunks_embedding_idx ON learning.session_chunks USING hnsw (chunk_embedding public.vector_cosine_ops);


--
-- Name: session_chunks_text_gin_idx; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX session_chunks_text_gin_idx ON learning.session_chunks USING gin (chunk_text public.gin_trgm_ops);


--
-- Name: sessions_summary_embedding_idx; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX sessions_summary_embedding_idx ON learning.sessions USING hnsw (summary_embedding public.vector_cosine_ops);


--
-- Name: sessions_title_embedding_idx; Type: INDEX; Schema: learning; Owner: claude
--

CREATE INDEX sessions_title_embedding_idx ON learning.sessions USING hnsw (title_embedding public.vector_cosine_ops);


--
-- Name: unique_content_hash_research; Type: INDEX; Schema: learning; Owner: claude
--

CREATE UNIQUE INDEX unique_content_hash_research ON learning.research_chunks USING btree (content_hash) WHERE (content_hash IS NOT NULL);


--
-- Name: human_correction_summary_model_correction_type_idx; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE UNIQUE INDEX human_correction_summary_model_correction_type_idx ON monitoring.human_correction_summary USING btree (model, correction_type);


--
-- Name: idx_api_health_checks_provider_created; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_api_health_checks_provider_created ON monitoring.api_health_checks USING btree (provider, created_at DESC);


--
-- Name: idx_api_usage_created; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_api_usage_created ON monitoring.api_usage USING btree (created_at DESC);


--
-- Name: idx_api_usage_endpoint; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_api_usage_endpoint ON monitoring.api_usage USING btree (endpoint);


--
-- Name: idx_api_usage_key; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_api_usage_key ON monitoring.api_usage USING btree (api_key_id);


--
-- Name: idx_cbe_event; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_cbe_event ON monitoring.circuit_breaker_events USING btree (event, created_at);


--
-- Name: idx_cbe_model; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_cbe_model ON monitoring.circuit_breaker_events USING btree (model);


--
-- Name: idx_confidence_calibration_error; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_confidence_calibration_error ON monitoring.confidence_calibration USING btree (calibration_error);


--
-- Name: idx_confidence_calibration_model; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_confidence_calibration_model ON monitoring.confidence_calibration USING btree (model);


--
-- Name: idx_confidence_calibration_over; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_confidence_calibration_over ON monitoring.confidence_calibration USING btree (overconfident);


--
-- Name: idx_document_stats; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE UNIQUE INDEX idx_document_stats ON monitoring.document_stats USING btree (file_type, status);


--
-- Name: idx_dual_review_repo; Type: INDEX; Schema: monitoring; Owner: postgres
--

CREATE INDEX idx_dual_review_repo ON monitoring.dual_review_results USING btree (repo_name);


--
-- Name: idx_dual_review_timestamp; Type: INDEX; Schema: monitoring; Owner: postgres
--

CREATE INDEX idx_dual_review_timestamp ON monitoring.dual_review_results USING btree ("timestamp" DESC);


--
-- Name: idx_exec_model; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_exec_model ON monitoring.execution_log USING btree (model);


--
-- Name: idx_exec_summary_outcome; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_exec_summary_outcome ON monitoring.execution_summary USING btree (outcome);


--
-- Name: idx_exec_summary_outcome_timestamp; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_exec_summary_outcome_timestamp ON monitoring.execution_summary USING btree (outcome, "timestamp" DESC);


--
-- Name: idx_exec_summary_task_type; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_exec_summary_task_type ON monitoring.execution_summary USING btree (task_type);


--
-- Name: idx_exec_summary_timestamp; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_exec_summary_timestamp ON monitoring.execution_summary USING btree ("timestamp" DESC);


--
-- Name: idx_exec_timestamp; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_exec_timestamp ON monitoring.execution_log USING btree ("timestamp" DESC);


--
-- Name: idx_exec_workflow; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_exec_workflow ON monitoring.execution_log USING btree (workflow);


--
-- Name: idx_execution_circuit_breaker; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_execution_circuit_breaker ON monitoring.execution_summary USING btree (circuit_breaker_state);


--
-- Name: idx_execution_quality; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_execution_quality ON monitoring.execution_summary USING btree (quality_score);


--
-- Name: idx_execution_quality_outcome; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_execution_quality_outcome ON monitoring.execution_summary USING btree (quality_score, outcome);


--
-- Name: idx_external_service_time; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_external_service_time ON monitoring.external_api_calls USING btree (service, "timestamp");


--
-- Name: idx_external_timestamp; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_external_timestamp ON monitoring.external_api_calls USING btree ("timestamp");


--
-- Name: idx_external_worker; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_external_worker ON monitoring.external_api_calls USING btree (worker_id, "timestamp");


--
-- Name: idx_fleet_health_timestamp; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_fleet_health_timestamp ON monitoring.fleet_health USING btree (hostname, last_seen DESC);


--
-- Name: idx_health_predictions_critical; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_health_predictions_critical ON monitoring.health_predictions USING btree (decision_urgency) WHERE (decision_urgency = ANY (ARRAY['critical'::text, 'high'::text]));


--
-- Name: idx_health_predictions_degradation; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_health_predictions_degradation ON monitoring.health_predictions USING btree (degradation_probability DESC) WHERE (degradation_probability >= (0.70)::double precision);


--
-- Name: idx_health_predictions_hostname_predicted; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_health_predictions_hostname_predicted ON monitoring.health_predictions USING btree (hostname, predicted_at DESC);


--
-- Name: idx_health_predictions_recent; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_health_predictions_recent ON monitoring.health_predictions USING btree (predicted_at DESC);


--
-- Name: idx_human_corrections_created; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_human_corrections_created ON monitoring.human_corrections USING btree (created_at);


--
-- Name: idx_human_corrections_model; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_human_corrections_model ON monitoring.human_corrections USING btree (model);


--
-- Name: idx_human_corrections_severity; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_human_corrections_severity ON monitoring.human_corrections USING btree (severity);


--
-- Name: idx_human_corrections_type; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_human_corrections_type ON monitoring.human_corrections USING btree (correction_type);


--
-- Name: idx_llm_provider_usage_provider; Type: INDEX; Schema: monitoring; Owner: postgres
--

CREATE INDEX idx_llm_provider_usage_provider ON monitoring.llm_provider_usage USING btree (provider, success);


--
-- Name: idx_llm_provider_usage_timestamp; Type: INDEX; Schema: monitoring; Owner: postgres
--

CREATE INDEX idx_llm_provider_usage_timestamp ON monitoring.llm_provider_usage USING btree ("timestamp" DESC);


--
-- Name: idx_model_capabilities_executions; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_model_capabilities_executions ON monitoring.model_capabilities USING btree (executions DESC) WHERE (executions >= 10);


--
-- Name: idx_model_capabilities_lookup; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_model_capabilities_lookup ON monitoring.model_capabilities USING btree (model, task_type);


--
-- Name: idx_model_capabilities_task; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_model_capabilities_task ON monitoring.model_capabilities USING btree (task_type, capability_score DESC);


--
-- Name: idx_model_capabilities_top_task; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE UNIQUE INDEX idx_model_capabilities_top_task ON monitoring.model_capabilities_top USING btree (task_type);


--
-- Name: idx_model_retraining_created; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_model_retraining_created ON monitoring.model_retraining USING btree (created_at);


--
-- Name: idx_model_retraining_model; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_model_retraining_model ON monitoring.model_retraining USING btree (model_name);


--
-- Name: idx_model_selections_timestamp; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_model_selections_timestamp ON monitoring.model_selections USING btree ("timestamp" DESC);


--
-- Name: idx_model_usage_anthropic_only; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_model_usage_anthropic_only ON monitoring.model_usage USING btree (anthropic_only);


--
-- Name: idx_model_usage_model; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_model_usage_model ON monitoring.model_usage USING btree (model);


--
-- Name: idx_model_usage_task_type; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_model_usage_task_type ON monitoring.model_usage USING btree (task_type);


--
-- Name: idx_model_usage_timestamp; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_model_usage_timestamp ON monitoring.model_usage USING btree ("timestamp" DESC);


--
-- Name: idx_network_latency_dest; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_network_latency_dest ON monitoring.network_latency_matrix USING btree (destination_host);


--
-- Name: idx_network_latency_measured; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_network_latency_measured ON monitoring.network_latency_matrix USING btree (measured_at);


--
-- Name: idx_network_latency_source; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_network_latency_source ON monitoring.network_latency_matrix USING btree (source_host);


--
-- Name: idx_network_measurements_target; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_network_measurements_target ON monitoring.network_measurements USING btree (target_node);


--
-- Name: idx_network_measurements_timestamp; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_network_measurements_timestamp ON monitoring.network_measurements USING btree ("timestamp");


--
-- Name: idx_network_predictions_timestamp; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_network_predictions_timestamp ON monitoring.network_predictions USING btree ("timestamp");


--
-- Name: idx_prediction_accuracy_created_at; Type: INDEX; Schema: monitoring; Owner: postgres
--

CREATE INDEX idx_prediction_accuracy_created_at ON monitoring.prediction_accuracy USING btree (created_at);


--
-- Name: idx_prediction_accuracy_model; Type: INDEX; Schema: monitoring; Owner: postgres
--

CREATE INDEX idx_prediction_accuracy_model ON monitoring.prediction_accuracy USING btree (model);


--
-- Name: idx_prediction_accuracy_workflow; Type: INDEX; Schema: monitoring; Owner: postgres
--

CREATE INDEX idx_prediction_accuracy_workflow ON monitoring.prediction_accuracy USING btree (workflow_name);


--
-- Name: idx_queue_health_measured; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_queue_health_measured ON monitoring.queue_health USING btree (measured_at);


--
-- Name: idx_queue_health_name; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_queue_health_name ON monitoring.queue_health USING btree (queue_name);


--
-- Name: idx_rate_limit_service_time; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_rate_limit_service_time ON monitoring.rate_limit_hits USING btree (service, "timestamp");


--
-- Name: idx_rate_limits_last_reset; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_rate_limits_last_reset ON monitoring.rate_limits USING btree (last_reset);


--
-- Name: idx_resource_coefficients_trained_at; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_resource_coefficients_trained_at ON monitoring.resource_estimation_coefficients USING btree (trained_at DESC);


--
-- Name: idx_resource_estimation_error; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_resource_estimation_error ON monitoring.resource_estimation_log USING btree (duration_error DESC, ram_error DESC);


--
-- Name: idx_resource_estimation_model; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_resource_estimation_model ON monitoring.resource_estimation_log USING btree (model, job_type);


--
-- Name: idx_resource_estimation_timestamp; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_resource_estimation_timestamp ON monitoring.resource_estimation_log USING btree ("timestamp" DESC);


--
-- Name: idx_resource_usage_created_at; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_resource_usage_created_at ON monitoring.resource_usage USING btree (created_at);


--
-- Name: idx_resource_usage_workflow_execution_id; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_resource_usage_workflow_execution_id ON monitoring.resource_usage USING btree (workflow_execution_id);


--
-- Name: idx_resource_usage_workflow_id; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_resource_usage_workflow_id ON monitoring.resource_usage USING btree (workflow_id);


--
-- Name: idx_rlr_provider_timestamp; Type: INDEX; Schema: monitoring; Owner: sfloess
--

CREATE INDEX idx_rlr_provider_timestamp ON monitoring.rate_limit_requests USING btree (provider, "timestamp" DESC);


--
-- Name: idx_scraping_metrics_node; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_scraping_metrics_node ON monitoring.scraping_metrics USING btree (node, "timestamp" DESC);


--
-- Name: idx_scraping_metrics_timestamp; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_scraping_metrics_timestamp ON monitoring.scraping_metrics USING btree ("timestamp" DESC);


--
-- Name: idx_task_attribution_model; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_task_attribution_model ON monitoring.task_attribution USING btree (model);


--
-- Name: idx_task_attribution_type; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_task_attribution_type ON monitoring.task_attribution USING btree (contribution_type);


--
-- Name: idx_task_attribution_workflow; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_task_attribution_workflow ON monitoring.task_attribution USING btree (workflow_execution_id);


--
-- Name: idx_training_jobs_created; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_training_jobs_created ON monitoring.training_jobs USING btree (created_at);


--
-- Name: idx_training_jobs_model; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_training_jobs_model ON monitoring.training_jobs USING btree (model_name);


--
-- Name: idx_training_jobs_platform; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_training_jobs_platform ON monitoring.training_jobs USING btree (platform);


--
-- Name: idx_training_jobs_status; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_training_jobs_status ON monitoring.training_jobs USING btree (status);


--
-- Name: idx_workers_last_heartbeat; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_workers_last_heartbeat ON monitoring.workers USING btree (last_heartbeat);


--
-- Name: idx_workers_status; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE INDEX idx_workers_status ON monitoring.workers USING btree (status);


--
-- Name: model_attribution_summary_model_contribution_type_idx; Type: INDEX; Schema: monitoring; Owner: claude
--

CREATE UNIQUE INDEX model_attribution_summary_model_contribution_type_idx ON monitoring.model_attribution_summary USING btree (model, contribution_type);


--
-- Name: idx_auto_storage_embedding; Type: INDEX; Schema: orchestration; Owner: sfloess
--

CREATE INDEX idx_auto_storage_embedding ON orchestration.auto_storage USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_auto_storage_source; Type: INDEX; Schema: orchestration; Owner: sfloess
--

CREATE INDEX idx_auto_storage_source ON orchestration.auto_storage USING btree (source_type, source_id);


--
-- Name: idx_progress_task_time; Type: INDEX; Schema: orchestration; Owner: sfloess
--

CREATE INDEX idx_progress_task_time ON orchestration.task_progress_log USING btree (task_id, "timestamp" DESC);


--
-- Name: idx_queue_summary_unique; Type: INDEX; Schema: orchestration; Owner: sfloess
--

CREATE UNIQUE INDEX idx_queue_summary_unique ON orchestration.queue_summary USING btree (status, task_type);


--
-- Name: idx_task_queue_created; Type: INDEX; Schema: orchestration; Owner: sfloess
--

CREATE INDEX idx_task_queue_created ON orchestration.task_queue USING btree (created_at);


--
-- Name: idx_task_queue_embedding; Type: INDEX; Schema: orchestration; Owner: sfloess
--

CREATE INDEX idx_task_queue_embedding ON orchestration.task_queue USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_task_queue_priority; Type: INDEX; Schema: orchestration; Owner: sfloess
--

CREATE INDEX idx_task_queue_priority ON orchestration.task_queue USING btree (priority DESC);


--
-- Name: idx_task_queue_status; Type: INDEX; Schema: orchestration; Owner: sfloess
--

CREATE INDEX idx_task_queue_status ON orchestration.task_queue USING btree (status);


--
-- Name: idx_task_queue_type; Type: INDEX; Schema: orchestration; Owner: sfloess
--

CREATE INDEX idx_task_queue_type ON orchestration.task_queue USING btree (task_type);


--
-- Name: idx_task_queue_worker; Type: INDEX; Schema: orchestration; Owner: sfloess
--

CREATE INDEX idx_task_queue_worker ON orchestration.task_queue USING btree (assigned_worker);


--
-- Name: idx_worker_util_unique; Type: INDEX; Schema: orchestration; Owner: sfloess
--

CREATE UNIQUE INDEX idx_worker_util_unique ON orchestration.worker_utilization USING btree (worker_id);


--
-- Name: idx_file_locks_expires; Type: INDEX; Schema: orchestrator; Owner: sfloess
--

CREATE INDEX idx_file_locks_expires ON orchestrator.file_locks USING btree (expires_at);


--
-- Name: idx_messages_to; Type: INDEX; Schema: orchestrator; Owner: sfloess
--

CREATE INDEX idx_messages_to ON orchestrator.messages USING btree (to_session, read_at) WHERE (read_at IS NULL);


--
-- Name: idx_sessions_heartbeat; Type: INDEX; Schema: orchestrator; Owner: sfloess
--

CREATE INDEX idx_sessions_heartbeat ON orchestrator.sessions USING btree (last_heartbeat);


--
-- Name: idx_sessions_node; Type: INDEX; Schema: orchestrator; Owner: sfloess
--

CREATE INDEX idx_sessions_node ON orchestrator.sessions USING btree (node_id);


--
-- Name: idx_sessions_status; Type: INDEX; Schema: orchestrator; Owner: sfloess
--

CREATE INDEX idx_sessions_status ON orchestrator.sessions USING btree (status) WHERE (status = 'active'::text);


--
-- Name: idx_work_assigned; Type: INDEX; Schema: orchestrator; Owner: sfloess
--

CREATE INDEX idx_work_assigned ON orchestrator.work_queue USING btree (assigned_to) WHERE (status = 'assigned'::text);


--
-- Name: idx_work_pending_priority; Type: INDEX; Schema: orchestrator; Owner: sfloess
--

CREATE INDEX idx_work_pending_priority ON orchestrator.work_queue USING btree (status, priority DESC, enqueued_at) WHERE (status = 'pending'::text);


--
-- Name: idx_chunks_embedded; Type: INDEX; Schema: processing; Owner: sfloess
--

CREATE INDEX idx_chunks_embedded ON processing.chunks USING btree (embedded_at) WHERE (embedded_at IS NULL);


--
-- Name: idx_chunks_graphed; Type: INDEX; Schema: processing; Owner: sfloess
--

CREATE INDEX idx_chunks_graphed ON processing.chunks USING btree (graphed_at) WHERE (graphed_at IS NULL);


--
-- Name: idx_chunks_source_file; Type: INDEX; Schema: processing; Owner: sfloess
--

CREATE INDEX idx_chunks_source_file ON processing.chunks USING btree (source_file_id);


--
-- Name: idx_queue_claimed; Type: INDEX; Schema: processing; Owner: sfloess
--

CREATE INDEX idx_queue_claimed ON processing.work_queue USING btree (claimed_by, claimed_at) WHERE ((claimed_at IS NOT NULL) AND (completed_at IS NULL));


--
-- Name: idx_queue_stale; Type: INDEX; Schema: processing; Owner: sfloess
--

CREATE INDEX idx_queue_stale ON processing.work_queue USING btree (queue_type, claimed_at) WHERE ((claimed_at IS NOT NULL) AND (completed_at IS NULL));


--
-- Name: idx_queue_type_pending; Type: INDEX; Schema: processing; Owner: sfloess
--

CREATE INDEX idx_queue_type_pending ON processing.work_queue USING btree (queue_type, priority DESC, created_at) WHERE ((claimed_at IS NULL) AND (failed_at IS NULL));


--
-- Name: idx_source_files_source; Type: INDEX; Schema: processing; Owner: sfloess
--

CREATE INDEX idx_source_files_source ON processing.source_files USING btree (source);


--
-- Name: idx_source_files_status; Type: INDEX; Schema: processing; Owner: sfloess
--

CREATE INDEX idx_source_files_status ON processing.source_files USING btree (status);


--
-- Name: idx_stats_time_queue; Type: INDEX; Schema: processing; Owner: sfloess
--

CREATE INDEX idx_stats_time_queue ON processing.processing_stats USING btree (recorded_at, queue_type);


--
-- Name: idx_workers_active; Type: INDEX; Schema: processing; Owner: sfloess
--

CREATE INDEX idx_workers_active ON processing.workers USING btree (last_heartbeat) WHERE (status = 'active'::text);


--
-- Name: pipeline_summary_status_idx; Type: INDEX; Schema: processing; Owner: sfloess
--

CREATE UNIQUE INDEX pipeline_summary_status_idx ON processing.pipeline_summary USING btree (status);


--
-- Name: pipeline_summary_status_idx1; Type: INDEX; Schema: processing; Owner: sfloess
--

CREATE UNIQUE INDEX pipeline_summary_status_idx1 ON processing.pipeline_summary USING btree (status);


--
-- Name: queue_summary_queue_type_idx; Type: INDEX; Schema: processing; Owner: sfloess
--

CREATE UNIQUE INDEX queue_summary_queue_type_idx ON processing.queue_summary USING btree (queue_type);


--
-- Name: queue_summary_queue_type_idx1; Type: INDEX; Schema: processing; Owner: sfloess
--

CREATE UNIQUE INDEX queue_summary_queue_type_idx1 ON processing.queue_summary USING btree (queue_type);


--
-- Name: idx_api_cache_hash; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_api_cache_hash ON public.api_cache USING btree (request_hash);


--
-- Name: idx_api_failures_provider; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_api_failures_provider ON public.api_failures USING btree (requested_provider, "timestamp" DESC);


--
-- Name: idx_api_failures_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_api_failures_timestamp ON public.api_failures USING btree ("timestamp" DESC);


--
-- Name: idx_api_usage_worker; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_api_usage_worker ON public.api_usage USING btree (worker_id, "timestamp" DESC);


--
-- Name: idx_embedding_usage_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_embedding_usage_timestamp ON public.api_embedding_usage USING btree ("timestamp" DESC);


--
-- Name: idx_embedding_usage_worker; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_embedding_usage_worker ON public.api_embedding_usage USING btree (worker_id, "timestamp" DESC);


--
-- Name: idx_models_name; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_models_name ON public.api_models USING btree (model_name);


--
-- Name: idx_models_provider; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_models_provider ON public.api_models USING btree (provider, enabled);


--
-- Name: idx_models_tier; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_models_tier ON public.api_models USING btree (tier, enabled);


--
-- Name: idx_session_context_updated; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_session_context_updated ON public.session_context USING btree (updated_at DESC);


--
-- Name: pdf_knowledge_category_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX pdf_knowledge_category_idx ON public.pdf_knowledge USING btree (category);


--
-- Name: pdf_knowledge_confidence_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX pdf_knowledge_confidence_idx ON public.pdf_knowledge USING btree (confidence DESC);


--
-- Name: pdf_knowledge_embedding_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX pdf_knowledge_embedding_idx ON public.pdf_knowledge USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: pdf_knowledge_pdf_path_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX pdf_knowledge_pdf_path_idx ON public.pdf_knowledge USING btree (pdf_path);


--
-- Name: idx_chunk_idempotency_key; Type: INDEX; Schema: queue; Owner: postgres
--

CREATE INDEX idx_chunk_idempotency_key ON queue.chunk USING btree (idempotency_key) WHERE (idempotency_key IS NOT NULL);


--
-- Name: idx_chunk_pending; Type: INDEX; Schema: queue; Owner: postgres
--

CREATE INDEX idx_chunk_pending ON queue.chunk USING btree (status, priority DESC, created_at) WHERE (status = 'pending'::text);


--
-- Name: idx_embed_idempotency_key; Type: INDEX; Schema: queue; Owner: postgres
--

CREATE INDEX idx_embed_idempotency_key ON queue.embed USING btree (idempotency_key) WHERE (idempotency_key IS NOT NULL);


--
-- Name: idx_embed_pending; Type: INDEX; Schema: queue; Owner: postgres
--

CREATE INDEX idx_embed_pending ON queue.embed USING btree (status, priority DESC, created_at) WHERE (status = 'pending'::text);


--
-- Name: idx_graph_idempotency_key; Type: INDEX; Schema: queue; Owner: postgres
--

CREATE INDEX idx_graph_idempotency_key ON queue.graph USING btree (idempotency_key) WHERE (idempotency_key IS NOT NULL);


--
-- Name: idx_graph_pending; Type: INDEX; Schema: queue; Owner: postgres
--

CREATE INDEX idx_graph_pending ON queue.graph USING btree (status, priority DESC, created_at) WHERE (status = 'pending'::text);


--
-- Name: idx_store_idempotency_key; Type: INDEX; Schema: queue; Owner: postgres
--

CREATE INDEX idx_store_idempotency_key ON queue.store USING btree (idempotency_key) WHERE (idempotency_key IS NOT NULL);


--
-- Name: idx_store_pending; Type: INDEX; Schema: queue; Owner: postgres
--

CREATE INDEX idx_store_pending ON queue.store USING btree (status, priority DESC, created_at) WHERE (status = 'pending'::text);


--
-- Name: idx_tasks_claim; Type: INDEX; Schema: queue; Owner: claude
--

CREATE INDEX idx_tasks_claim ON queue.tasks USING btree (status, priority DESC, created_at) WHERE ((status)::text = 'pending'::text);


--
-- Name: idx_worker_heartbeat_timeout; Type: INDEX; Schema: queue; Owner: sfloess
--

CREATE INDEX idx_worker_heartbeat_timeout ON queue.worker_heartbeat USING btree (last_heartbeat);


--
-- Name: idx_evidence_embedding; Type: INDEX; Schema: reasoning; Owner: claude
--

CREATE INDEX idx_evidence_embedding ON reasoning.evidence USING ivfflat (embedding public.vector_cosine_ops) WITH (lists='100');


--
-- Name: idx_hypotheses_embedding; Type: INDEX; Schema: reasoning; Owner: claude
--

CREATE INDEX idx_hypotheses_embedding ON reasoning.hypotheses USING ivfflat (embedding public.vector_cosine_ops) WITH (lists='100');


--
-- Name: idx_scraping_tasks_category; Type: INDEX; Schema: scraping; Owner: sfloess
--

CREATE INDEX idx_scraping_tasks_category ON scraping.tasks USING btree (category);


--
-- Name: idx_scraping_tasks_created_at; Type: INDEX; Schema: scraping; Owner: sfloess
--

CREATE INDEX idx_scraping_tasks_created_at ON scraping.tasks USING btree (created_at);


--
-- Name: idx_scraping_tasks_priority; Type: INDEX; Schema: scraping; Owner: sfloess
--

CREATE INDEX idx_scraping_tasks_priority ON scraping.tasks USING btree (priority DESC);


--
-- Name: idx_scraping_tasks_status; Type: INDEX; Schema: scraping; Owner: sfloess
--

CREATE INDEX idx_scraping_tasks_status ON scraping.tasks USING btree (status);


--
-- Name: knowledge_base_category_idx; Type: INDEX; Schema: search; Owner: postgres
--

CREATE INDEX knowledge_base_category_idx ON search.knowledge_base USING btree (category);


--
-- Name: knowledge_base_search_idx; Type: INDEX; Schema: search; Owner: postgres
--

CREATE INDEX knowledge_base_search_idx ON search.knowledge_base USING gin (search_vector);


--
-- Name: idx_api_calls_created_at; Type: INDEX; Schema: storage; Owner: claude
--

CREATE INDEX idx_api_calls_created_at ON storage.api_calls USING btree (created_at);


--
-- Name: idx_api_calls_model; Type: INDEX; Schema: storage; Owner: claude
--

CREATE INDEX idx_api_calls_model ON storage.api_calls USING btree (model);


--
-- Name: idx_api_calls_worker_id; Type: INDEX; Schema: storage; Owner: claude
--

CREATE INDEX idx_api_calls_worker_id ON storage.api_calls USING btree (worker_id);


--
-- Name: idx_arbiter_decisions_created_at; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_arbiter_decisions_created_at ON workflow.arbiter_decisions USING btree (created_at DESC);


--
-- Name: idx_arbiter_decisions_embedding; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_arbiter_decisions_embedding ON workflow.arbiter_decisions USING ivfflat (decision_embedding public.vector_cosine_ops) WITH (lists='100');


--
-- Name: idx_arbiter_decisions_model; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_arbiter_decisions_model ON workflow.arbiter_decisions USING btree (arbiter_model);


--
-- Name: idx_arbiter_decisions_workflow; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_arbiter_decisions_workflow ON workflow.arbiter_decisions USING btree (workflow_execution_id);


--
-- Name: idx_cache_model_prompt; Type: INDEX; Schema: workflow; Owner: postgres
--

CREATE INDEX idx_cache_model_prompt ON workflow.response_cache USING btree (model, prompt_hash);


--
-- Name: idx_consensus_cache_embedding; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_consensus_cache_embedding ON workflow.consensus_cache USING hnsw (question_embedding public.vector_cosine_ops);


--
-- Name: idx_consensus_cache_expires; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_consensus_cache_expires ON workflow.consensus_cache USING btree (expires_at);


--
-- Name: idx_consensus_cache_key; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_consensus_cache_key ON workflow.consensus_cache USING btree (cache_key);


--
-- Name: idx_executions_created_at; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_executions_created_at ON workflow.executions USING btree (created_at DESC);


--
-- Name: idx_executions_embedding; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_executions_embedding ON workflow.executions USING ivfflat (task_embedding public.vector_cosine_ops) WITH (lists='100');


--
-- Name: idx_executions_execution_hosts; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_executions_execution_hosts ON workflow.executions USING gin (execution_hosts);


--
-- Name: idx_executions_outcome; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_executions_outcome ON workflow.executions USING btree (outcome);


--
-- Name: idx_executions_outcome_workers_created; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_executions_outcome_workers_created ON workflow.executions USING btree (outcome, total_workers, created_at DESC);


--
-- Name: idx_executions_total_workers; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_executions_total_workers ON workflow.executions USING btree (total_workers);


--
-- Name: idx_executions_workflow_id; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_executions_workflow_id ON workflow.executions USING btree (workflow_id);


--
-- Name: idx_feedback_processed; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_feedback_processed ON workflow.feedback USING btree (processed) WHERE (processed = false);


--
-- Name: idx_feedback_type; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_feedback_type ON workflow.feedback USING btree (feedback_type);


--
-- Name: idx_feedback_workflow; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_feedback_workflow ON workflow.feedback USING btree (workflow_execution_id);


--
-- Name: idx_phases_order; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_phases_order ON workflow.phases USING btree (workflow_execution_id, phase_order);


--
-- Name: idx_phases_workflow; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_phases_workflow ON workflow.phases USING btree (workflow_execution_id);


--
-- Name: idx_prediction_accuracy_created; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_prediction_accuracy_created ON workflow.prediction_accuracy USING btree (created_at DESC);


--
-- Name: idx_prediction_accuracy_outcome; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_prediction_accuracy_outcome ON workflow.prediction_accuracy USING btree (outcome);


--
-- Name: idx_prediction_accuracy_workflow; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_prediction_accuracy_workflow ON workflow.prediction_accuracy USING btree (workflow_name, created_at DESC);


--
-- Name: idx_response_cache_model_prompt; Type: INDEX; Schema: workflow; Owner: postgres
--

CREATE INDEX idx_response_cache_model_prompt ON workflow.response_cache USING btree (model, prompt_hash);


--
-- Name: idx_rotation_model; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_rotation_model ON workflow.model_rotation_schedule USING btree (model);


--
-- Name: idx_rotation_stage; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_rotation_stage ON workflow.model_rotation_schedule USING btree (rollout_stage);


--
-- Name: idx_rotation_stale; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_rotation_stale ON workflow.model_rotation_schedule USING btree (is_stale);


--
-- Name: idx_worker_results_created_at; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_worker_results_created_at ON workflow.worker_results USING btree (created_at DESC);


--
-- Name: idx_worker_results_embedding; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_worker_results_embedding ON workflow.worker_results USING ivfflat (result_embedding public.vector_cosine_ops) WITH (lists='100');


--
-- Name: idx_worker_results_execution_host; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_worker_results_execution_host ON workflow.worker_results USING btree (execution_host);


--
-- Name: idx_worker_results_model; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_worker_results_model ON workflow.worker_results USING btree (model);


--
-- Name: idx_worker_results_outcome; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_worker_results_outcome ON workflow.worker_results USING btree (outcome);


--
-- Name: idx_worker_results_outcome_created_at; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_worker_results_outcome_created_at ON workflow.worker_results USING btree (outcome, created_at DESC);


--
-- Name: idx_worker_results_tokens; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_worker_results_tokens ON workflow.worker_results USING btree (input_tokens, output_tokens);


--
-- Name: idx_worker_results_workflow; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_worker_results_workflow ON workflow.worker_results USING btree (workflow_execution_id);


--
-- Name: idx_workflow_quality; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_workflow_quality ON workflow.executions USING btree (quality_score);


--
-- Name: idx_workflow_quality_outcome; Type: INDEX; Schema: workflow; Owner: sfloess
--

CREATE INDEX idx_workflow_quality_outcome ON workflow.executions USING btree (quality_score, outcome);


--
-- Name: idx_arbiter_decisions_confidence; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_arbiter_decisions_confidence ON workflows.arbiter_decisions USING btree (confidence DESC NULLS LAST);


--
-- Name: idx_arbiter_decisions_execution; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_arbiter_decisions_execution ON workflows.arbiter_decisions USING btree (execution_id);


--
-- Name: idx_arbiter_decisions_model; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_arbiter_decisions_model ON workflows.arbiter_decisions USING btree (arbiter_model);


--
-- Name: idx_execution_embeddings_context; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_execution_embeddings_context ON workflows.execution_embeddings USING hnsw (context_embedding public.vector_cosine_ops) WITH (m='16', ef_construction='64');


--
-- Name: idx_execution_embeddings_input; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_execution_embeddings_input ON workflows.execution_embeddings USING hnsw (input_embedding public.vector_cosine_ops) WITH (m='16', ef_construction='64');


--
-- Name: idx_execution_embeddings_output; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_execution_embeddings_output ON workflows.execution_embeddings USING hnsw (output_embedding public.vector_cosine_ops) WITH (m='16', ef_construction='64');


--
-- Name: idx_execution_phases_execution; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_execution_phases_execution ON workflows.execution_phases USING btree (execution_id);


--
-- Name: idx_execution_phases_order; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_execution_phases_order ON workflows.execution_phases USING btree (execution_id, phase_order);


--
-- Name: idx_executions_metadata; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_executions_metadata ON workflows.executions USING gin (metadata);


--
-- Name: idx_executions_started; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_executions_started ON workflows.executions USING btree (started_at DESC);


--
-- Name: idx_executions_status; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_executions_status ON workflows.executions USING btree (status);


--
-- Name: idx_executions_workflow; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_executions_workflow ON workflows.executions USING btree (workflow_name);


--
-- Name: idx_feedback_execution; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_feedback_execution ON workflows.feedback USING btree (execution_id);


--
-- Name: idx_feedback_rating; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_feedback_rating ON workflows.feedback USING btree (rating);


--
-- Name: idx_feedback_type; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_feedback_type ON workflows.feedback USING btree (feedback_type);


--
-- Name: idx_learnings_embedding; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_learnings_embedding ON workflows.learnings USING hnsw (embedding public.vector_cosine_ops) WITH (m='16', ef_construction='64');


--
-- Name: idx_learnings_impact; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_learnings_impact ON workflows.learnings USING btree (impact_score DESC NULLS LAST);


--
-- Name: idx_learnings_type; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_learnings_type ON workflows.learnings USING btree (learning_type);


--
-- Name: idx_learnings_workflow; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_learnings_workflow ON workflows.learnings USING btree (workflow_name);


--
-- Name: idx_model_combinations_quality; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_model_combinations_quality ON workflows.model_combinations USING btree (avg_quality DESC NULLS LAST);


--
-- Name: idx_model_combinations_success; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_model_combinations_success ON workflows.model_combinations USING btree (success_rate DESC NULLS LAST);


--
-- Name: idx_model_combinations_workflow; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_model_combinations_workflow ON workflows.model_combinations USING btree (workflow_name);


--
-- Name: idx_model_performance_model; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE UNIQUE INDEX idx_model_performance_model ON workflows.model_performance USING btree (model);


--
-- Name: idx_summary_workflow; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE UNIQUE INDEX idx_summary_workflow ON workflows.summary USING btree (workflow_name);


--
-- Name: idx_worker_results_execution; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_worker_results_execution ON workflows.worker_results USING btree (execution_id);


--
-- Name: idx_worker_results_model; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_worker_results_model ON workflows.worker_results USING btree (model);


--
-- Name: idx_worker_results_quality; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_worker_results_quality ON workflows.worker_results USING btree (quality_score DESC NULLS LAST);


--
-- Name: idx_worker_results_status; Type: INDEX; Schema: workflows; Owner: sfloess
--

CREATE INDEX idx_worker_results_status ON workflows.worker_results USING btree (status);


--
-- Name: documents trigger_documents_updated_at; Type: TRIGGER; Schema: documents; Owner: sfloess
--

CREATE TRIGGER trigger_documents_updated_at BEFORE UPDATE ON documents.documents FOR EACH ROW EXECUTE FUNCTION documents.update_updated_at();


--
-- Name: results trg_update_overall_score; Type: TRIGGER; Schema: evaluation; Owner: sfloess
--

CREATE TRIGGER trg_update_overall_score BEFORE INSERT OR UPDATE ON evaluation.results FOR EACH ROW EXECUTE FUNCTION evaluation.update_result_overall_score();


--
-- Name: registry trg_registry_updated_at; Type: TRIGGER; Schema: experiments; Owner: sfloess
--

CREATE TRIGGER trg_registry_updated_at BEFORE UPDATE ON experiments.registry FOR EACH ROW EXECUTE FUNCTION experiments.update_registry_timestamp();


--
-- Name: request_history trigger_cleanup_request_history; Type: TRIGGER; Schema: learning; Owner: claude
--

CREATE TRIGGER trigger_cleanup_request_history AFTER INSERT ON learning.request_history FOR EACH ROW EXECUTE FUNCTION public.cleanup_request_history();


--
-- Name: model_capabilities trigger_model_capabilities_refresh; Type: TRIGGER; Schema: monitoring; Owner: sfloess
--

CREATE TRIGGER trigger_model_capabilities_refresh AFTER INSERT OR DELETE OR UPDATE ON monitoring.model_capabilities FOR EACH STATEMENT EXECUTE FUNCTION monitoring.trigger_refresh_capabilities_top();


--
-- Name: arbiter_decisions trigger_update_arbiter_duration; Type: TRIGGER; Schema: workflows; Owner: sfloess
--

CREATE TRIGGER trigger_update_arbiter_duration BEFORE UPDATE ON workflows.arbiter_decisions FOR EACH ROW EXECUTE FUNCTION workflows.update_arbiter_duration();


--
-- Name: executions trigger_update_execution_summary; Type: TRIGGER; Schema: workflows; Owner: sfloess
--

CREATE TRIGGER trigger_update_execution_summary BEFORE UPDATE ON workflows.executions FOR EACH ROW EXECUTE FUNCTION workflows.update_execution_summary();


--
-- Name: execution_phases trigger_update_phase_duration; Type: TRIGGER; Schema: workflows; Owner: sfloess
--

CREATE TRIGGER trigger_update_phase_duration BEFORE UPDATE ON workflows.execution_phases FOR EACH ROW EXECUTE FUNCTION workflows.update_phase_duration();


--
-- Name: worker_results trigger_update_worker_duration; Type: TRIGGER; Schema: workflows; Owner: sfloess
--

CREATE TRIGGER trigger_update_worker_duration BEFORE UPDATE ON workflows.worker_results FOR EACH ROW EXECUTE FUNCTION workflows.update_worker_duration();


--
-- Name: key_usage_log key_usage_log_key_id_fkey; Type: FK CONSTRAINT; Schema: config; Owner: claude
--

ALTER TABLE ONLY config.key_usage_log
    ADD CONSTRAINT key_usage_log_key_id_fkey FOREIGN KEY (key_id) REFERENCES config.api_keys(id) ON DELETE CASCADE;


--
-- Name: chunks chunks_document_id_fkey; Type: FK CONSTRAINT; Schema: documents; Owner: sfloess
--

ALTER TABLE ONLY documents.chunks
    ADD CONSTRAINT chunks_document_id_fkey FOREIGN KEY (document_id) REFERENCES documents.documents(id) ON DELETE CASCADE;


--
-- Name: processing_log processing_log_document_id_fkey; Type: FK CONSTRAINT; Schema: documents; Owner: sfloess
--

ALTER TABLE ONLY documents.processing_log
    ADD CONSTRAINT processing_log_document_id_fkey FOREIGN KEY (document_id) REFERENCES documents.documents(id) ON DELETE CASCADE;


--
-- Name: results results_benchmark_id_fkey; Type: FK CONSTRAINT; Schema: evaluation; Owner: sfloess
--

ALTER TABLE ONLY evaluation.results
    ADD CONSTRAINT results_benchmark_id_fkey FOREIGN KEY (benchmark_id) REFERENCES evaluation.benchmarks(id) ON DELETE CASCADE;


--
-- Name: runs runs_experiment_id_fkey; Type: FK CONSTRAINT; Schema: experiments; Owner: sfloess
--

ALTER TABLE ONLY experiments.runs
    ADD CONSTRAINT runs_experiment_id_fkey FOREIGN KEY (experiment_id) REFERENCES experiments.registry(id) ON DELETE CASCADE;


--
-- Name: embeddings embeddings_chunk_id_fkey; Type: FK CONSTRAINT; Schema: knowledge; Owner: sfloess
--

ALTER TABLE ONLY knowledge.embeddings
    ADD CONSTRAINT embeddings_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES knowledge.chunks(id) ON DELETE CASCADE;


--
-- Name: provenance provenance_entry_id_fkey; Type: FK CONSTRAINT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.provenance
    ADD CONSTRAINT provenance_entry_id_fkey FOREIGN KEY (entry_id) REFERENCES knowledge.entries(id) ON DELETE CASCADE;


--
-- Name: relationships relationships_source_id_fkey; Type: FK CONSTRAINT; Schema: knowledge; Owner: sfloess
--

ALTER TABLE ONLY knowledge.relationships
    ADD CONSTRAINT relationships_source_id_fkey FOREIGN KEY (source_id) REFERENCES knowledge.concepts(id) ON DELETE CASCADE;


--
-- Name: relationships relationships_target_id_fkey; Type: FK CONSTRAINT; Schema: knowledge; Owner: sfloess
--

ALTER TABLE ONLY knowledge.relationships
    ADD CONSTRAINT relationships_target_id_fkey FOREIGN KEY (target_id) REFERENCES knowledge.concepts(id) ON DELETE CASCADE;


--
-- Name: verification_votes verification_votes_discovery_id_fkey; Type: FK CONSTRAINT; Schema: knowledge; Owner: claude
--

ALTER TABLE ONLY knowledge.verification_votes
    ADD CONSTRAINT verification_votes_discovery_id_fkey FOREIGN KEY (discovery_id) REFERENCES knowledge.discoveries(id) ON DELETE CASCADE;


--
-- Name: relationships relationships_from_concept_id_fkey; Type: FK CONSTRAINT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.relationships
    ADD CONSTRAINT relationships_from_concept_id_fkey FOREIGN KEY (from_concept_id) REFERENCES learning.concepts(id);


--
-- Name: relationships relationships_to_concept_id_fkey; Type: FK CONSTRAINT; Schema: learning; Owner: postgres
--

ALTER TABLE ONLY learning.relationships
    ADD CONSTRAINT relationships_to_concept_id_fkey FOREIGN KEY (to_concept_id) REFERENCES learning.concepts(id);


--
-- Name: research_chunks research_chunks_parent_chunk_id_fkey; Type: FK CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.research_chunks
    ADD CONSTRAINT research_chunks_parent_chunk_id_fkey FOREIGN KEY (parent_chunk_id) REFERENCES learning.research_chunks(id);


--
-- Name: security_violations security_violations_policy_id_fkey; Type: FK CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.security_violations
    ADD CONSTRAINT security_violations_policy_id_fkey FOREIGN KEY (policy_id) REFERENCES learning.security_policies(policy_id);


--
-- Name: session_chunks session_chunks_parent_chunk_id_fkey; Type: FK CONSTRAINT; Schema: learning; Owner: claude
--

ALTER TABLE ONLY learning.session_chunks
    ADD CONSTRAINT session_chunks_parent_chunk_id_fkey FOREIGN KEY (parent_chunk_id) REFERENCES learning.session_chunks(id);


--
-- Name: api_usage api_usage_api_key_id_fkey; Type: FK CONSTRAINT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.api_usage
    ADD CONSTRAINT api_usage_api_key_id_fkey FOREIGN KEY (api_key_id) REFERENCES auth.api_keys(id);


--
-- Name: confidence_calibration confidence_calibration_worker_result_id_fkey; Type: FK CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.confidence_calibration
    ADD CONSTRAINT confidence_calibration_worker_result_id_fkey FOREIGN KEY (worker_result_id) REFERENCES workflow.worker_results(id);


--
-- Name: human_corrections human_corrections_worker_result_id_fkey; Type: FK CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.human_corrections
    ADD CONSTRAINT human_corrections_worker_result_id_fkey FOREIGN KEY (worker_result_id) REFERENCES workflow.worker_results(id);


--
-- Name: human_corrections human_corrections_workflow_execution_id_fkey; Type: FK CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.human_corrections
    ADD CONSTRAINT human_corrections_workflow_execution_id_fkey FOREIGN KEY (workflow_execution_id) REFERENCES workflow.executions(id);


--
-- Name: rate_limit_state rate_limit_state_api_key_id_fkey; Type: FK CONSTRAINT; Schema: monitoring; Owner: sfloess
--

ALTER TABLE ONLY monitoring.rate_limit_state
    ADD CONSTRAINT rate_limit_state_api_key_id_fkey FOREIGN KEY (api_key_id) REFERENCES auth.api_keys(id);


--
-- Name: task_attribution task_attribution_worker_result_id_fkey; Type: FK CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.task_attribution
    ADD CONSTRAINT task_attribution_worker_result_id_fkey FOREIGN KEY (worker_result_id) REFERENCES workflow.worker_results(id);


--
-- Name: task_attribution task_attribution_workflow_execution_id_fkey; Type: FK CONSTRAINT; Schema: monitoring; Owner: claude
--

ALTER TABLE ONLY monitoring.task_attribution
    ADD CONSTRAINT task_attribution_workflow_execution_id_fkey FOREIGN KEY (workflow_execution_id) REFERENCES workflow.executions(id);


--
-- Name: task_dependencies task_dependencies_from_task_id_fkey; Type: FK CONSTRAINT; Schema: orchestration; Owner: sfloess
--

ALTER TABLE ONLY orchestration.task_dependencies
    ADD CONSTRAINT task_dependencies_from_task_id_fkey FOREIGN KEY (from_task_id) REFERENCES orchestration.task_queue(task_id);


--
-- Name: task_dependencies task_dependencies_to_task_id_fkey; Type: FK CONSTRAINT; Schema: orchestration; Owner: sfloess
--

ALTER TABLE ONLY orchestration.task_dependencies
    ADD CONSTRAINT task_dependencies_to_task_id_fkey FOREIGN KEY (to_task_id) REFERENCES orchestration.task_queue(task_id);


--
-- Name: task_progress_log task_progress_log_task_id_fkey; Type: FK CONSTRAINT; Schema: orchestration; Owner: sfloess
--

ALTER TABLE ONLY orchestration.task_progress_log
    ADD CONSTRAINT task_progress_log_task_id_fkey FOREIGN KEY (task_id) REFERENCES orchestration.task_queue(task_id);


--
-- Name: worker_heartbeats worker_heartbeats_current_task_id_fkey; Type: FK CONSTRAINT; Schema: orchestration; Owner: sfloess
--

ALTER TABLE ONLY orchestration.worker_heartbeats
    ADD CONSTRAINT worker_heartbeats_current_task_id_fkey FOREIGN KEY (current_task_id) REFERENCES orchestration.task_queue(task_id);


--
-- Name: file_locks file_locks_locked_by_fkey; Type: FK CONSTRAINT; Schema: orchestrator; Owner: sfloess
--

ALTER TABLE ONLY orchestrator.file_locks
    ADD CONSTRAINT file_locks_locked_by_fkey FOREIGN KEY (locked_by) REFERENCES orchestrator.sessions(session_id) ON DELETE CASCADE;


--
-- Name: work_queue work_queue_assigned_to_fkey; Type: FK CONSTRAINT; Schema: orchestrator; Owner: sfloess
--

ALTER TABLE ONLY orchestrator.work_queue
    ADD CONSTRAINT work_queue_assigned_to_fkey FOREIGN KEY (assigned_to) REFERENCES orchestrator.sessions(session_id) ON DELETE SET NULL;


--
-- Name: work_queue work_queue_session_id_fkey; Type: FK CONSTRAINT; Schema: orchestrator; Owner: sfloess
--

ALTER TABLE ONLY orchestrator.work_queue
    ADD CONSTRAINT work_queue_session_id_fkey FOREIGN KEY (session_id) REFERENCES orchestrator.sessions(session_id) ON DELETE SET NULL;


--
-- Name: chunks chunks_source_file_id_fkey; Type: FK CONSTRAINT; Schema: processing; Owner: sfloess
--

ALTER TABLE ONLY processing.chunks
    ADD CONSTRAINT chunks_source_file_id_fkey FOREIGN KEY (source_file_id) REFERENCES processing.source_files(id) ON DELETE RESTRICT;


--
-- Name: work_queue work_queue_chunk_id_fkey; Type: FK CONSTRAINT; Schema: processing; Owner: sfloess
--

ALTER TABLE ONLY processing.work_queue
    ADD CONSTRAINT work_queue_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES processing.chunks(id) ON DELETE RESTRICT;


--
-- Name: work_queue work_queue_source_file_id_fkey; Type: FK CONSTRAINT; Schema: processing; Owner: sfloess
--

ALTER TABLE ONLY processing.work_queue
    ADD CONSTRAINT work_queue_source_file_id_fkey FOREIGN KEY (source_file_id) REFERENCES processing.source_files(id) ON DELETE RESTRICT;


--
-- Name: workers workers_current_task_id_fkey; Type: FK CONSTRAINT; Schema: processing; Owner: sfloess
--

ALTER TABLE ONLY processing.workers
    ADD CONSTRAINT workers_current_task_id_fkey FOREIGN KEY (current_task_id) REFERENCES processing.work_queue(id);


--
-- Name: explanations explanations_evidence_id_fkey; Type: FK CONSTRAINT; Schema: reasoning; Owner: claude
--

ALTER TABLE ONLY reasoning.explanations
    ADD CONSTRAINT explanations_evidence_id_fkey FOREIGN KEY (evidence_id) REFERENCES reasoning.evidence(id);


--
-- Name: explanations explanations_hypothesis_id_fkey; Type: FK CONSTRAINT; Schema: reasoning; Owner: claude
--

ALTER TABLE ONLY reasoning.explanations
    ADD CONSTRAINT explanations_hypothesis_id_fkey FOREIGN KEY (hypothesis_id) REFERENCES reasoning.hypotheses(id);


--
-- Name: arbiter_decisions arbiter_decisions_workflow_execution_id_fkey; Type: FK CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.arbiter_decisions
    ADD CONSTRAINT arbiter_decisions_workflow_execution_id_fkey FOREIGN KEY (workflow_execution_id) REFERENCES workflow.executions(id) ON DELETE CASCADE;


--
-- Name: feedback feedback_workflow_execution_id_fkey; Type: FK CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.feedback
    ADD CONSTRAINT feedback_workflow_execution_id_fkey FOREIGN KEY (workflow_execution_id) REFERENCES workflow.executions(id) ON DELETE CASCADE;


--
-- Name: learnings learnings_workflow_execution_id_fkey; Type: FK CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.learnings
    ADD CONSTRAINT learnings_workflow_execution_id_fkey FOREIGN KEY (workflow_execution_id) REFERENCES workflow.executions(id) ON DELETE CASCADE;


--
-- Name: phases phases_workflow_execution_id_fkey; Type: FK CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.phases
    ADD CONSTRAINT phases_workflow_execution_id_fkey FOREIGN KEY (workflow_execution_id) REFERENCES workflow.executions(id) ON DELETE CASCADE;


--
-- Name: worker_results worker_results_workflow_execution_id_fkey; Type: FK CONSTRAINT; Schema: workflow; Owner: sfloess
--

ALTER TABLE ONLY workflow.worker_results
    ADD CONSTRAINT worker_results_workflow_execution_id_fkey FOREIGN KEY (workflow_execution_id) REFERENCES workflow.executions(id) ON DELETE CASCADE;


--
-- Name: arbiter_decisions arbiter_decisions_execution_id_fkey; Type: FK CONSTRAINT; Schema: workflows; Owner: sfloess
--

ALTER TABLE ONLY workflows.arbiter_decisions
    ADD CONSTRAINT arbiter_decisions_execution_id_fkey FOREIGN KEY (execution_id) REFERENCES workflows.executions(execution_id) ON DELETE CASCADE;


--
-- Name: execution_embeddings execution_embeddings_execution_id_fkey; Type: FK CONSTRAINT; Schema: workflows; Owner: sfloess
--

ALTER TABLE ONLY workflows.execution_embeddings
    ADD CONSTRAINT execution_embeddings_execution_id_fkey FOREIGN KEY (execution_id) REFERENCES workflows.executions(execution_id) ON DELETE CASCADE;


--
-- Name: execution_phases execution_phases_execution_id_fkey; Type: FK CONSTRAINT; Schema: workflows; Owner: sfloess
--

ALTER TABLE ONLY workflows.execution_phases
    ADD CONSTRAINT execution_phases_execution_id_fkey FOREIGN KEY (execution_id) REFERENCES workflows.executions(execution_id) ON DELETE CASCADE;


--
-- Name: feedback feedback_execution_id_fkey; Type: FK CONSTRAINT; Schema: workflows; Owner: sfloess
--

ALTER TABLE ONLY workflows.feedback
    ADD CONSTRAINT feedback_execution_id_fkey FOREIGN KEY (execution_id) REFERENCES workflows.executions(execution_id) ON DELETE CASCADE;


--
-- Name: learnings learnings_execution_id_fkey; Type: FK CONSTRAINT; Schema: workflows; Owner: sfloess
--

ALTER TABLE ONLY workflows.learnings
    ADD CONSTRAINT learnings_execution_id_fkey FOREIGN KEY (execution_id) REFERENCES workflows.executions(execution_id) ON DELETE CASCADE;


--
-- Name: worker_results worker_results_execution_id_fkey; Type: FK CONSTRAINT; Schema: workflows; Owner: sfloess
--

ALTER TABLE ONLY workflows.worker_results
    ADD CONSTRAINT worker_results_execution_id_fkey FOREIGN KEY (execution_id) REFERENCES workflows.executions(execution_id) ON DELETE CASCADE;


--
-- Name: learning_pub; Type: PUBLICATION; Schema: -; Owner: postgres
--

CREATE PUBLICATION learning_pub WITH (publish = 'insert, update, delete, truncate');


ALTER PUBLICATION learning_pub OWNER TO postgres;

--
-- Name: learning_pub entries; Type: PUBLICATION TABLE; Schema: costs; Owner: postgres
--

ALTER PUBLICATION learning_pub ADD TABLE ONLY costs.entries;


--
-- Name: learning_pub consciousness_research; Type: PUBLICATION TABLE; Schema: learning; Owner: postgres
--

ALTER PUBLICATION learning_pub ADD TABLE ONLY learning.consciousness_research;


--
-- Name: learning_pub experiences; Type: PUBLICATION TABLE; Schema: learning; Owner: postgres
--

ALTER PUBLICATION learning_pub ADD TABLE ONLY learning.experiences;


--
-- Name: learning_pub research_chunks; Type: PUBLICATION TABLE; Schema: learning; Owner: postgres
--

ALTER PUBLICATION learning_pub ADD TABLE ONLY learning.research_chunks;


--
-- Name: learning_pub research_documents; Type: PUBLICATION TABLE; Schema: learning; Owner: postgres
--

ALTER PUBLICATION learning_pub ADD TABLE ONLY learning.research_documents;


--
-- Name: learning_pub strategy_performance; Type: PUBLICATION TABLE; Schema: learning; Owner: postgres
--

ALTER PUBLICATION learning_pub ADD TABLE ONLY learning.strategy_performance;


--
-- Name: learning_pub execution_summary; Type: PUBLICATION TABLE; Schema: monitoring; Owner: postgres
--

ALTER PUBLICATION learning_pub ADD TABLE ONLY monitoring.execution_summary;


--
-- Name: learning_pub model_selections; Type: PUBLICATION TABLE; Schema: monitoring; Owner: postgres
--

ALTER PUBLICATION learning_pub ADD TABLE ONLY monitoring.model_selections;


--
-- Name: SCHEMA auth; Type: ACL; Schema: -; Owner: sfloess
--

GRANT USAGE ON SCHEMA auth TO claude;


--
-- Name: SCHEMA auto_storage; Type: ACL; Schema: -; Owner: claude
--

GRANT ALL ON SCHEMA auto_storage TO sfloess;


--
-- Name: SCHEMA costs; Type: ACL; Schema: -; Owner: sfloess
--

GRANT ALL ON SCHEMA costs TO claude;


--
-- Name: SCHEMA documents; Type: ACL; Schema: -; Owner: sfloess
--

GRANT USAGE ON SCHEMA documents TO claude;


--
-- Name: SCHEMA evaluation; Type: ACL; Schema: -; Owner: postgres
--

GRANT USAGE ON SCHEMA evaluation TO PUBLIC;


--
-- Name: SCHEMA knowledge; Type: ACL; Schema: -; Owner: sfloess
--

GRANT ALL ON SCHEMA knowledge TO claude;


--
-- Name: SCHEMA learning; Type: ACL; Schema: -; Owner: sfloess
--

GRANT ALL ON SCHEMA learning TO claude;


--
-- Name: SCHEMA monitoring; Type: ACL; Schema: -; Owner: sfloess
--

GRANT ALL ON SCHEMA monitoring TO claude;


--
-- Name: SCHEMA search; Type: ACL; Schema: -; Owner: postgres
--

GRANT USAGE ON SCHEMA search TO claude;


--
-- Name: SCHEMA workflow; Type: ACL; Schema: -; Owner: sfloess
--

GRANT ALL ON SCHEMA workflow TO claude;


--
-- Name: TABLE config; Type: ACL; Schema: admin; Owner: sfloess
--

GRANT SELECT ON TABLE admin.config TO claude;


--
-- Name: TABLE secrets; Type: ACL; Schema: auth; Owner: sfloess
--

GRANT SELECT ON TABLE auth.secrets TO claude;


--
-- Name: TABLE api_calls; Type: ACL; Schema: auto_storage; Owner: claude
--

GRANT ALL ON TABLE auto_storage.api_calls TO sfloess;


--
-- Name: SEQUENCE api_calls_id_seq; Type: ACL; Schema: auto_storage; Owner: claude
--

GRANT ALL ON SEQUENCE auto_storage.api_calls_id_seq TO sfloess;


--
-- Name: TABLE entries; Type: ACL; Schema: costs; Owner: sfloess
--

GRANT ALL ON TABLE costs.entries TO claude;


--
-- Name: SEQUENCE entries_id_seq; Type: ACL; Schema: costs; Owner: sfloess
--

GRANT ALL ON SEQUENCE costs.entries_id_seq TO claude;


--
-- Name: TABLE chunks; Type: ACL; Schema: documents; Owner: sfloess
--

GRANT SELECT,INSERT,UPDATE ON TABLE documents.chunks TO claude;


--
-- Name: TABLE documents; Type: ACL; Schema: documents; Owner: sfloess
--

GRANT SELECT,INSERT,UPDATE ON TABLE documents.documents TO claude;


--
-- Name: TABLE processing_log; Type: ACL; Schema: documents; Owner: sfloess
--

GRANT SELECT,INSERT,UPDATE ON TABLE documents.processing_log TO claude;


--
-- Name: TABLE benchmarks; Type: ACL; Schema: evaluation; Owner: sfloess
--

GRANT SELECT ON TABLE evaluation.benchmarks TO PUBLIC;


--
-- Name: TABLE results; Type: ACL; Schema: evaluation; Owner: sfloess
--

GRANT SELECT ON TABLE evaluation.results TO PUBLIC;


--
-- Name: TABLE model_performance; Type: ACL; Schema: evaluation; Owner: sfloess
--

GRANT SELECT ON TABLE evaluation.model_performance TO PUBLIC;


--
-- Name: TABLE task_model_performance; Type: ACL; Schema: evaluation; Owner: sfloess
--

GRANT SELECT ON TABLE evaluation.task_model_performance TO PUBLIC;


--
-- Name: TABLE chunks; Type: ACL; Schema: knowledge; Owner: sfloess
--

GRANT ALL ON TABLE knowledge.chunks TO claude;


--
-- Name: SEQUENCE chunks_id_seq; Type: ACL; Schema: knowledge; Owner: sfloess
--

GRANT ALL ON SEQUENCE knowledge.chunks_id_seq TO claude;


--
-- Name: TABLE concepts; Type: ACL; Schema: knowledge; Owner: sfloess
--

GRANT ALL ON TABLE knowledge.concepts TO claude;


--
-- Name: TABLE embeddings; Type: ACL; Schema: knowledge; Owner: sfloess
--

GRANT ALL ON TABLE knowledge.embeddings TO claude;


--
-- Name: SEQUENCE embeddings_id_seq; Type: ACL; Schema: knowledge; Owner: sfloess
--

GRANT ALL ON SEQUENCE knowledge.embeddings_id_seq TO claude;


--
-- Name: TABLE relationships; Type: ACL; Schema: knowledge; Owner: sfloess
--

GRANT ALL ON TABLE knowledge.relationships TO claude;


--
-- Name: TABLE research_findings; Type: ACL; Schema: knowledge; Owner: sfloess
--

GRANT ALL ON TABLE knowledge.research_findings TO claude;


--
-- Name: SEQUENCE research_findings_id_seq; Type: ACL; Schema: knowledge; Owner: sfloess
--

GRANT ALL ON SEQUENCE knowledge.research_findings_id_seq TO claude;


--
-- Name: TABLE web_articles; Type: ACL; Schema: knowledge; Owner: sfloess
--

GRANT ALL ON TABLE knowledge.web_articles TO claude;


--
-- Name: SEQUENCE web_articles_id_seq; Type: ACL; Schema: knowledge; Owner: sfloess
--

GRANT ALL ON SEQUENCE knowledge.web_articles_id_seq TO claude;


--
-- Name: TABLE analogical_patterns; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON TABLE learning.analogical_patterns TO claude;


--
-- Name: TABLE api_models; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON TABLE learning.api_models TO claude;


--
-- Name: SEQUENCE api_models_id_seq; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON SEQUENCE learning.api_models_id_seq TO claude;


--
-- Name: TABLE best_models_by_task; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON TABLE learning.best_models_by_task TO claude;


--
-- Name: TABLE confidence_observations; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON TABLE learning.confidence_observations TO claude;


--
-- Name: SEQUENCE confidence_observations_id_seq; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON SEQUENCE learning.confidence_observations_id_seq TO claude;


--
-- Name: TABLE conversation_learnings; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON TABLE learning.conversation_learnings TO claude;


--
-- Name: TABLE diversity_current; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON TABLE learning.diversity_current TO claude;


--
-- Name: TABLE error_logs; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON TABLE learning.error_logs TO claude;


--
-- Name: TABLE git_commits; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON TABLE learning.git_commits TO claude;


--
-- Name: TABLE gitlab_issues; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON TABLE learning.gitlab_issues TO claude;


--
-- Name: TABLE memories; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON TABLE learning.memories TO claude;


--
-- Name: TABLE memory; Type: ACL; Schema: learning; Owner: postgres
--

GRANT ALL ON TABLE learning.memory TO claude;


--
-- Name: SEQUENCE memory_id_seq; Type: ACL; Schema: learning; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE learning.memory_id_seq TO claude;


--
-- Name: TABLE model_censorship; Type: ACL; Schema: learning; Owner: claude
--

GRANT SELECT ON TABLE learning.model_censorship TO PUBLIC;


--
-- Name: TABLE model_censorship_summary; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT SELECT ON TABLE learning.model_censorship_summary TO PUBLIC;
GRANT ALL ON TABLE learning.model_censorship_summary TO claude;


--
-- Name: TABLE pdf_knowledge; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON TABLE learning.pdf_knowledge TO claude;


--
-- Name: SEQUENCE pdf_knowledge_id_seq; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON SEQUENCE learning.pdf_knowledge_id_seq TO claude;


--
-- Name: TABLE preference_learner_stats; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON TABLE learning.preference_learner_stats TO claude;


--
-- Name: TABLE chunk; Type: ACL; Schema: queue; Owner: postgres
--

GRANT ALL ON TABLE queue.chunk TO claude;


--
-- Name: TABLE embed; Type: ACL; Schema: queue; Owner: postgres
--

GRANT ALL ON TABLE queue.embed TO claude;


--
-- Name: TABLE graph; Type: ACL; Schema: queue; Owner: postgres
--

GRANT ALL ON TABLE queue.graph TO claude;


--
-- Name: TABLE store; Type: ACL; Schema: queue; Owner: postgres
--

GRANT ALL ON TABLE queue.store TO claude;


--
-- Name: TABLE reasoning_patterns; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON TABLE learning.reasoning_patterns TO claude;


--
-- Name: SEQUENCE reasoning_patterns_id_seq; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON SEQUENCE learning.reasoning_patterns_id_seq TO claude;


--
-- Name: TABLE service_mesh_models; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON TABLE learning.service_mesh_models TO claude;


--
-- Name: TABLE specialist_models; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON TABLE learning.specialist_models TO claude;


--
-- Name: TABLE strategy_performance_multi; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON TABLE learning.strategy_performance_multi TO claude;


--
-- Name: SEQUENCE strategy_performance_multi_id_seq; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON SEQUENCE learning.strategy_performance_multi_id_seq TO claude;


--
-- Name: TABLE test_results; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON TABLE learning.test_results TO claude;


--
-- Name: TABLE uncensored_models; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT SELECT ON TABLE learning.uncensored_models TO PUBLIC;
GRANT ALL ON TABLE learning.uncensored_models TO claude;


--
-- Name: TABLE vec_scale_test_1783055901; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON TABLE learning.vec_scale_test_1783055901 TO claude;


--
-- Name: TABLE vec_scale_test_1783055962; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON TABLE learning.vec_scale_test_1783055962 TO claude;


--
-- Name: TABLE vec_scale_test_1783055991; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON TABLE learning.vec_scale_test_1783055991 TO claude;


--
-- Name: TABLE vec_scale_test_1783056573; Type: ACL; Schema: learning; Owner: sfloess
--

GRANT ALL ON TABLE learning.vec_scale_test_1783056573 TO claude;


--
-- Name: TABLE api_health_checks; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON TABLE monitoring.api_health_checks TO claude;


--
-- Name: SEQUENCE api_health_checks_id_seq; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON SEQUENCE monitoring.api_health_checks_id_seq TO claude;


--
-- Name: TABLE api_health_status; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON TABLE monitoring.api_health_status TO claude;


--
-- Name: TABLE api_usage; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON TABLE monitoring.api_usage TO claude;


--
-- Name: SEQUENCE api_usage_id_seq; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON SEQUENCE monitoring.api_usage_id_seq TO claude;


--
-- Name: TABLE circuit_breaker_events; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON TABLE monitoring.circuit_breaker_events TO claude;


--
-- Name: SEQUENCE circuit_breaker_events_id_seq; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON SEQUENCE monitoring.circuit_breaker_events_id_seq TO claude;


--
-- Name: TABLE diversity_alerts; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON TABLE monitoring.diversity_alerts TO claude;


--
-- Name: SEQUENCE diversity_alerts_id_seq; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON SEQUENCE monitoring.diversity_alerts_id_seq TO claude;


--
-- Name: TABLE document_stats; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON TABLE monitoring.document_stats TO claude;


--
-- Name: TABLE execution_log; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON TABLE monitoring.execution_log TO claude;


--
-- Name: SEQUENCE execution_log_id_seq; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON SEQUENCE monitoring.execution_log_id_seq TO claude;


--
-- Name: TABLE execution_summary; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON TABLE monitoring.execution_summary TO claude;


--
-- Name: SEQUENCE execution_summary_id_seq; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON SEQUENCE monitoring.execution_summary_id_seq TO claude;


--
-- Name: TABLE fleet_health; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON TABLE monitoring.fleet_health TO claude;


--
-- Name: SEQUENCE fleet_health_id_seq; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON SEQUENCE monitoring.fleet_health_id_seq TO claude;


--
-- Name: TABLE health_checks; Type: ACL; Schema: monitoring; Owner: claude
--

GRANT SELECT,INSERT ON TABLE monitoring.health_checks TO sfloess;


--
-- Name: SEQUENCE health_checks_id_seq; Type: ACL; Schema: monitoring; Owner: claude
--

GRANT USAGE ON SEQUENCE monitoring.health_checks_id_seq TO sfloess;


--
-- Name: TABLE model_capabilities; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON TABLE monitoring.model_capabilities TO claude;


--
-- Name: SEQUENCE model_capabilities_id_seq; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON SEQUENCE monitoring.model_capabilities_id_seq TO claude;


--
-- Name: TABLE model_capabilities_top; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON TABLE monitoring.model_capabilities_top TO claude;


--
-- Name: TABLE model_capabilities_with_confidence; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON TABLE monitoring.model_capabilities_with_confidence TO claude;


--
-- Name: TABLE model_retraining; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON TABLE monitoring.model_retraining TO claude;


--
-- Name: SEQUENCE model_retraining_id_seq; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON SEQUENCE monitoring.model_retraining_id_seq TO claude;


--
-- Name: TABLE model_selections; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON TABLE monitoring.model_selections TO claude;


--
-- Name: SEQUENCE model_selections_id_seq; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON SEQUENCE monitoring.model_selections_id_seq TO claude;


--
-- Name: TABLE model_tuning; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON TABLE monitoring.model_tuning TO claude;


--
-- Name: SEQUENCE model_tuning_id_seq; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON SEQUENCE monitoring.model_tuning_id_seq TO claude;


--
-- Name: TABLE network_measurements; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON TABLE monitoring.network_measurements TO claude;


--
-- Name: SEQUENCE network_measurements_id_seq; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON SEQUENCE monitoring.network_measurements_id_seq TO claude;


--
-- Name: TABLE network_predictions; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON TABLE monitoring.network_predictions TO claude;


--
-- Name: SEQUENCE network_predictions_id_seq; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON SEQUENCE monitoring.network_predictions_id_seq TO claude;


--
-- Name: TABLE prediction_accuracy; Type: ACL; Schema: monitoring; Owner: postgres
--

GRANT SELECT ON TABLE monitoring.prediction_accuracy TO claude;


--
-- Name: TABLE prediction_accuracy_by_model; Type: ACL; Schema: monitoring; Owner: postgres
--

GRANT SELECT ON TABLE monitoring.prediction_accuracy_by_model TO claude;


--
-- Name: TABLE prediction_health_summary; Type: ACL; Schema: monitoring; Owner: postgres
--

GRANT SELECT ON TABLE monitoring.prediction_health_summary TO claude;


--
-- Name: TABLE prediction_trends_hourly; Type: ACL; Schema: monitoring; Owner: postgres
--

GRANT SELECT ON TABLE monitoring.prediction_trends_hourly TO claude;


--
-- Name: TABLE rate_limit_requests; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON TABLE monitoring.rate_limit_requests TO claude;


--
-- Name: SEQUENCE rate_limit_requests_id_seq; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON SEQUENCE monitoring.rate_limit_requests_id_seq TO claude;


--
-- Name: TABLE rate_limit_state; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON TABLE monitoring.rate_limit_state TO claude;


--
-- Name: TABLE rate_limits; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON TABLE monitoring.rate_limits TO claude;


--
-- Name: TABLE resource_usage; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON TABLE monitoring.resource_usage TO claude;


--
-- Name: SEQUENCE resource_usage_id_seq; Type: ACL; Schema: monitoring; Owner: sfloess
--

GRANT ALL ON SEQUENCE monitoring.resource_usage_id_seq TO claude;


--
-- Name: TABLE session_learnings; Type: ACL; Schema: monitoring; Owner: claude
--

GRANT SELECT,INSERT ON TABLE monitoring.session_learnings TO sfloess;


--
-- Name: SEQUENCE session_learnings_id_seq; Type: ACL; Schema: monitoring; Owner: claude
--

GRANT USAGE ON SEQUENCE monitoring.session_learnings_id_seq TO sfloess;


--
-- Name: TABLE chunks; Type: ACL; Schema: processing; Owner: sfloess
--

GRANT ALL ON TABLE processing.chunks TO claude;


--
-- Name: SEQUENCE chunks_id_seq; Type: ACL; Schema: processing; Owner: sfloess
--

GRANT ALL ON SEQUENCE processing.chunks_id_seq TO claude;


--
-- Name: TABLE source_files; Type: ACL; Schema: processing; Owner: sfloess
--

GRANT ALL ON TABLE processing.source_files TO claude;


--
-- Name: TABLE pipeline_summary; Type: ACL; Schema: processing; Owner: sfloess
--

GRANT ALL ON TABLE processing.pipeline_summary TO claude;


--
-- Name: TABLE processing_stats; Type: ACL; Schema: processing; Owner: sfloess
--

GRANT ALL ON TABLE processing.processing_stats TO claude;


--
-- Name: SEQUENCE processing_stats_id_seq; Type: ACL; Schema: processing; Owner: sfloess
--

GRANT ALL ON SEQUENCE processing.processing_stats_id_seq TO claude;


--
-- Name: TABLE work_queue; Type: ACL; Schema: processing; Owner: sfloess
--

GRANT ALL ON TABLE processing.work_queue TO claude;


--
-- Name: TABLE queue_summary; Type: ACL; Schema: processing; Owner: sfloess
--

GRANT ALL ON TABLE processing.queue_summary TO claude;


--
-- Name: SEQUENCE source_files_id_seq; Type: ACL; Schema: processing; Owner: sfloess
--

GRANT ALL ON SEQUENCE processing.source_files_id_seq TO claude;


--
-- Name: SEQUENCE work_queue_id_seq; Type: ACL; Schema: processing; Owner: sfloess
--

GRANT ALL ON SEQUENCE processing.work_queue_id_seq TO claude;


--
-- Name: TABLE workers; Type: ACL; Schema: processing; Owner: sfloess
--

GRANT ALL ON TABLE processing.workers TO claude;


--
-- Name: TABLE api_cache; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.api_cache TO claude;
GRANT ALL ON TABLE public.api_cache TO sfloess;


--
-- Name: TABLE api_embedding_usage; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.api_embedding_usage TO claude;
GRANT ALL ON TABLE public.api_embedding_usage TO sfloess;


--
-- Name: SEQUENCE api_embedding_usage_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.api_embedding_usage_id_seq TO claude;


--
-- Name: TABLE api_failures; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.api_failures TO claude;
GRANT ALL ON TABLE public.api_failures TO sfloess;


--
-- Name: SEQUENCE api_failures_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.api_failures_id_seq TO claude;


--
-- Name: TABLE api_models; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.api_models TO claude;
GRANT ALL ON TABLE public.api_models TO sfloess;


--
-- Name: SEQUENCE api_models_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.api_models_id_seq TO claude;


--
-- Name: TABLE api_usage; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.api_usage TO claude;
GRANT ALL ON TABLE public.api_usage TO sfloess;


--
-- Name: SEQUENCE api_usage_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.api_usage_id_seq TO claude;


--
-- Name: TABLE session_context; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.session_context TO PUBLIC;


--
-- Name: SEQUENCE chunk_id_seq; Type: ACL; Schema: queue; Owner: postgres
--

GRANT ALL ON SEQUENCE queue.chunk_id_seq TO claude;


--
-- Name: SEQUENCE embed_id_seq; Type: ACL; Schema: queue; Owner: postgres
--

GRANT ALL ON SEQUENCE queue.embed_id_seq TO claude;


--
-- Name: SEQUENCE graph_id_seq; Type: ACL; Schema: queue; Owner: postgres
--

GRANT ALL ON SEQUENCE queue.graph_id_seq TO claude;


--
-- Name: SEQUENCE store_id_seq; Type: ACL; Schema: queue; Owner: postgres
--

GRANT ALL ON SEQUENCE queue.store_id_seq TO claude;


--
-- Name: TABLE worker_heartbeat; Type: ACL; Schema: queue; Owner: sfloess
--

GRANT ALL ON TABLE queue.worker_heartbeat TO claude;


--
-- Name: TABLE knowledge_base; Type: ACL; Schema: search; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE search.knowledge_base TO claude;


--
-- Name: SEQUENCE knowledge_base_id_seq; Type: ACL; Schema: search; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE search.knowledge_base_id_seq TO claude;


--
-- Name: TABLE arbiter_decisions; Type: ACL; Schema: workflow; Owner: sfloess
--

GRANT ALL ON TABLE workflow.arbiter_decisions TO claude;


--
-- Name: SEQUENCE arbiter_decisions_id_seq; Type: ACL; Schema: workflow; Owner: sfloess
--

GRANT ALL ON SEQUENCE workflow.arbiter_decisions_id_seq TO claude;


--
-- Name: TABLE executions; Type: ACL; Schema: workflow; Owner: sfloess
--

GRANT ALL ON TABLE workflow.executions TO claude;


--
-- Name: SEQUENCE executions_id_seq; Type: ACL; Schema: workflow; Owner: sfloess
--

GRANT ALL ON SEQUENCE workflow.executions_id_seq TO claude;


--
-- Name: TABLE feedback; Type: ACL; Schema: workflow; Owner: sfloess
--

GRANT ALL ON TABLE workflow.feedback TO claude;


--
-- Name: SEQUENCE feedback_id_seq; Type: ACL; Schema: workflow; Owner: sfloess
--

GRANT ALL ON SEQUENCE workflow.feedback_id_seq TO claude;


--
-- Name: TABLE worker_results; Type: ACL; Schema: workflow; Owner: sfloess
--

GRANT ALL ON TABLE workflow.worker_results TO claude;


--
-- Name: TABLE hourly_performance; Type: ACL; Schema: workflow; Owner: postgres
--

GRANT ALL ON TABLE workflow.hourly_performance TO claude;


--
-- Name: TABLE learnings; Type: ACL; Schema: workflow; Owner: sfloess
--

GRANT ALL ON TABLE workflow.learnings TO claude;


--
-- Name: SEQUENCE learnings_id_seq; Type: ACL; Schema: workflow; Owner: sfloess
--

GRANT ALL ON SEQUENCE workflow.learnings_id_seq TO claude;


--
-- Name: TABLE phases; Type: ACL; Schema: workflow; Owner: sfloess
--

GRANT ALL ON TABLE workflow.phases TO claude;


--
-- Name: SEQUENCE phases_id_seq; Type: ACL; Schema: workflow; Owner: sfloess
--

GRANT ALL ON SEQUENCE workflow.phases_id_seq TO claude;


--
-- Name: TABLE response_cache; Type: ACL; Schema: workflow; Owner: postgres
--

GRANT ALL ON TABLE workflow.response_cache TO claude;


--
-- Name: SEQUENCE worker_results_id_seq; Type: ACL; Schema: workflow; Owner: sfloess
--

GRANT ALL ON SEQUENCE workflow.worker_results_id_seq TO claude;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: costs; Owner: sfloess
--

ALTER DEFAULT PRIVILEGES FOR ROLE sfloess IN SCHEMA costs GRANT ALL ON SEQUENCES TO claude;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: costs; Owner: sfloess
--

ALTER DEFAULT PRIVILEGES FOR ROLE sfloess IN SCHEMA costs GRANT ALL ON TABLES TO claude;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: knowledge; Owner: sfloess
--

ALTER DEFAULT PRIVILEGES FOR ROLE sfloess IN SCHEMA knowledge GRANT ALL ON SEQUENCES TO claude;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: knowledge; Owner: sfloess
--

ALTER DEFAULT PRIVILEGES FOR ROLE sfloess IN SCHEMA knowledge GRANT ALL ON TABLES TO claude;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: learning; Owner: sfloess
--

ALTER DEFAULT PRIVILEGES FOR ROLE sfloess IN SCHEMA learning GRANT ALL ON SEQUENCES TO claude;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: learning; Owner: sfloess
--

ALTER DEFAULT PRIVILEGES FOR ROLE sfloess IN SCHEMA learning GRANT ALL ON TABLES TO claude;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: monitoring; Owner: sfloess
--

ALTER DEFAULT PRIVILEGES FOR ROLE sfloess IN SCHEMA monitoring GRANT ALL ON SEQUENCES TO claude;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: monitoring; Owner: sfloess
--

ALTER DEFAULT PRIVILEGES FOR ROLE sfloess IN SCHEMA monitoring GRANT ALL ON TABLES TO claude;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: processing; Owner: sfloess
--

ALTER DEFAULT PRIVILEGES FOR ROLE sfloess IN SCHEMA processing GRANT ALL ON SEQUENCES TO claude;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: processing; Owner: sfloess
--

ALTER DEFAULT PRIVILEGES FOR ROLE sfloess IN SCHEMA processing GRANT ALL ON TABLES TO claude;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: queue; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA queue GRANT ALL ON SEQUENCES TO claude;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: queue; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA queue GRANT ALL ON TABLES TO claude;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: search; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA search GRANT SELECT,USAGE ON SEQUENCES TO claude;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: search; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA search GRANT SELECT,INSERT,DELETE,UPDATE ON TABLES TO claude;


--
-- PostgreSQL database dump complete
--

\unrestrict loX8UIKKQU7dMak5804wozJnglwlJGjhNleUqat3bVWUCtA4J4J9hud5vRt61Dm

