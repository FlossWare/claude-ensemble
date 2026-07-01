#!/usr/bin/env python3
"""
Orchestrator REST API - Wrapper for Claude Code Workflows
Port: 8080
Runs workflows using Claude Code's Workflow tool
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import subprocess
import uuid
import json
from datetime import datetime
import os

app = FastAPI(title="Orchestrator API", version="1.0")

# Track running workflows
workflows = {}

class WorkflowRequest(BaseModel):
    name: str
    script_path: Optional[str] = None
    script: Optional[str] = None
    priority: Optional[str] = "normal"
    metadata: Optional[Dict[str, Any]] = {}

class WorkflowStatus(BaseModel):
    job_id: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None

@app.post("/api/workflow")
async def submit_workflow(req: WorkflowRequest, background_tasks: BackgroundTasks):
    """Submit a workflow for execution"""
    job_id = str(uuid.uuid4())
    
    # Save workflow script if provided inline
    script_path = req.script_path
    if req.script and not script_path:
        script_path = f"/tmp/workflow-{job_id}.mjs"
        with open(script_path, 'w') as f:
            f.write(req.script)
    
    if not script_path:
        raise HTTPException(status_code=400, detail="Either script or script_path required")
    
    # Initialize workflow status
    workflows[job_id] = {
        "job_id": job_id,
        "name": req.name,
        "status": "pending",
        "started_at": datetime.now().isoformat(),
        "script_path": script_path,
        "metadata": req.metadata
    }
    
    # Run workflow in background
    background_tasks.add_task(run_workflow, job_id, script_path)
    
    return {"job_id": job_id, "status": "pending"}

def run_workflow(job_id: str, script_path: str):
    """Execute workflow using node"""
    try:
        workflows[job_id]["status"] = "running"
        
        # Run the workflow script directly with node
        result = subprocess.run(
            ['node', script_path],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
            cwd='/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills'
        )
        
        workflows[job_id]["status"] = "completed" if result.returncode == 0 else "error"
        workflows[job_id]["completed_at"] = datetime.now().isoformat()
        
        if result.returncode == 0:
            # Try to parse JSON output
            try:
                workflows[job_id]["result"] = json.loads(result.stdout)
            except:
                workflows[job_id]["result"] = {"stdout": result.stdout}
        else:
            workflows[job_id]["error"] = result.stderr or result.stdout
            
    except subprocess.TimeoutExpired:
        workflows[job_id]["status"] = "timeout"
        workflows[job_id]["error"] = "Workflow timed out after 10 minutes"
        workflows[job_id]["completed_at"] = datetime.now().isoformat()
    except Exception as e:
        workflows[job_id]["status"] = "error"
        workflows[job_id]["error"] = str(e)
        workflows[job_id]["completed_at"] = datetime.now().isoformat()

@app.get("/api/workflow/{job_id}/status")
async def get_workflow_status(job_id: str):
    """Get workflow status"""
    if job_id not in workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    return workflows[job_id]

@app.get("/api/workflows")
async def list_workflows(limit: int = 50):
    """List recent workflows"""
    sorted_workflows = sorted(
        workflows.values(),
        key=lambda x: x["started_at"],
        reverse=True
    )
    return {"workflows": sorted_workflows[:limit], "count": len(sorted_workflows)}

@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "service": "orchestrator-api",
        "workflows_tracked": len(workflows)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
