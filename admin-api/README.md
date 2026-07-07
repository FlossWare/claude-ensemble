# Admin REST API

REST API on aio-01:8001 for administrative tasks triggered by util-ap cron jobs.

## Authentication

All `/admin/*` endpoints require a JWT Bearer token. Obtain a token via the login endpoint.

### Login
```bash
# Get a JWT token
curl -X POST http://aio-01:8001/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username": "admin", "password": "changeme"}'

# Response:
# {
#   "access_token": "eyJ...",
#   "token_type": "bearer",
#   "expires_in_hours": 24,
#   "username": "admin",
#   "role": "superadmin"
# }
```

### Using the token
```bash
# Store token in a variable
TOKEN=$(curl -s -X POST http://aio-01:8001/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username": "admin", "password": "changeme"}' | jq -r .access_token)

# Use token with any admin endpoint
curl -H "Authorization: Bearer $TOKEN" http://aio-01:8001/admin/health
```

### Default credentials

On first startup, a default `admin` user is created:
- Username: `admin`
- Password: `changeme` (or value of `ADMIN_API_DEFAULT_PASSWORD` env var)
- Role: `superadmin`

**Change the default password immediately after first login.**

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `ADMIN_API_JWT_SECRET` | Random (regenerated on restart) | JWT signing secret. Set explicitly for token persistence across restarts. |
| `ADMIN_API_TOKEN_EXPIRY_HOURS` | `24` | Token expiration time in hours |
| `ADMIN_API_DEFAULT_PASSWORD` | `changeme` | Default admin password on first startup |
| `DB_PASSWORD` | (empty) | PostgreSQL password |

### Password requirements

- Minimum 8 characters

## Endpoints

### POST /auth/login
Authenticate and receive a JWT token. No auth required.
```bash
curl -X POST http://aio-01:8001/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username": "admin", "password": "yourpassword"}'
```

### POST /admin/users
Create a new admin user. Requires `superadmin` role.
```bash
curl -X POST http://aio-01:8001/admin/users \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"username": "operator", "password": "securepass123", "role": "admin"}'
```

### GET /admin/users
List all admin users. Requires `superadmin` role.
```bash
curl -H "Authorization: Bearer $TOKEN" http://aio-01:8001/admin/users
```

### PUT /admin/users/me/password
Change your own password.
```bash
curl -X PUT http://aio-01:8001/admin/users/me/password \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"current_password": "changeme", "new_password": "newsecurepass123"}'
```

### GET /admin/health
System health check
```bash
curl -H "Authorization: Bearer $TOKEN" http://aio-01:8001/admin/health
```

### GET /admin/stats
Current statistics (models, API usage)
```bash
curl -H "Authorization: Bearer $TOKEN" http://aio-01:8001/admin/stats
```

### POST /admin/maintain-models
Check for new/deprecated models
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" http://aio-01:8001/admin/maintain-models
```

### POST /admin/run-chunking
Trigger chunking process
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" http://aio-01:8001/admin/run-chunking
```

### POST /admin/vacuum-db
Run PostgreSQL VACUUM
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" http://aio-01:8001/admin/vacuum-db
```

### POST /admin/backup-db
Backup PostgreSQL and Neo4j databases
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" http://aio-01:8001/admin/backup-db
```

### GET /admin/tasks/{job_id}
Get background task status
```bash
curl -H "Authorization: Bearer $TOKEN" http://aio-01:8001/admin/tasks/<job_id>
```

### GET /admin/tasks
List recent background tasks
```bash
curl -H "Authorization: Bearer $TOKEN" http://aio-01:8001/admin/tasks
curl -H "Authorization: Bearer $TOKEN" "http://aio-01:8001/admin/tasks?status=running&limit=10"
```

## Database schema

Users are stored in the `admin.users` table:

```sql
CREATE TABLE admin.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,  -- bcrypt
    role VARCHAR(20) NOT NULL DEFAULT 'admin',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);
```

## Deployment

```bash
# Install dependencies on aio-01
ssh root@aio-01 "pip3 install bcrypt PyJWT"

# Set JWT secret (important for production)
ssh root@aio-01 "echo 'ADMIN_API_JWT_SECRET=your-secret-here' >> /etc/default/admin-api"

# Deploy to aio-01
scp admin-api/admin-api.py root@aio-01:/opt/
scp admin-api/admin-api.service root@aio-01:/etc/systemd/system/

ssh root@aio-01 "
  systemctl daemon-reload
  systemctl enable admin-api
  systemctl restart admin-api
"
```

## Updating cron jobs for authentication

Cron jobs on util-ap need to obtain a token first:

```bash
# Example cron script with auth
TOKEN=$(curl -s -X POST http://aio-01:8001/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username": "cron-user", "password": "cron-password"}' | jq -r .access_token)

curl -X POST -H "Authorization: Bearer $TOKEN" http://aio-01:8001/admin/maintain-models
```

## Monitor

```bash
# Service status
ssh root@aio-01 "systemctl status admin-api"

# Logs
ssh root@aio-01 "journalctl -u admin-api -f"

# Test login
curl -X POST http://aio-01:8001/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username": "admin", "password": "changeme"}'
```
