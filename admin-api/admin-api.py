#!/usr/bin/env python3
"""
Admin REST API for aio-01
Exposes endpoints for scheduled maintenance tasks
Port: 8001

ISSUE 4 FIX: Background task status tracking
"""

from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
import subprocess
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import os
import uuid
import logging
from logging.handlers import RotatingFileHandler

# Setup logging
logger = logging.getLogger('admin-api')
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('/var/log/admin-api.log', maxBytes=10*1024*1024, backupCount=5)
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

app = FastAPI(title="aio-01 Admin API", version="1.0")

DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,
    'database': 'learning',
    'user': 'claude',
    'password': os.getenv('DB_PASSWORD', '')
}

# Connection pool helpers
def get_db():
    """Get database connection"""
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

def return_db(conn):
    """Return connection to pool"""
    if conn:
        conn.close()

def init_background_tasks_table():
    """Create background_tasks table if not exists"""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE SCHEMA IF NOT EXISTS admin
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS admin.background_tasks (
                job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                task_type VARCHAR(50) NOT NULL,
                status VARCHAR(20) NOT NULL,  -- pending, running, success, error
                started_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP,
                error_message TEXT,
                result_summary TEXT
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_background_tasks_status
            ON admin.background_tasks(status)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_background_tasks_started
            ON admin.background_tasks(started_at DESC)
        """)
        conn.commit()
        logger.info("Background tasks table initialized")
    except Exception as e:
        logger.error(f"Failed to initialize background_tasks table: {e}")
    finally:
        return_db(conn)

# Initialize table on startup
@app.on_event("startup")
async def startup_event():
    init_background_tasks_table()

def create_task(task_type: str) -> str:
    """Create a background task record and return job_id"""
    conn = get_db()
    try:
        cur = conn.cursor()
        job_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO admin.background_tasks (job_id, task_type, status)
            VALUES (%s, %s, 'pending')
            RETURNING job_id
        """, (job_id, task_type))
        conn.commit()
        result = cur.fetchone()
        return result['job_id']
    finally:
        return_db(conn)

def update_task_status(job_id: str, status: str, error_message: str = None, result_summary: str = None):
    """Update background task status"""
    conn = get_db()
    try:
        cur = conn.cursor()
        if status in ['success', 'error']:
            cur.execute("""
                UPDATE admin.background_tasks
                SET status = %s,
                    completed_at = NOW(),
                    error_message = %s,
                    result_summary = %s
                WHERE job_id = %s
            """, (status, error_message, result_summary, job_id))
        else:
            cur.execute("""
                UPDATE admin.background_tasks
                SET status = %s
                WHERE job_id = %s
            """, (status, job_id))
        conn.commit()
    finally:
        return_db(conn)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "aio-01 Admin API",
        "version": "1.0",
        "endpoints": [
            "POST /admin/maintain-models",
            "POST /admin/run-chunking",
            "POST /admin/vacuum-db",
            "GET /admin/health",
            "GET /admin/stats",
            "GET /admin/tasks/{job_id}",
            "GET /admin/tasks"
        ]
    }

@app.get("/admin/health")
async def health():
    """System health check"""
    try:
        # Check proxy
        proxy_status = subprocess.run(
            ['systemctl', 'is-active', 'api-proxy'],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Check PostgreSQL
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM api_models WHERE enabled = true")
        enabled_models = cur.fetchone()[0]
        conn.close()

        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "api_proxy": proxy_status.stdout.strip(),
                "postgresql": "active"
            },
            "models": {
                "enabled": enabled_models
            }
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )

