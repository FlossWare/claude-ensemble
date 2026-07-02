#!/usr/bin/env python3
"""
Fleet Control API - Remote orchestration and task management
Runs on aio-01:8004 - trigger workflows, submit tasks, monitor fleet
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import subprocess
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
import psycopg2
import requests

app = FastAPI(title="Fleet Control API", version="1.0.0")

DB_CONFIG = {
    'host': os.getenv('PGHOST', 'aio-01'),
    'port': int(os.getenv('PGPORT', '5433')),
    'database': os.getenv('PGDATABASE', 'learning'),
    'user': os.getenv('PGUSER', 'claude')
}

ORCHESTRATOR_PATH = Path('/mnt/aio-01/claude-orchestrator')

class TaskSubmission(BaseModel):
    prompt: str
    model: str = 'llama-3.3-70b-versatile'
    worker: str = None  # Auto-select if None
    timeout_ms: int = 30000

class WorkflowSubmission(BaseModel):
    workflow_name: str
    args: dict = {}
    description: str = ''

class CommandSubmission(BaseModel):
    command: str
    workers: list[str] = []  # Empty = all workers
    timeout_ms: int = 30000

def get_db():
    return psycopg2.connect(**DB_CONFIG)

@app.get("/")
async def root():
    """API information"""
    return {
        "service": "Fleet Control API",
        "version": "1.0.0",
        "endpoints": {
            "/task": "Submit single task",
            "/workflow": "Trigger workflow",
            "/command": "Run command on workers",
            "/status": "Get fleet status",
            "/workers": "List workers",
            "/tasks/{task_id}": "Get task status"
        }
    }

@app.post("/task")
async def submit_task(task: TaskSubmission, background_tasks: BackgroundTasks):
    """Submit a single task to the fleet"""
    task_id = str(uuid.uuid4())

    # Store task in database
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO fleet.tasks
            (task_id, prompt, model, worker, status, timeout_ms, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        """, (task_id, task.prompt, task.model, task.worker, 'pending', task.timeout_ms))

        conn.commit()

        # Execute task in background
        background_tasks.add_task(execute_task, task_id, task)

        return {
            "task_id": task_id,
            "status": "submitted",
            "message": "Task queued for execution"
        }
    finally:
        conn.close()

@app.post("/workflow")
async def trigger_workflow(workflow: WorkflowSubmission, background_tasks: BackgroundTasks):
    """Trigger a workflow"""
    workflow_id = str(uuid.uuid4())

    # Store workflow in database
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO fleet.workflows
            (workflow_id, workflow_name, args, description, status, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            RETURNING id
        """, (workflow_id, workflow.workflow_name, json.dumps(workflow.args),
              workflow.description, 'pending'))

        conn.commit()

        # Execute workflow in background
        background_tasks.add_task(execute_workflow, workflow_id, workflow)

        return {
            "workflow_id": workflow_id,
            "status": "submitted",
            "message": "Workflow queued for execution"
        }
    finally:
        conn.close()

@app.post("/command")
async def run_command(cmd: CommandSubmission):
    """Run command on one or more workers (synchronous execution)"""
    command_id = str(uuid.uuid4())

    # If no workers specified, get all active workers
    if not cmd.workers:
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT hostname FROM fleet.workers
                WHERE last_heartbeat > NOW() - INTERVAL '2 minutes'
                AND status = 'active'
            """)
            cmd.workers = [row[0] for row in cur.fetchall()]
        finally:
            conn.close()

    # Execute command synchronously (for immediate results)
    results = await execute_command(command_id, cmd)

    return {
        "command_id": command_id,
        "workers": cmd.workers,
        "status": "completed",
        "results": results
    }

