#!/bin/bash
# Document Ingestion API Startup Script
# Place this in /opt/document-ingestion-api/start.sh

set -e

# Activate virtual environment
source /opt/document-ingestion-api/venv/bin/activate

# Start API server
exec uvicorn document-ingestion-api:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --loop uvloop \
    --access-log
