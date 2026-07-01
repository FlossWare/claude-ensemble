#!/usr/bin/env python3
"""
Admin REST API for aio-01
Exposes endpoints for scheduled maintenance tasks
Port: 8001
"""

from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
import subprocess
import psycopg2
from datetime import datetime
import os

app = FastAPI(title="aio-01 Admin API", version="1.0")

DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,
    'database': 'learning',
    'user': 'claude'
}

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
            "GET /admin/stats"
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

@app.post("/admin/maintain-models")
async def maintain_models(background_tasks: BackgroundTasks):
    """Run model maintenance (check for new/deprecated models)"""
    def run_maintenance():
        try:
            result = subprocess.run(
                ['python3', '/mnt/aio-01/claude-orchestrator/scripts/maintain-models.py', '--auto'],
                capture_output=True,
                text=True,
                timeout=60
            )
            print(f"Model maintenance: {result.returncode}")
            print(result.stdout)
            if result.stderr:
                print(f"Errors: {result.stderr}")
        except Exception as e:
            print(f"Model maintenance failed: {e}")
    
    background_tasks.add_task(run_maintenance)
    
    return {
        "status": "started",
        "task": "model_maintenance",
        "timestamp": datetime.now().isoformat(),
        "message": "Model maintenance started in background"
    }

@app.post("/admin/run-chunking")
async def run_chunking(background_tasks: BackgroundTasks):
    """Trigger chunking process"""
    def run_chunker():
        try:
            chunker_path = '/mnt/aio-01/claude-orchestrator/universal-chunker.py'
            if os.path.exists(chunker_path):
                result = subprocess.run(
                    ['python3', chunker_path],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                print(f"Chunking: {result.returncode}")
                print(result.stdout)
            else:
                print(f"Chunker not found at {chunker_path}")
        except Exception as e:
            print(f"Chunking failed: {e}")
    
    background_tasks.add_task(run_chunker)
    
    return {
        "status": "started",
        "task": "chunking",
        "timestamp": datetime.now().isoformat(),
        "message": "Chunking process started in background"
    }

@app.post("/admin/vacuum-db")
async def vacuum_db(background_tasks: BackgroundTasks):
    """Run PostgreSQL VACUUM"""
    def run_vacuum():
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            conn.autocommit = True
            cur = conn.cursor()
            
            # VACUUM major tables
            tables = ['api_usage', 'api_embedding_usage', 'api_cache']
            
            for table in tables:
                try:
                    cur.execute(f"VACUUM ANALYZE {table}")
                    print(f"Vacuumed {table}")
                except Exception as e:
                    print(f"Could not vacuum {table}: {e}")
            
            conn.close()
            print("Database vacuum complete")
        except Exception as e:
            print(f"Vacuum failed: {e}")
    
    background_tasks.add_task(run_vacuum)
    
    return {
        "status": "started",
        "task": "vacuum",
        "timestamp": datetime.now().isoformat(),
        "message": "Database vacuum started in background"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
