#!/bin/bash
# Setup test database for workflow storage integration tests
# Creates a Docker container with PostgreSQL + pgvector extension

set -e

DB_HOST="${TEST_DB_HOST:-localhost}"
DB_PORT="${TEST_DB_PORT:-5433}"
DB_NAME="${TEST_DB_NAME:-learning_test}"
DB_USER="${TEST_DB_USER:-test_user}"
DB_PASSWORD="${TEST_DB_PASSWORD:-test_password}"
CONTAINER_NAME="workflow-storage-test-db"

echo "Setting up test database..."
echo "  Host: $DB_HOST"
echo "  Port: $DB_PORT"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"

# Check if container already exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Removing existing container..."
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
fi

# Start PostgreSQL with pgvector
echo "Starting PostgreSQL container with pgvector..."
docker run -d \
    --name "$CONTAINER_NAME" \
    -e POSTGRES_USER="$DB_USER" \
    -e POSTGRES_PASSWORD="$DB_PASSWORD" \
    -e POSTGRES_DB="$DB_NAME" \
    -p "${DB_PORT}:5432" \
    --health-cmd="pg_isready -U $DB_USER -d $DB_NAME" \
    --health-interval=5s \
    --health-timeout=5s \
    --health-retries=5 \
    pgvector/pgvector:pg15

# Wait for container to be healthy
echo "Waiting for database to be ready..."
for i in {1..30}; do
    if docker exec "$CONTAINER_NAME" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
        echo "✓ Database is ready"
        break
    fi
    echo "  Waiting... ($i/30)"
    sleep 1
done

# Create pgvector extension
echo "Creating pgvector extension..."
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c \
    "CREATE EXTENSION IF NOT EXISTS vector;"

echo "✓ Test database setup complete"
echo ""
echo "Connection string:"
echo "  postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
echo ""
echo "To clean up, run:"
echo "  docker rm -f $CONTAINER_NAME"
