# Document Ingestion API

Production-ready FastAPI service for asynchronous document processing with security hardening, rate limiting, and monitoring.

## Features

- **Security Hardened**: Constant-time API key validation, input sanitization, SQL injection protection
- **Async Processing**: Non-blocking document ingestion with background task queue
- **Rate Limiting**: Per-API-key rate limits with Redis Sentinel backend
- **Monitoring**: Prometheus metrics for throughput, latency, and error rates
- **File Support**: PDF, images (OCR), text, firmware binaries
- **Vector Embeddings**: Automatic semantic chunking and embedding generation

## Architecture

```
Client → NGINX (TLS termination)
       → FastAPI (8000)
       → PostgreSQL (aio-01:5433)
       → Redis Sentinel (HA task queue)
       → Celery Workers (background processing)
```

## Installation

### Prerequisites

```bash
# On aio-01 (API server)
sudo dnf install -y python3.11 python3-pip tesseract redis postgresql-client nginx

# Install system dependencies
sudo dnf install -y libmagic file-devel
```

### Setup

```bash
# Create deployment directory
sudo mkdir -p /opt/document-ingestion-api
sudo chown sfloess:sfloess /opt/document-ingestion-api
cd /opt/document-ingestion-api

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Generate API key
python3 << EOF
import secrets
import bcrypt
api_key = secrets.token_urlsafe(32)
key_hash = bcrypt.hashpw(api_key.encode(), bcrypt.gensalt()).decode()
print(f"API Key: {api_key}")
print(f"Key Hash: {key_hash}")
print(f"Key Prefix: {api_key[:8]}")
EOF

# Store API key in database (see schema.sql)
```

### Database Setup

```bash
# Run DDL on aio-01 PostgreSQL
psql -h aio-01 -p 5433 -U sfloess -d learning -f schema.sql

# Insert API key
psql -h aio-01 -p 5433 -U sfloess -d learning << EOF
INSERT INTO auth.api_keys (key_prefix, key_hash, scopes, rate_limit_per_minute)
VALUES ('YOUR_KEY_PREFIX', 'YOUR_KEY_HASH', ARRAY['ingest:documents'], 100);
EOF
```

### NGINX Configuration

```nginx
# /etc/nginx/conf.d/document-ingestion.conf
upstream document_api {
    server 127.0.0.1:8000;
}

server {
    listen 443 ssl http2;
    server_name aio-01;

    ssl_certificate /etc/pki/tls/certs/aio-01.crt;
    ssl_certificate_key /etc/pki/tls/private/aio-01.key;

    client_max_body_size 100M;

    location / {
        proxy_pass http://document_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Systemd Service

```bash
# Copy service file and start script
sudo cp scripts/document-ingestion-api.service /etc/systemd/system/
sudo cp start.sh /opt/document-ingestion-api/start.sh
sudo chmod +x /opt/document-ingestion-api/start.sh

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable document-ingestion-api
sudo systemctl start document-ingestion-api
```

## Usage

### Client Example

```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "https://aio-01:8000/api/v1/ingest/pdf",
        headers={"X-API-Key": "YOUR_API_KEY"},
        files={"file": open("document.pdf", "rb")},
        data={"metadata": '{"source": "user_upload", "tags": ["firmware"]}'}
    )
    print(response.json())
```

### Testing

```bash
# Run unit tests
./test-api.sh

# Run end-to-end tests
./test-e2e.sh
```

## Monitoring

Prometheus metrics available at `http://aio-01:8000/metrics`:

- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request latency histogram
- `documents_processed_total` - Total documents processed
- `document_processing_duration_seconds` - Processing time histogram
- `embeddings_generated_total` - Total embeddings generated
- `database_errors_total` - Database error count

## Security

- **API Keys**: bcrypt-hashed with constant-time validation
- **Rate Limiting**: Per-key limits enforced by Redis
- **Input Validation**: Magic byte checks, size limits, sanitization
- **SQL Injection**: Parameterized queries only
- **HTTPS**: Required for all external access
- **CORS**: Whitelist-based origin validation

## Deployment Checklist

- [ ] PostgreSQL database schema deployed
- [ ] Redis Sentinel cluster running (3 nodes)
- [ ] API key generated and stored
- [ ] NGINX TLS certificates configured
- [ ] Systemd service enabled
- [ ] Prometheus scraping configured
- [ ] Celery workers started (background tasks)
- [ ] Health check passing: `curl https://aio-01:8000/health`

## Integration with Autostorage

See `shared/auto_storage.py` for DocumentIngestionClient usage:

```python
from auto_storage import DocumentIngestionClient

client = DocumentIngestionClient(
    base_url="https://aio-01:8000",
    api_key=os.getenv("DOCUMENT_INGESTION_API_KEY")
)

async with client:
    result = await client.ingest_pdf("firmware.pdf", metadata={"type": "firmware"})
    print(f"Processed {len(result['chunks'])} chunks")
```

## Troubleshooting

```bash
# Check service status
sudo systemctl status document-ingestion-api

# View logs
sudo journalctl -u document-ingestion-api -f

# Test health endpoint
curl https://aio-01:8000/health

# Check Redis connectivity
redis-cli -h aio-01 -p 26379 sentinel masters

# Check PostgreSQL connectivity
psql -h aio-01 -p 5433 -U sfloess -d learning -c "SELECT COUNT(*) FROM documents.documents"
```

## Performance Tuning

```bash
# Increase file descriptor limits
sudo sysctl -w fs.file-max=2097152

# Tune PostgreSQL connection pool
# Edit settings.py:
# db_pool_max_size = 50

# Add more Celery workers
# celery -A document_ingestion worker --concurrency=8
```

## Implementation Status

**IMPORTANT: This is a security-hardened SKELETON implementation.**

The current file (`document-ingestion-api.py`) contains:
- ✅ Configuration and settings (lines 1-90)
- ✅ Security hardening (constant-time API key validation, lines 91-128)
- ✅ Placeholder implementations for integration (lines 129-167)
- ✅ FastAPI app initialization (lines 169-177)
- ❌ **MISSING: Actual API endpoints** (no routes implemented)

**To complete the implementation, add these endpoints:**

1. **Health and Monitoring**
   - `GET /health` - Health check endpoint
   - `GET /metrics` - Prometheus metrics

2. **Document Ingestion**
   - `POST /api/v1/ingest/pdf` - Upload and process PDF
   - `POST /api/v1/ingest/image` - Upload and OCR image
   - `POST /api/v1/ingest/text` - Upload text document

3. **Search and Retrieval**
   - `POST /api/v1/search/similar` - Semantic similarity search
   - `GET /api/v1/documents/{id}` - Get document by ID

**Integration Required:**
- Replace placeholder functions with actual implementations from:
  - `shared/semantic_chunker.py`
  - `shared/generate-embedding.py`
  - `app/services/file_validator.py`

## TODO

- [ ] **Implement API endpoints** (currently only skeleton)
- [ ] Integrate semantic_chunker.py (replace placeholder)
- [ ] Integrate generate-embedding.py (replace placeholder)
- [ ] Add Celery task queue implementation
- [ ] Add document versioning (deduplication by hash)
- [ ] Add batch ingestion endpoint
- [ ] Add document deletion API
- [ ] Add audit logging