@app.get("/status")
async def get_fleet_status():
    """Get overall fleet status"""
    conn = get_db()
    try:
        cur = conn.cursor()

        # Worker counts
        cur.execute("""
            SELECT status, COUNT(*)
            FROM fleet.workers
            WHERE last_heartbeat > NOW() - INTERVAL '2 minutes'
            GROUP BY status
        """)
        worker_status = {row[0]: row[1] for row in cur.fetchall()}

        # Recent tasks
        cur.execute("""
            SELECT status, COUNT(*)
            FROM fleet.tasks
            WHERE created_at > NOW() - INTERVAL '1 hour'
            GROUP BY status
        """)
        task_status = {row[0]: row[1] for row in cur.fetchall()}

        # Active workflows
        cur.execute("""
            SELECT COUNT(*)
            FROM fleet.workflows
            WHERE status IN ('pending', 'running')
        """)
        active_workflows = cur.fetchone()[0]

        return {
            "workers": worker_status,
            "tasks": task_status,
            "active_workflows": active_workflows,
            "timestamp": datetime.now().isoformat()
        }
    finally:
        conn.close()

@app.get("/workers")
async def list_workers():
    """List all workers"""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT hostname, ip_address, cpu_cores, ram_gb, status,
                   last_heartbeat, failure_count
            FROM fleet.workers
            WHERE last_heartbeat > NOW() - INTERVAL '5 minutes'
            ORDER BY hostname
        """)

        workers = []
        for row in cur.fetchall():
            workers.append({
                "hostname": row[0],
                "ip_address": row[1],
                "cpu_cores": row[2],
                "ram_gb": float(row[3]) if row[3] else 0,
                "status": row[4],
                "last_heartbeat": row[5].isoformat() if row[5] else None,
                "failure_count": row[6]
            })

        return {"workers": workers, "count": len(workers)}
    finally:
        conn.close()

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get task status"""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT task_id, prompt, model, worker, status,
                   result, error, created_at, completed_at
            FROM fleet.tasks
            WHERE task_id = %s
        """, (task_id,))

        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")

        return {
            "task_id": row[0],
            "prompt": row[1],
            "model": row[2],
            "worker": row[3],
            "status": row[4],
            "result": row[5],
            "error": row[6],
            "created_at": row[7].isoformat() if row[7] else None,
            "completed_at": row[8].isoformat() if row[8] else None
        }
    finally:
        conn.close()

@app.get("/commands/{command_id}")
async def get_command_results(command_id: str):
    """Get command execution results"""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT command_id, command, workers, results, created_at
            FROM fleet.command_results
            WHERE command_id = %s
        """, (command_id,))

        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Command not found")

        return {
            "command_id": row[0],
            "command": row[1],
            "workers": row[2],
            "results": json.loads(row[3]) if isinstance(row[3], str) else row[3],
            "created_at": row[4].isoformat() if row[4] else None
        }
    finally:
        conn.close()

# Background task execution functions

async def execute_task(task_id: str, task: TaskSubmission):
    """Execute task using worker-http-client"""
    conn = get_db()
    try:
        # Update status to running
        cur = conn.cursor()
        cur.execute("""
            UPDATE fleet.tasks
            SET status = 'running', started_at = NOW()
            WHERE task_id = %s
        """, (task_id,))
        conn.commit()

        # Execute via Node.js worker-http-client
        # For now, use worker-client.sh via subprocess
        # CRITICAL FIX (#276): Use list format to prevent command injection
        # Never use shell=True with user-provided input (task.prompt)

        import shlex
        worker_client = os.path.expanduser('~/worker-client.sh')
        result = subprocess.run(
            [worker_client, task.prompt, task.model],
            shell=False,  # CRITICAL: Prevents command injection
            capture_output=True,
            text=True,
            timeout=task.timeout_ms / 1000
        )

        # Update with result
        cur.execute("""
            UPDATE fleet.tasks
            SET status = %s, result = %s, error = %s, completed_at = NOW()
            WHERE task_id = %s
        """, ('completed' if result.returncode == 0 else 'failed',
              result.stdout, result.stderr, task_id))
        conn.commit()

    except Exception as e:
        cur = conn.cursor()
        cur.execute("""
            UPDATE fleet.tasks
            SET status = 'failed', error = %s, completed_at = NOW()
            WHERE task_id = %s
        """, (str(e), task_id))
        conn.commit()
    finally:
        conn.close()

