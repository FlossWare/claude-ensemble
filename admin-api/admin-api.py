#!/usr/bin/env python3
"""
Admin REST API for aio-01
Exposes endpoints for scheduled maintenance tasks
Port: 8001

ISSUE 4 FIX: Background task status tracking
ISSUE 238 FIX: Password authentication with bcrypt + JWT
"""

from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import subprocess
import psycopg2
from psycopg2 import sql as psycopg2_sql
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta, timezone
import os
import uuid
import logging
from logging.handlers import RotatingFileHandler
import bcrypt
import jwt
import secrets

# Setup logging
logger = logging.getLogger('admin-api')
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('/var/log/admin-api.log', maxBytes=10*1024*1024, backupCount=5)
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

app = FastAPI(title="aio-01 Admin API", version="2.0")

# JWT configuration
JWT_SECRET = os.getenv('ADMIN_API_JWT_SECRET', secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv('ADMIN_API_TOKEN_EXPIRY_HOURS', '24'))

# Security scheme
security = HTTPBearer()

DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,
    'database': 'learning',
    'user': 'claude',
    'password': os.getenv('DB_PASSWORD', '')
}


# ---------- Pydantic models for request bodies ----------

class LoginRequest(BaseModel):
    username: str
    password: str

class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "admin"

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ---------- Password hashing ----------

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


# ---------- JWT token management ----------

def create_access_token(username: str, role: str) -> str:
    """Create a JWT access token."""
    payload = {
        "sub": username,
        "role": role,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Validate JWT token and return current user info."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
            )
        # Verify user still exists in database
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT username, role, enabled FROM admin.users WHERE username = %s",
                (username,),
            )
            user = cur.fetchone()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User no longer exists",
                )
            if not user['enabled']:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is disabled",
                )
            return {"username": user['username'], "role": user['role']}
        finally:
            return_db(conn)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )


# ---------- Connection helpers ----------

def get_db():
    """Get database connection"""
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

def return_db(conn):
    """Return connection to pool"""
    if conn:
        conn.close()


# ---------- Database initialization ----------

def init_users_table():
    """Create admin.users table if not exists and seed default admin user."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("CREATE SCHEMA IF NOT EXISTS admin")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS admin.users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'admin',
                enabled BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_login TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_username
            ON admin.users(username)
        """)
        # Seed default admin user if no users exist
        cur.execute("SELECT COUNT(*) as cnt FROM admin.users")
        count = cur.fetchone()['cnt']
        if count == 0:
            default_password = os.getenv('ADMIN_API_DEFAULT_PASSWORD', 'changeme')
            hashed = hash_password(default_password)
            cur.execute("""
                INSERT INTO admin.users (username, password_hash, role)
                VALUES ('admin', %s, 'superadmin')
            """, (hashed,))
            logger.info("Default admin user created (username: admin) - change password immediately")
        conn.commit()
        logger.info("Users table initialized")
    except Exception as e:
        logger.error(f"Failed to initialize users table: {e}")
    finally:
        return_db(conn)


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


# Initialize tables on startup
@app.on_event("startup")
async def startup_event():
    init_background_tasks_table()
    init_users_table()


# ---------- Background task helpers ----------

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


# ======================================================================
# PUBLIC ENDPOINTS (no authentication required)
# ======================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "aio-01 Admin API",
        "version": "2.0",
        "auth": "Bearer token required for /admin/* endpoints",
        "endpoints": [
            "POST /auth/login",
            "POST /admin/maintain-models",
            "POST /admin/run-chunking",
            "POST /admin/vacuum-db",
            "POST /admin/backup-db",
            "POST /admin/users",
            "PUT /admin/users/me/password",
            "GET /admin/users",
            "GET /admin/health",
            "GET /admin/stats",
            "GET /admin/tasks/{job_id}",
            "GET /admin/tasks"
        ]
    }


