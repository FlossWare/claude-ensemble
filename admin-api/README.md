# Admin REST API

REST API on aio-01:8001 for administrative tasks triggered by util-ap cron jobs.

## Endpoints

### GET /admin/health
System health check
```bash
curl http://aio-01:8001/admin/health
```

### GET /admin/stats
Current statistics (models, API usage)
```bash
curl http://aio-01:8001/admin/stats
```

### POST /admin/maintain-models
Check for new/deprecated models
```bash
curl -X POST http://aio-01:8001/admin/maintain-models
```

### POST /admin/run-chunking
Trigger chunking process
```bash
curl -X POST http://aio-01:8001/admin/run-chunking
```

### POST /admin/vacuum-db
Run PostgreSQL VACUUM
```bash
curl -X POST http://aio-01:8001/admin/vacuum-db
```

## Deployment

```bash
# Deploy to aio-01
scp admin-api/admin-api.py root@aio-01:/opt/
scp admin-api/admin-api.service root@aio-01:/etc/systemd/system/

ssh root@aio-01 "
  systemctl daemon-reload
  systemctl enable admin-api
  systemctl start admin-api
"
```

## Install cron jobs on util-ap

```bash
ssh root@util-ap "crontab -e"
# Add contents of util-ap-crontab.txt
```

## Monitor

```bash
# Service status
ssh root@aio-01 "systemctl status admin-api"

# Logs
ssh root@aio-01 "journalctl -u admin-api -f"

# Test endpoints
curl http://aio-01:8001/admin/health
curl http://aio-01:8001/admin/stats
```
