#!/usr/bin/env python3
"""
Orchestrator REST API - Fleet Task Distribution
Port: 8080

Distributes tasks across 8-worker fleet via SSH using fleet-ssh-orchestrator.js
Workers: server-01/02/03, laptop-01, pi-01/02, desktop-ap, server-ap
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import subprocess
import uuid
import json
from datetime import datetime
import os

app = FastAPI(title="Fleet Orchestrator API", version="1.0")

# Track running tasks
tasks = {}

ORCHESTRATOR_PATH = "/mnt/aio-01/claude-orchestrator/shared/fleet-ssh-orchestrator.js"

class TaskRequest(BaseModel):
    prompt: str
    workers: Optional[List[str]] = None  # Specific workers, or None for all
    model: Optional[str] = None  # Model to use on workers
    timeout_ms: Optional[int] = 300000
    parallel: Optional[bool] = True  # Run on all workers in parallel

class TaskStatus(BaseModel):
    task_id: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    results: Optional[List[Dict]] = None
    error: Optional[str] = None

@app.post("/api/task")
async def submit_task(req: TaskRequest, background_tasks: BackgroundTasks):
    """Submit a task for fleet execution"""
    task_id = str(uuid.uuid4())

    # Initialize task status
    tasks[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "started_at": datetime.now().isoformat(),
        "prompt": req.prompt,
        "workers": req.workers,
        "parallel": req.parallel
    }

    # Run task in background
    background_tasks.add_task(execute_fleet_task, task_id, req)

    return {"task_id": task_id, "status": "pending"}

def execute_fleet_task(task_id: str, req: TaskRequest):
    """Execute task across fleet using Node.js orchestrator"""
    try:
        tasks[task_id]["status"] = "running"

        # Build Node.js script to call fleet-ssh-orchestrator
        workers = req.workers or [
            "server-01", "server-02", "server-03",
            "laptop-01", "pi-01", "pi-02",
            "desktop-ap", "server-ap"
        ]

        # Create temp script
        script_path = f"/tmp/fleet-task-{task_id}.mjs"
        with open(script_path, 'w') as f:
            f.write(f"""
import {{ executeOnWorker }} from '{ORCHESTRATOR_PATH}';

const workers = {json.dumps(workers)};
const prompt = {json.dumps(req.prompt)};

const results = await Promise.all(
  workers.map(async (worker) => {{
    try {{
      const result = await executeOnWorker({{
        worker,
        prompt,
        timeoutMs: {req.timeout_ms}
      }});
      return {{ worker, success: true, ...result }};
    }} catch (error) {{
      return {{ worker, success: false, error: error.message }};
    }}
  }})
);

console.log(JSON.stringify(results, null, 2));
""")

        # Execute with Node.js
        result = subprocess.run(
            ['node', script_path],
            capture_output=True,
            text=True,
            timeout=req.timeout_ms / 1000 + 10,  # Add buffer
            cwd='/mnt/aio-01/claude-orchestrator'
        )

        # Clean up temp script
        os.unlink(script_path)

        if result.returncode == 0:
            try:
                results = json.loads(result.stdout)
                tasks[task_id]["status"] = "completed"
                tasks[task_id]["results"] = results
            except json.JSONDecodeError:
                tasks[task_id]["status"] = "completed"
                tasks[task_id]["results"] = [{"raw_output": result.stdout}]
        else:
            tasks[task_id]["status"] = "error"
            tasks[task_id]["error"] = result.stderr or result.stdout

        tasks[task_id]["completed_at"] = datetime.now().isoformat()

    except subprocess.TimeoutExpired:
        tasks[task_id]["status"] = "timeout"
        tasks[task_id]["error"] = f"Timeout after {req.timeout_ms}ms"
        tasks[task_id]["completed_at"] = datetime.now().isoformat()
    except Exception as e:
        tasks[task_id]["status"] = "error"
        tasks[task_id]["error"] = str(e)
        tasks[task_id]["completed_at"] = datetime.now().isoformat()

@app.get("/api/task/{task_id}")
async def get_task_status(task_id: str):
    """Get task status"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    return tasks[task_id]

@app.get("/api/tasks")
async def list_tasks(limit: int = 50):
    """List recent tasks"""
    sorted_tasks = sorted(
        tasks.values(),
        key=lambda x: x["started_at"],
        reverse=True
    )
    return {"tasks": sorted_tasks[:limit], "count": len(sorted_tasks)}

@app.get("/health")
async def health():
    """Health check"""
    # Check if orchestrator file exists
    orchestrator_exists = os.path.exists(ORCHESTRATOR_PATH)

    return {
        "status": "healthy" if orchestrator_exists else "degraded",
        "service": "fleet-orchestrator-api",
        "tasks_tracked": len(tasks),
        "orchestrator_available": orchestrator_exists
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
