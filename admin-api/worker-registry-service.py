#!/usr/bin/env python3
"""
Worker Registry Service
Runs on aio-01:8002 - workers register themselves via HTTP POST
Maintains dynamic fleet topology in PostgreSQL
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
import psycopg2
import os

app = FastAPI(title="Worker Registry", version="1.0.0")

DB_CONFIG = {
    'host': os.getenv('PGHOST', 'aio-01'),
    'port': int(os.getenv('PGPORT', '5433')),
    'database': os.getenv('PGDATABASE', 'learning'),
    'user': os.getenv('PGUSER', 'claude')
}

class WorkerRegistration(BaseModel):
    hostname: str
    ip_address: str
    cpu_cores: int
    ram_gb: float
    architecture: str
    roles: list[str] = ['worker']
    capabilities: list[str] = []

class WorkerFailure(BaseModel):
    hostname: str
    error_message: str
    reported_by: str = 'orchestrator'

def get_db():
    return psycopg2.connect(**DB_CONFIG)

@app.post("/register")
async def register_worker(worker: WorkerRegistration):
    """Register or update a worker node"""
    conn = get_db()
    try:
        cur = conn.cursor()

        # Upsert worker registration
        cur.execute("""
            INSERT INTO fleet.workers
            (hostname, ip_address, cpu_cores, ram_gb, architecture, roles, capabilities,
             last_seen, last_heartbeat, status, failure_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), 'active', 0)
            ON CONFLICT (hostname) DO UPDATE SET
                ip_address = EXCLUDED.ip_address,
                cpu_cores = EXCLUDED.cpu_cores,
                ram_gb = EXCLUDED.ram_gb,
                architecture = EXCLUDED.architecture,
                roles = EXCLUDED.roles,
                capabilities = EXCLUDED.capabilities,
                last_seen = NOW(),
                last_heartbeat = NOW(),
                status = 'active',
                failure_count = 0
            RETURNING id
        """, (
            worker.hostname,
            worker.ip_address,
            worker.cpu_cores,
            worker.ram_gb,
            worker.architecture,
            worker.roles,
            worker.capabilities
        ))

        worker_id = cur.fetchone()[0]
        conn.commit()

        return {
            "status": "registered",
            "worker_id": worker_id,
            "hostname": worker.hostname,
            "registered_at": datetime.now().isoformat()
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/heartbeat/{hostname}")
async def heartbeat(hostname: str):
    """Worker sends heartbeat to stay active"""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE fleet.workers
            SET last_heartbeat = NOW(),
                last_seen = NOW(),
                status = 'active',
                failure_count = 0
            WHERE hostname = %s
            RETURNING id
        """, (hostname,))

        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Worker {hostname} not registered")

        conn.commit()
        return {"status": "ok", "hostname": hostname}
    finally:
        conn.close()

