# Grafana JSON Datasource API - Deployment Guide

## Installation & Deployment Options

### Option 1: Direct Node.js (Development)

**Requirements**:
- Node.js 14+ installed
- `/home/sfloess/.claude/learning/db/learning.db` exists

**Installation**:
```bash
cd /home/sfloess/.claude/learning
npm install
npm start
```

**Output**:
```
Grafana API server running on http://0.0.0.0:3000
Database: /home/sfloess/.claude/learning/db/learning.db

Endpoints:
  REST API:
    GET http://localhost:3000/metrics/lis
    GET http://localhost:3000/metrics/quality
    GET http://localhost:3000/metrics/cost
    GET http://localhost:3000/metrics/discoveries
  Grafana Plugin:
    POST http://localhost:3000/search
    POST http://localhost:3000/query
  Health:
    GET http://localhost:3000/health
```

**Stop Server**:
```bash
# Press Ctrl+C in terminal
# Or: pkill -f "node grafana-api.js"
```

---

### Option 2: systemd Service (Production Linux)

**Installation**:

1. Copy service file:
```bash
sudo cp /home/sfloess/.claude/learning/grafana-api.service /etc/systemd/system/
```

2. Reload systemd daemon:
```bash
sudo systemctl daemon-reload
```

3. Enable and start service:
```bash
sudo systemctl enable grafana-api
sudo systemctl start grafana-api
```

**Verify**:
```bash
sudo systemctl status grafana-api
curl http://localhost:3000/health
```

**Logs**:
```bash
# Real-time logs
sudo journalctl -f -u grafana-api

# Last 50 lines
sudo journalctl -u grafana-api -n 50

# Since service started
sudo journalctl -u grafana-api --since today
```

**Manage**:
```bash
# Restart
sudo systemctl restart grafana-api

# Stop
sudo systemctl stop grafana-api

# Disable
sudo systemctl disable grafana-api
```

---

### Option 3: Docker Container

**Requirements**:
- Docker & Docker Compose installed
- `/home/sfloess/.claude/learning/db/learning.db` exists

**Build & Run**:
```bash
cd /home/sfloess/.claude/learning

# Build image
docker build -t grafana-learning-api .

# Run container
docker run -d \
  --name grafana-api \
  -p 3000:3000 \
  -v $(pwd)/db/learning.db:/app/db/learning.db:ro \
  grafana-learning-api
```

**Or use Docker Compose** (includes Grafana):
```bash
cd /home/sfloess/.claude/learning
docker-compose up -d

# Services:
# - API: http://localhost:3000
# - Grafana: http://localhost:3001
```

**Manage**:
```bash
# Logs
docker logs -f grafana-api

# Stop
docker stop grafana-api

# Remove
docker rm grafana-api

# Full cleanup
docker-compose down
```

---

### Option 4: PM2 Process Manager (Production Node.js)

**Installation**:
```bash
npm install -g pm2
```

**Start**:
```bash
cd /home/sfloess/.claude/learning
pm2 start grafana-api.js --name "grafana-api"
pm2 save
pm2 startup
```

**Verify**:
```bash
pm2 logs grafana-api
pm2 monit
```

**Manage**:
```bash
pm2 restart grafana-api
pm2 stop grafana-api
pm2 delete grafana-api
```

---

### Option 5: Kubernetes Deployment

**Helm Chart Example**:

Create `values.yaml`:
```yaml
image:
  repository: grafana-learning-api
  tag: latest

service:
  type: ClusterIP
  port: 3000

resources:
  requests:
    memory: "128Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "500m"

persistence:
  enabled: true
  path: /app/db/learning.db
  size: 1Gi
```

**Deploy**:
```bash
helm install grafana-api ./helm-chart -f values.yaml
```

---

## Firewall Configuration

### Linux (firewalld)

```bash
# Allow port 3000
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --reload

# Verify
sudo firewall-cmd --list-ports
```

### Linux (ufw)

