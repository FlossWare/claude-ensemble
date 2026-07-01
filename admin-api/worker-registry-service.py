#!/usr/bin/env python3
"""
Worker Registry Service
Runs on aio-01:8001 - workers register themselves via HTTP POST
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
            (hostname, ip_address, cpu_cores, ram_gb, architecture, roles, capabilities, last_seen, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), 'active')
            ON CONFLICT (hostname) DO UPDATE SET
                ip_address = EXCLUDED.ip_address,
                cpu_cores = EXCLUDED.cpu_cores,
                ram_gb = EXCLUDED.ram_gb,
                architecture = EXCLUDED.architecture,
                roles = EXCLUDED.roles,
                capabilities = EXCLUDED.capabilities,
                last_seen = NOW(),
                status = 'active'
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
            SET last_seen = NOW(), status = 'active'
            WHERE hostname = %s
            RETURNING id
        """, (hostname,))

        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Worker {hostname} not registered")

        conn.commit()
        return {"status": "ok", "hostname": hostname}
    finally:
        conn.close()

@app.get("/workers")
async def list_workers(active_only: bool = True):
    """Get list of registered workers"""
    conn = get_db()
    try:
        cur = conn.cursor()

        if active_only:
            # Workers are active if heartbeat within last 5 minutes
            cur.execute("""
                SELECT hostname, ip_address, cpu_cores, ram_gb, architecture,
                       roles, capabilities, last_seen, status
                FROM fleet.workers
                WHERE last_seen > NOW() - INTERVAL '5 minutes'
                ORDER BY hostname
            """)
        else:
            cur.execute("""
                SELECT hostname, ip_address, cpu_cores, ram_gb, architecture,
                       roles, capabilities, last_seen, status
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
                "last_seen": row[7].isoformat() if row[7] else None,
                "status": row[8]
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

        # Create workers table
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
                last_seen TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Create index on last_seen for active worker queries
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_workers_last_seen
            ON fleet.workers(last_seen)
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