async def execute_workflow(workflow_id: str, workflow: WorkflowSubmission):
    """Execute workflow"""
    conn = get_db()
    try:
        # Update status
        cur = conn.cursor()
        cur.execute("""
            UPDATE fleet.workflows
            SET status = 'running', started_at = NOW()
            WHERE workflow_id = %s
        """, (workflow_id,))
        conn.commit()

        # Execute workflow
        workflow_path = ORCHESTRATOR_PATH / 'workflows' / f'{workflow.workflow_name}.mjs'
        if not workflow_path.exists():
            raise Exception(f"Workflow not found: {workflow.workflow_name}")

        result = subprocess.run(
            ['node', str(workflow_path)],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=ORCHESTRATOR_PATH
        )

        # Update with result
        cur.execute("""
            UPDATE fleet.workflows
            SET status = %s, result = %s, error = %s, completed_at = NOW()
            WHERE workflow_id = %s
        """, ('completed' if result.returncode == 0 else 'failed',
              result.stdout, result.stderr, workflow_id))
        conn.commit()

    except Exception as e:
        cur = conn.cursor()
        cur.execute("""
            UPDATE fleet.workflows
            SET status = 'failed', error = %s, completed_at = NOW()
            WHERE workflow_id = %s
        """, (str(e), workflow_id))
        conn.commit()
    finally:
        conn.close()

async def execute_command(command_id: str, cmd: CommandSubmission):
    """Execute command on workers via HTTP"""
    results = {}
    for worker in cmd.workers:
        try:
            # Call worker daemon HTTP API
            response = requests.post(
                f'http://{worker}:8003/execute',
                json={
                    'command': cmd.command,
                    'args': [],
                    'timeout': cmd.timeout_ms // 1000
                },
                headers={'Authorization': f'Bearer {os.getenv("WORKER_AUTH_TOKEN", "change-me-in-production")}'},
                timeout=cmd.timeout_ms / 1000
            )

            if response.status_code == 200:
                data = response.json()
                results[worker] = {
                    'success': data.get('success', False),
                    'stdout': data.get('stdout', ''),
                    'stderr': data.get('stderr', ''),
                    'returncode': data.get('returncode', -1)
                }
            else:
                results[worker] = {
                    'success': False,
                    'error': f'HTTP {response.status_code}: {response.text[:100]}'
                }
        except Exception as e:
            results[worker] = {
                'success': False,
                'error': str(e)
            }

    # Store results in database
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO fleet.command_results
            (command_id, command, workers, results, created_at)
            VALUES (%s, %s, %s, %s, NOW())
        """, (command_id, cmd.command, cmd.workers, json.dumps(results)))
        conn.commit()
    finally:
        conn.close()

    return results

@app.on_event("startup")
async def startup():
    """Create database schema if needed"""
    conn = get_db()
    try:
        cur = conn.cursor()

        # Tasks table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fleet.tasks (
                id SERIAL PRIMARY KEY,
                task_id VARCHAR(255) UNIQUE NOT NULL,
                prompt TEXT,
                model VARCHAR(255),
                worker VARCHAR(255),
                status VARCHAR(20) DEFAULT 'pending',
                result TEXT,
                error TEXT,
                timeout_ms INTEGER,
                created_at TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

        # Workflows table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fleet.workflows (
                id SERIAL PRIMARY KEY,
                workflow_id VARCHAR(255) UNIQUE NOT NULL,
                workflow_name VARCHAR(255),
                args JSONB,
                description TEXT,
                status VARCHAR(20) DEFAULT 'pending',
                result TEXT,
                error TEXT,
                created_at TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

        # Command results table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fleet.command_results (
                id SERIAL PRIMARY KEY,
                command_id VARCHAR(255) UNIQUE NOT NULL,
                command TEXT,
                workers TEXT[],
                results JSONB,
                created_at TIMESTAMP
            )
        """)

        conn.commit()
        print("✓ Fleet control schema ready")
    except Exception as e:
        print(f"⚠ Schema setup error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