```bash
# Allow port 3000
sudo ufw allow 3000/tcp
sudo ufw reload

# Verify
sudo ufw status
```

### Windows (PowerShell)

```powershell
New-NetFirewallRule -DisplayName "Grafana API" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 3000
```

---

## Reverse Proxy Configuration

### Nginx

```nginx
upstream grafana_api {
  server localhost:3000;
}

server {
  listen 80;
  server_name metrics.example.com;

  location / {
    proxy_pass http://grafana_api;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # CORS
    add_header 'Access-Control-Allow-Origin' '*' always;
    add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS' always;
    add_header 'Access-Control-Allow-Headers' 'Content-Type' always;
  }
}
```

**Enable**:
```bash
sudo ln -s /etc/nginx/sites-available/grafana-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Apache

```apache
<VirtualHost *:80>
  ServerName metrics.example.com

  ProxyPreserveHost On
  ProxyPass / http://localhost:3000/
  ProxyPassReverse / http://localhost:3000/

  # CORS
  Header always set Access-Control-Allow-Origin "*"
  Header always set Access-Control-Allow-Methods "GET, POST, OPTIONS"
  Header always set Access-Control-Allow-Headers "Content-Type"
</VirtualHost>
```

**Enable**:
```bash
sudo a2enmod proxy
sudo a2enmod headers
sudo a2ensite grafana-api
sudo apache2ctl configtest
sudo systemctl restart apache2
```

---

## SSL/TLS Configuration

### Let's Encrypt (Certbot)

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Generate certificate
sudo certbot certonly --nginx -d metrics.example.com

# Auto-renewal
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

### Self-Signed Certificate

```bash
# Generate
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365

# Use in Node.js
const https = require('https');
const fs = require('fs');

const options = {
  key: fs.readFileSync('key.pem'),
  cert: fs.readFileSync('cert.pem')
};

https.createServer(options, handleRequest).listen(3000);
```

---

## Monitoring & Health Checks

### Systemd Health Check

The systemd service includes automatic restart on failure:
```
Restart=on-failure
RestartSec=10
```

### Health Check Endpoint

```bash
# Check health
curl -f http://localhost:3000/health || echo "Service unhealthy"

# Use in monitoring script
while true; do
  curl -f http://localhost:3000/health > /dev/null 2>&1
  if [ $? -ne 0 ]; then
    echo "Alert: API health check failed"
    # Send alert, restart service, etc.
  fi
  sleep 60
done
```

### Docker Health Check

```bash
docker run \
  --health-cmd='node -e "require(\"http\").get(\"http://localhost:3000/health\", (r) => process.exit(r.statusCode === 200 ? 0 : 1))"' \
  --health-interval=30s \
  --health-timeout=10s \
  --health-retries=3 \
  grafana-api
```

### Prometheus Metrics (Optional)

To add Prometheus support, expose metrics endpoint:
```javascript
// Add to grafana-api.js
app.get('/metrics', (req, res) => {
  res.setHeader('Content-Type', 'text/plain');
  res.end(`
# HELP api_requests_total Total API requests
# TYPE api_requests_total counter
api_requests_total{endpoint="/metrics/lis"} 1250

# HELP api_response_time_ms Response time in milliseconds
# TYPE api_response_time_ms histogram
api_response_time_ms{endpoint="/metrics/lis"} 45
  `);
});
```

---

## Performance Tuning

### Database Optimization

```bash
# Connect to database
sqlite3 /home/sfloess/.claude/learning/db/learning.db

# Analyze query performance
ANALYZE;

# Rebuild database
VACUUM;

# Check index usage
SELECT * FROM sqlite_stat1;
```

### Node.js Optimization

**Memory**:
```bash
# Run with increased memory limit
node --max-old-space-size=4096 grafana-api.js
```

**CPU**:
```bash
# Use clustering for multi-core
npm install cluster
# Then use: require('cluster')
```

### Caching Layer

Add Redis caching:
```bash
npm install redis