@app.get("/admin/stats")
async def stats():
    """Current system stats"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Model counts
        cur.execute("""
            SELECT provider, COUNT(*) as total,
                   COUNT(*) FILTER (WHERE enabled) as enabled
            FROM api_models
            GROUP BY provider
            ORDER BY provider
        """)
        models = [{"provider": r[0], "total": r[1], "enabled": r[2]}
                  for r in cur.fetchall()]

        # Recent API usage
        cur.execute("""
            SELECT COUNT(*) as calls,
                   SUM(prompt_tokens + completion_tokens) as tokens,
                   COUNT(DISTINCT worker_id) as workers
            FROM api_usage
            WHERE timestamp > NOW() - INTERVAL '24 hours'
        """)
        usage = cur.fetchone()

        conn.close()

        return {
            "timestamp": datetime.now().isoformat(),
            "models": models,
            "usage_24h": {
                "api_calls": usage[0] or 0,
                "tokens": usage[1] or 0,
                "unique_workers": usage[2] or 0
            }
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.get("/admin/tasks/{job_id}")
async def get_task_status(job_id: str):
    """Get background task status"""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM admin.background_tasks WHERE job_id = %s", (job_id,))
        row = cur.fetchone()
        if not row:
            return JSONResponse(status_code=404, content={"error": "Task not found"})

        # Convert datetime to ISO string
        result = dict(row)
        if result.get('started_at'):
            result['started_at'] = result['started_at'].isoformat()
        if result.get('completed_at'):
            result['completed_at'] = result['completed_at'].isoformat()

        return result
    finally:
        return_db(conn)

@app.get("/admin/tasks")
async def list_tasks(limit: int = 50, status: str = None):
    """List recent background tasks"""
    conn = get_db()
    try:
        cur = conn.cursor()
        if status:
            cur.execute("""
                SELECT * FROM admin.background_tasks
                WHERE status = %s
                ORDER BY started_at DESC
                LIMIT %s
            """, (status, limit))
        else:
            cur.execute("""
                SELECT * FROM admin.background_tasks
                ORDER BY started_at DESC
                LIMIT %s
            """, (limit,))

        rows = cur.fetchall()
        results = []
        for row in rows:
            result = dict(row)
            if result.get('started_at'):
                result['started_at'] = result['started_at'].isoformat()
            if result.get('completed_at'):
                result['completed_at'] = result['completed_at'].isoformat()
            results.append(result)

        return {"tasks": results, "count": len(results)}
    finally:
        return_db(conn)

@app.post("/admin/maintain-models")
async def maintain_models(background_tasks: BackgroundTasks):
    """Run model maintenance (check for new/deprecated models)"""
    job_id = create_task('model_maintenance')

    def run_maintenance():
        try:
            update_task_status(job_id, 'running')
            logger.info(f"Model maintenance started (job_id={job_id})")

            result = subprocess.run(
                ['python3', '/mnt/aio-01/claude-orchestrator/scripts/maintain-models.py', '--auto'],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                summary = f"Success: {result.stdout[:200]}" if result.stdout else "Success"
                update_task_status(job_id, 'success', result_summary=summary)
                logger.info(f"Model maintenance complete (job_id={job_id})")
            else:
                error_msg = result.stderr or "Non-zero exit code"
                update_task_status(job_id, 'error', error_message=error_msg)
                logger.error(f"Model maintenance failed (job_id={job_id}): {error_msg}")

        except subprocess.TimeoutExpired:
            update_task_status(job_id, 'error', error_message="Timeout after 60s")
            logger.error(f"Model maintenance timed out (job_id={job_id})")
        except Exception as e:
            update_task_status(job_id, 'error', error_message=str(e))
            logger.error(f"Model maintenance failed (job_id={job_id}): {e}")

    background_tasks.add_task(run_maintenance)

    return {
        "status": "started",
        "task": "model_maintenance",
        "job_id": job_id,
        "timestamp": datetime.now().isoformat(),
        "message": "Model maintenance started in background"
    }

@app.post("/admin/run-chunking")
async def run_chunking(background_tasks: BackgroundTasks):
    """Trigger chunking process"""
    job_id = create_task('chunking')

    def run_chunker():
        try:
            update_task_status(job_id, 'running')
            logger.info(f"Chunking started (job_id={job_id})")

            chunker_path = '/mnt/aio-01/claude-orchestrator/universal-chunker.py'
            if not os.path.exists(chunker_path):
                update_task_status(job_id, 'error', error_message=f"Chunker not found at {chunker_path}")
                logger.error(f"Chunker not found (job_id={job_id})")
                return

            result = subprocess.run(
                ['python3', chunker_path],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                summary = f"Success: {result.stdout[:200]}" if result.stdout else "Success"
                update_task_status(job_id, 'success', result_summary=summary)
                logger.info(f"Chunking complete (job_id={job_id})")
            else:
                error_msg = result.stderr or "Non-zero exit code"
                update_task_status(job_id, 'error', error_message=error_msg)
                logger.error(f"Chunking failed (job_id={job_id}): {error_msg}")

        except subprocess.TimeoutExpired:
            update_task_status(job_id, 'error', error_message="Timeout after 300s")
            logger.error(f"Chunking timed out (job_id={job_id})")
        except Exception as e:
            update_task_status(job_id, 'error', error_message=str(e))
            logger.error(f"Chunking failed (job_id={job_id}): {e}")

    background_tasks.add_task(run_chunker)

    return {
        "status": "started",
        "task": "chunking",
        "job_id": job_id,
        "timestamp": datetime.now().isoformat(),
        "message": "Chunking process started in background"
    }

@app.post("/admin/vacuum-db")
async def vacuum_db(background_tasks: BackgroundTasks):
    """Run PostgreSQL VACUUM"""
    job_id = create_task('vacuum')

    def run_vacuum():
        try:
            update_task_status(job_id, 'running')
            logger.info(f"Database vacuum started (job_id={job_id})")

            conn = psycopg2.connect(**DB_CONFIG)
            conn.autocommit = True
            cur = conn.cursor()

            # VACUUM major tables
            tables = ['api_usage', 'api_embedding_usage', 'api_cache']
            vacuumed = []
            errors = []

            for table in tables:
                try:
                    cur.execute(f"VACUUM ANALYZE {table}")
                    vacuumed.append(table)
                    logger.info(f"Vacuumed {table} (job_id={job_id})")
                except Exception as e:
                    errors.append(f"{table}: {str(e)}")
                    logger.error(f"Could not vacuum {table} (job_id={job_id}): {e}")

            conn.close()

            if errors:
                update_task_status(job_id, 'error',
                                 error_message=f"Partial success. Errors: {'; '.join(errors)}",
                                 result_summary=f"Vacuumed: {', '.join(vacuumed)}")
            else:
                update_task_status(job_id, 'success',
                                 result_summary=f"Vacuumed: {', '.join(vacuumed)}")

            logger.info(f"Database vacuum complete (job_id={job_id})")

        except Exception as e:
            update_task_status(job_id, 'error', error_message=str(e))
            logger.error(f"Database vacuum failed (job_id={job_id}): {e}")

    background_tasks.add_task(run_vacuum)

    return {
        "status": "started",
        "task": "vacuum",
        "job_id": job_id,
        "timestamp": datetime.now().isoformat(),
        "message": "Database vacuum started in background"
    }





@app.post("/admin/backup-db")
async def backup_db(background_tasks: BackgroundTasks):
    """Backup PostgreSQL and Neo4j databases to local storage"""
    def run_backup():
        job_id = create_task('backup')
        update_task_status(job_id, 'running')
        logger.info(f"Starting database backups (job_id={job_id})")

        results = []
        errors = []

        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = "/var/backups/databases"

            # Ensure local backup directory exists
            subprocess.run(f"mkdir -p {backup_dir}", shell=True, timeout=5)

            # 1. Backup PostgreSQL (can run while online)
            logger.info("Backing up PostgreSQL...")
            pg_file = f"{backup_dir}/postgresql-learning-{timestamp}.sql.gz"
            pg_result = subprocess.run(
                f"PGPASSWORD='' pg_dump -h localhost -p 5433 -U claude learning | gzip > {pg_file}",
                shell=True,
                capture_output=True,
                text=True,
                timeout=600
            )

            if pg_result.returncode == 0:
                size = subprocess.run(f"du -h {pg_file} | cut -f1", shell=True, capture_output=True, text=True).stdout.strip()
                logger.info(f"PostgreSQL backup complete: {pg_file} ({size})")
                results.append(f"PostgreSQL: {size}")
            else:
                logger.error(f"PostgreSQL backup failed: {pg_result.stderr}")
                errors.append(f"PostgreSQL: {pg_result.stderr[:200]}")

            # 2. Backup Neo4j (must stop, dump, restart)
            logger.info("Stopping Neo4j for backup...")
            subprocess.run("systemctl stop neo4j", shell=True, timeout=30)

            neo4j_file = f"{backup_dir}/neo4j-{timestamp}.dump"
            neo4j_result = subprocess.run(
                f"sudo -u neo4j neo4j-admin database dump neo4j --to-path=/tmp && "
                f"mv /tmp/neo4j.dump {neo4j_file} && "
                f"chmod 644 {neo4j_file}",
                shell=True,
                capture_output=True,
                text=True,
                timeout=600
            )

            # Always restart Neo4j
            logger.info("Restarting Neo4j...")
            subprocess.run("systemctl start neo4j", shell=True, timeout=30)

            if neo4j_result.returncode == 0:
                size = subprocess.run(f"du -h {neo4j_file} | cut -f1", shell=True, capture_output=True, text=True).stdout.strip()
                logger.info(f"Neo4j backup complete: {neo4j_file} ({size})")
                results.append(f"Neo4j: {size}")
            else:
                logger.error(f"Neo4j backup failed: {neo4j_result.stderr}")
                errors.append(f"Neo4j: {neo4j_result.stderr[:200]}")

            # Update status
            if errors:
                summary = f"Partial: {', '.join(results)}. Errors: {'; '.join(errors)}"
                update_task_status(job_id, 'error', 
                                 error_message='; '.join(errors),
                                 result_summary=summary)
            else:
                summary = f"Backed up to /var/backups/databases: {', '.join(results)}"
                update_task_status(job_id, 'success', result_summary=summary)

        except subprocess.TimeoutExpired:
            logger.error("Backup timed out")
            # Ensure Neo4j is running
            subprocess.run("systemctl start neo4j", shell=True, timeout=30)
            update_task_status(job_id, 'error', error_message="Backup timed out")
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            # Ensure Neo4j is running
            subprocess.run("systemctl start neo4j", shell=True, timeout=30)
            update_task_status(job_id, 'error', error_message=str(e)[:500])

    job_id = create_task('backup')
    background_tasks.add_task(run_backup)

    return {
        "status": "started",
        "task": "backup",
        "timestamp": datetime.now().isoformat(),
        "job_id": str(job_id),
        "message": "Database backups (PostgreSQL + Neo4j) to /var/backups/databases started"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