@app.post("/auth/login")
async def login(request: LoginRequest):
    """Authenticate and receive a JWT token."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT username, password_hash, role, enabled FROM admin.users WHERE username = %s",
            (request.username,),
        )
        user = cur.fetchone()

        if not user or not verify_password(request.password, user['password_hash']):
            logger.warning(f"Failed login attempt for user: {request.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )

        if not user['enabled']:
            logger.warning(f"Login attempt for disabled user: {request.username}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled",
            )

        # Update last login timestamp
        cur.execute(
            "UPDATE admin.users SET last_login = NOW() WHERE username = %s",
            (request.username,),
        )
        conn.commit()

        token = create_access_token(user['username'], user['role'])
        logger.info(f"Successful login for user: {request.username}")

        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in_hours": JWT_EXPIRATION_HOURS,
            "username": user['username'],
            "role": user['role'],
        }
    finally:
        return_db(conn)


# ======================================================================
# AUTHENTICATED ENDPOINTS (JWT required)
# ======================================================================

@app.post("/admin/users", status_code=status.HTTP_201_CREATED)
async def create_user(request: CreateUserRequest, current_user: dict = Depends(get_current_user)):
    """Create a new admin user. Requires superadmin role."""
    if current_user['role'] != 'superadmin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superadmin can create users",
        )

    if len(request.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )

    conn = get_db()
    try:
        cur = conn.cursor()
        # Check if username already exists
        cur.execute("SELECT username FROM admin.users WHERE username = %s", (request.username,))
        if cur.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User '{request.username}' already exists",
            )

        hashed = hash_password(request.password)
        cur.execute("""
            INSERT INTO admin.users (username, password_hash, role)
            VALUES (%s, %s, %s)
            RETURNING id, username, role, created_at
        """, (request.username, hashed, request.role))
        conn.commit()
        user = cur.fetchone()

        logger.info(f"User created: {request.username} (role: {request.role}) by {current_user['username']}")

        return {
            "id": str(user['id']),
            "username": user['username'],
            "role": user['role'],
            "created_at": user['created_at'].isoformat(),
        }
    finally:
        return_db(conn)


@app.get("/admin/users")
async def list_users(current_user: dict = Depends(get_current_user)):
    """List all admin users. Requires superadmin role."""
    if current_user['role'] != 'superadmin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superadmin can list users",
        )

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, role, enabled, created_at, last_login
            FROM admin.users
            ORDER BY created_at
        """)
        rows = cur.fetchall()
        users = []
        for row in rows:
            user = dict(row)
            user['id'] = str(user['id'])
            if user.get('created_at'):
                user['created_at'] = user['created_at'].isoformat()
            if user.get('last_login'):
                user['last_login'] = user['last_login'].isoformat()
            users.append(user)
        return {"users": users, "count": len(users)}
    finally:
        return_db(conn)


@app.put("/admin/users/me/password")
async def change_password(request: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    """Change your own password."""
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters",
        )

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT password_hash FROM admin.users WHERE username = %s",
            (current_user['username'],),
        )
        user = cur.fetchone()

        if not verify_password(request.current_password, user['password_hash']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect",
            )

        new_hash = hash_password(request.new_password)
        cur.execute(
            "UPDATE admin.users SET password_hash = %s WHERE username = %s",
            (new_hash, current_user['username']),
        )
        conn.commit()

        logger.info(f"Password changed for user: {current_user['username']}")

        return {"message": "Password changed successfully"}
    finally:
        return_db(conn)


@app.get("/admin/health")
async def health(current_user: dict = Depends(get_current_user)):
    """System health check"""
    conn = None
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
    finally:
        if conn:
            conn.close()

@app.get("/admin/stats")
async def stats(current_user: dict = Depends(get_current_user)):
    """Current system stats"""
    conn = None
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
    finally:
        if conn:
            conn.close()

@app.get("/admin/tasks/{job_id}")
async def get_task_status(job_id: str, current_user: dict = Depends(get_current_user)):
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
async def list_tasks(limit: int = 50, status: str = None, current_user: dict = Depends(get_current_user)):
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
async def maintain_models(background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
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
async def run_chunking(background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
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
async def vacuum_db(background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    """Run PostgreSQL VACUUM"""
    job_id = create_task('vacuum')

    def run_vacuum():
        conn = None
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
                    cur.execute(psycopg2_sql.SQL("VACUUM ANALYZE {}").format(psycopg2_sql.Identifier(table)))
                    vacuumed.append(table)
                    logger.info(f"Vacuumed {table} (job_id={job_id})")
                except Exception as e:
                    errors.append(f"{table}: {str(e)}")
                    logger.error(f"Could not vacuum {table} (job_id={job_id}): {e}")

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
        finally:
            if conn:
                conn.close()

    background_tasks.add_task(run_vacuum)

    return {
        "status": "started",
        "task": "vacuum",
        "job_id": job_id,
        "timestamp": datetime.now().isoformat(),
        "message": "Database vacuum started in background"
    }


@app.post("/admin/backup-db")
async def backup_db(background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    """Backup PostgreSQL and OrientDB databases to local storage"""
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

            # 2. Backup OrientDB (online export, no restart needed)
            logger.info("Backing up OrientDB...")
            orientdb_file = f"{backup_dir}/orientdb-{timestamp}.gz"

            export_result = subprocess.run(
                'docker exec orientdb /orientdb/bin/console.sh "EXPORT DATABASE /orientdb/databases/backup.gz"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=600
            )

            if export_result.returncode == 0:
                copy_result = subprocess.run(
                    f"docker cp orientdb:/orientdb/databases/backup.gz {orientdb_file}",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                if copy_result.returncode == 0:
                    size = subprocess.run(f"du -h {orientdb_file} | cut -f1", shell=True, capture_output=True, text=True).stdout.strip()
                    logger.info(f"OrientDB backup complete: {orientdb_file} ({size})")
                    results.append(f"OrientDB: {size}")
                else:
                    logger.error(f"OrientDB copy failed: {copy_result.stderr}")
                    errors.append(f"OrientDB copy: {copy_result.stderr[:200]}")
            else:
                logger.error(f"OrientDB export failed: {export_result.stderr}")
                errors.append(f"OrientDB: {export_result.stderr[:200]}")

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
            update_task_status(job_id, 'error', error_message="Backup timed out")
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            update_task_status(job_id, 'error', error_message=str(e)[:500])

    background_tasks.add_task(run_backup)

    return {
        "status": "started",
        "task": "backup",
        "timestamp": datetime.now().isoformat(),
        "message": "Database backups (PostgreSQL + OrientDB) to /var/backups/databases started"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