@app.post("/failure")
async def report_failure(failure: WorkerFailure):
    """Orchestrator reports a worker failure (SSH timeout, connection refused, etc)"""
    conn = get_db()
    try:
        cur = conn.cursor()

        # Increment failure count and mark as degraded if failures > 2
        cur.execute("""
            UPDATE fleet.workers
            SET failure_count = failure_count + 1,
                last_failure = NOW(),
                last_failure_reason = %s,
                status = CASE
                    WHEN failure_count + 1 >= 3 THEN 'failed'
                    WHEN failure_count + 1 >= 1 THEN 'degraded'
                    ELSE status
                END,
                last_seen = NOW()
            WHERE hostname = %s
            RETURNING id, failure_count + 1, status
        """, (failure.error_message, failure.hostname))

        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail=f"Worker {failure.hostname} not registered")

        worker_id, failure_count, status = result
        conn.commit()

        return {
            "status": "recorded",
            "worker_id": worker_id,
            "hostname": failure.hostname,
            "failure_count": failure_count,
            "worker_status": status
        }
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/workers")
async def list_workers(active_only: bool = True, include_degraded: bool = False):
    """Get list of registered workers

    Args:
        active_only: Only return workers with heartbeat in last 2 minutes
        include_degraded: Include workers in 'degraded' state
    """
    conn = get_db()
    try:
        cur = conn.cursor()

        if active_only:
            # Workers are active if heartbeat within last 2 minutes (2x heartbeat interval)
            # This catches failures faster than the old 5-minute window
            if include_degraded:
                cur.execute("""
                    SELECT hostname, ip_address, cpu_cores, ram_gb, architecture,
                           roles, capabilities, last_heartbeat, last_seen, status,
                           failure_count, last_failure, last_failure_reason
                    FROM fleet.workers
                    WHERE last_heartbeat > NOW() - INTERVAL '2 minutes'
                      AND status IN ('active', 'degraded')
                    ORDER BY failure_count ASC, hostname
                """)
            else:
                cur.execute("""
                    SELECT hostname, ip_address, cpu_cores, ram_gb, architecture,
                           roles, capabilities, last_heartbeat, last_seen, status,
                           failure_count, last_failure, last_failure_reason
                    FROM fleet.workers
                    WHERE last_heartbeat > NOW() - INTERVAL '2 minutes'
                      AND status = 'active'
                    ORDER BY hostname
                """)
        else:
            cur.execute("""
                SELECT hostname, ip_address, cpu_cores, ram_gb, architecture,
                       roles, capabilities, last_heartbeat, last_seen, status,
                       failure_count, last_failure, last_failure_reason
                FROM fleet.workers
                ORDER BY hostname
            """)

        workers = []
        for row in cur.fetchall():
            workers.append({
                "hostname": row[0],
                "ip_address": row[1],
                "cpu_cores": row[2],
                "ram_gb": row[3],
                "architecture": row[4],
                "roles": row[5],
                "capabilities": row[6],
                "last_heartbeat": row[7].isoformat() if row[7] else None,
                "last_seen": row[8].isoformat() if row[8] else None,
                "status": row[9],
                "failure_count": row[10] if len(row) > 10 else 0,
                "last_failure": row[11].isoformat() if len(row) > 11 and row[11] else None,
                "last_failure_reason": row[12] if len(row) > 12 else None
            })

        return {"workers": workers, "count": len(workers)}
    finally:
        conn.close()

@app.delete("/workers/{hostname}")
async def deregister_worker(hostname: str):
    """Deregister a worker"""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE fleet.workers
            SET status = 'deregistered', last_seen = NOW()
            WHERE hostname = %s
            RETURNING id
        """, (hostname,))

        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Worker {hostname} not found")

        conn.commit()
        return {"status": "deregistered", "hostname": hostname}
    finally:
        conn.close()

@app.on_event("startup")
async def startup():
    """Create database schema if needed"""
    conn = get_db()
    try:
        cur = conn.cursor()

        # Create schema
        cur.execute("CREATE SCHEMA IF NOT EXISTS fleet")

        # Create workers table with failure tracking
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fleet.workers (
                id SERIAL PRIMARY KEY,
                hostname VARCHAR(255) UNIQUE NOT NULL,
                ip_address VARCHAR(45),
                cpu_cores INTEGER,
                ram_gb NUMERIC(6,2),
                architecture VARCHAR(50),
                roles TEXT[],
                capabilities TEXT[],
                status VARCHAR(20) DEFAULT 'active',
                last_heartbeat TIMESTAMP,
                last_seen TIMESTAMP,
                last_failure TIMESTAMP,
                last_failure_reason TEXT,
                failure_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Add new columns if they don't exist (migration)
        cur.execute("""
            DO $$
            BEGIN
                BEGIN
                    ALTER TABLE fleet.workers ADD COLUMN last_heartbeat TIMESTAMP;
                EXCEPTION WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE fleet.workers ADD COLUMN last_failure TIMESTAMP;
                EXCEPTION WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE fleet.workers ADD COLUMN last_failure_reason TEXT;
                EXCEPTION WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE fleet.workers ADD COLUMN failure_count INTEGER DEFAULT 0;
                EXCEPTION WHEN duplicate_column THEN NULL;
                END;
            END $$;
        """)

        # Create index on last_heartbeat for fast active worker queries
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_workers_heartbeat
            ON fleet.workers(last_heartbeat)
            WHERE status IN ('active', 'degraded')
        """)

        # Create index on failure_count for prioritizing healthy workers
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_workers_failures
            ON fleet.workers(failure_count)
            WHERE status = 'active'
        """)

        conn.commit()
        print("✓ Worker registry schema ready")
    except Exception as e:
        print(f"⚠ Schema setup error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