# In grafana-api.js
const redis = require('redis');
const client = redis.createClient();

// Cache LIS metrics for 30 seconds
async function getLISMetrics() {
  const cached = await client.get('lis_metrics');
  if (cached) return JSON.parse(cached);
  
  const metrics = await dbQuery(...);
  await client.setex('lis_metrics', 30, JSON.stringify(metrics));
  return metrics;
}
```

---

## Backup & Recovery

### Database Backup

```bash
# Daily backup script
#!/bin/bash
BACKUP_DIR="/home/sfloess/.claude/learning/backups"
mkdir -p $BACKUP_DIR
cp /home/sfloess/.claude/learning/db/learning.db \
   $BACKUP_DIR/learning-$(date +%Y%m%d-%H%M%S).db

# Keep only last 7 days
find $BACKUP_DIR -name "learning-*.db" -mtime +7 -delete
```

**Cron Job**:
```bash
# Daily at 2 AM
0 2 * * * /home/sfloess/.claude/learning/backup-db.sh
```

### Database Restore

```bash
# Stop API
sudo systemctl stop grafana-api

# Restore from backup
cp /home/sfloess/.claude/learning/backups/learning-20240613-020000.db \
   /home/sfloess/.claude/learning/db/learning.db

# Start API
sudo systemctl start grafana-api

# Verify
curl http://localhost:3000/health
```

---

## Troubleshooting

### Server Won't Start

```bash
# Check if port is already in use
lsof -i :3000

# Kill existing process
kill -9 <PID>

# Try different port
PORT=3001 node grafana-api.js
```

### Database Connection Error

```bash
# Verify database exists
ls -la /home/sfloess/.claude/learning/db/learning.db

# Check permissions
stat /home/sfloess/.claude/learning/db/learning.db

# Test with sqlite3
sqlite3 /home/sfloess/.claude/learning/db/learning.db "SELECT COUNT(*) FROM execution_log;"
```

### Slow Queries

```bash
# Check query plans
sqlite3 /home/sfloess/.claude/learning/db/learning.db
EXPLAIN QUERY PLAN SELECT ...;

# Rebuild indexes
REINDEX;
VACUUM;
ANALYZE;
```

### High Memory Usage

```bash
# Monitor memory
watch -n 1 'ps aux | grep grafana-api'

# Check for memory leaks
node --inspect grafana-api.js
# Then visit chrome://inspect in Chrome DevTools
```

---

## Scaling

### Horizontal Scaling

For multiple API instances, use load balancer:

**HAProxy**:
```
global
  daemon

defaults
  mode http

frontend api-frontend
  bind *:80
  default_backend api-backend

backend api-backend
  balance roundrobin
  server api1 localhost:3001
  server api2 localhost:3002
  server api3 localhost:3003
```

### Database Sharding

For very large datasets:
- Split execution_log by date ranges
- Query across multiple databases
- Aggregate results in application

---

## Production Checklist

- [ ] Database backup automation configured
- [ ] Firewall rules set up
- [ ] Reverse proxy configured with SSL
- [ ] systemd service installed and enabled
- [ ] Health check monitoring in place
- [ ] Logs configured (rotation, archival)
- [ ] Performance baselines established
- [ ] Alerts configured for anomalies
- [ ] Disaster recovery plan documented
- [ ] Team trained on troubleshooting

---

## Support & Documentation

- **README**: `/home/sfloess/.claude/learning/GRAFANA_API_README.md`
- **API Reference**: `/home/sfloess/.claude/learning/API_REFERENCE.md`
- **Source Code**: `/home/sfloess/.claude/learning/grafana-api.js`
- **Database Schema**: `/home/sfloess/.claude/learning/db/init-learning-db.sql`
- **Example Dashboard**: `/home/sfloess/.claude/learning/example-dashboard.json`

---

## License

Part of the Autonomous AI Learning System.
