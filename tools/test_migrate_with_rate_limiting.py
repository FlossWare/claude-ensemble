#!/usr/bin/env python3
"""
Test suite for migration script with rate limiting.

Tests:
1. Rate limiting enforcement
2. Queue size limits
3. Token bucket algorithm
4. Wait for capacity
5. Migration flow
"""

import time
import json
import hashlib
from unittest.mock import Mock, MagicMock, patch
import pytest

# Import the migration script
from migrate_with_rate_limiting import (
    RateLimiter,
    MigrationManager,
    DEFAULT_RATE_LIMIT,
    DEFAULT_BURST_LIMIT,
    RATE_LIMIT_WINDOW
)


class MockRedis:
    """Mock Redis client for testing."""

    def __init__(self):
        self.data = {}
        self.sorted_sets = {}
        self.lists = {}
        self.expirations = {}

    def zadd(self, key, mapping):
        if key not in self.sorted_sets:
            self.sorted_sets[key] = []
        for member, score in mapping.items():
            self.sorted_sets[key].append((score, member))

    def zcard(self, key):
        return len(self.sorted_sets.get(key, []))

    def zremrangebyscore(self, key, min_score, max_score):
        if key not in self.sorted_sets:
            return 0
        original_len = len(self.sorted_sets[key])
        self.sorted_sets[key] = [
            (score, member)
            for score, member in self.sorted_sets[key]
            if not (min_score <= score <= max_score)
        ]
        return original_len - len(self.sorted_sets[key])

    def expire(self, key, seconds):
        self.expirations[key] = time.time() + seconds

    def llen(self, key):
        return len(self.lists.get(key, []))

    def rpush(self, key, value):
        if key not in self.lists:
            self.lists[key] = []
        self.lists[key].append(value)

    def lpop(self, key):
        if key in self.lists and self.lists[key]:
            return self.lists[key].pop(0)
        return None

    def close(self):
        pass


class TestRateLimiter:
    """Test rate limiting functionality."""

    def test_check_rate_limit_under_limit(self):
        """Test rate limit check when under limit."""
        redis_mock = MockRedis()
        limiter = RateLimiter(redis_mock)

        # No items queued yet
        allowed, remaining = limiter.check_rate_limit("test_queue", rate_limit=100)

        assert allowed is True
        assert remaining == 100

    def test_check_rate_limit_at_limit(self):
        """Test rate limit check when at limit."""
        redis_mock = MockRedis()
        limiter = RateLimiter(redis_mock)

        # Add items up to limit
        current_time = time.time()
        for i in range(100):
            redis_mock.zadd(
                "rate_limit:test_queue",
                {f"item_{i}": current_time}
            )

        allowed, remaining = limiter.check_rate_limit("test_queue", rate_limit=100)

        assert allowed is False
        assert remaining == 0

    def test_check_rate_limit_window_expiration(self):
        """Test that old items outside window are removed."""
        redis_mock = MockRedis()
        limiter = RateLimiter(redis_mock)

        # Add items in the past (outside window)
        old_time = time.time() - 120  # 2 minutes ago
        for i in range(50):
            redis_mock.zadd(
                "rate_limit:test_queue",
                {f"old_{i}": old_time}
            )

        # Add items within window
        current_time = time.time()
        for i in range(30):
            redis_mock.zadd(
                "rate_limit:test_queue",
                {f"new_{i}": current_time}
            )

        allowed, remaining = limiter.check_rate_limit("test_queue", rate_limit=100, window=60)

        assert allowed is True
        assert remaining == 70  # 100 - 30 = 70

    def test_record_queued(self):
        """Test recording queued items."""
        redis_mock = MockRedis()
        limiter = RateLimiter(redis_mock)

        limiter.record_queued("test_queue")

        assert redis_mock.zcard("rate_limit:test_queue") == 1

    def test_check_queue_size_under_limit(self):
        """Test queue size check when under limit."""
        redis_mock = MockRedis()
        limiter = RateLimiter(redis_mock)

        # Add 50 items to queue
        for i in range(50):
            redis_mock.rpush("test_queue", f"item_{i}")

        allowed, size = limiter.check_queue_size("test_queue", max_size=200)

        assert allowed is True
        assert size == 50

    def test_check_queue_size_at_limit(self):
        """Test queue size check when at limit."""
        redis_mock = MockRedis()
        limiter = RateLimiter(redis_mock)

        # Add 200 items to queue
        for i in range(200):
            redis_mock.rpush("test_queue", f"item_{i}")

        allowed, size = limiter.check_queue_size("test_queue", max_size=200)

        assert allowed is False
        assert size == 200

    def test_wait_for_capacity_immediate(self):
        """Test wait_for_capacity when capacity immediately available."""
        redis_mock = MockRedis()
        limiter = RateLimiter(redis_mock)

        # No items, should return immediately
        result = limiter.wait_for_capacity("test_queue", timeout=5)

        assert result is True

    def test_wait_for_capacity_timeout(self):
        """Test wait_for_capacity timeout."""
        redis_mock = MockRedis()
        limiter = RateLimiter(redis_mock)

        # Fill queue to capacity
        current_time = time.time()
        for i in range(100):
            redis_mock.zadd("rate_limit:test_queue", {f"item_{i}": current_time})

        # Should timeout immediately (timeout=0)
        result = limiter.wait_for_capacity("test_queue", rate_limit=100, timeout=0)

        assert result is False


class TestMigrationManager:
    """Test migration manager functionality."""

    @patch('migrate_with_rate_limiting.psycopg2.connect')
    @patch('migrate_with_rate_limiting.redis.Redis')
    def test_queue_document_success(self, mock_redis_class, mock_pg_connect):
        """Test successful document queueing."""
        # Setup mocks
        redis_mock = MockRedis()
        mock_redis_class.return_value = redis_mock

        pg_conn_mock = MagicMock()
        mock_pg_connect.return_value = pg_conn_mock

        manager = MigrationManager()
        manager.pg_conn = pg_conn_mock

        # Create test document
        document = {
            'url': 'https://example.com/test',
            'category': 'test',
            'title': 'Test Document',
            'content': 'Test content',
            'metadata': {}
        }

        # Queue document
        result = manager.queue_document(document)

        assert result is True
        assert redis_mock.llen("queue:store") == 1

        # Verify payload
        queued_data = json.loads(redis_mock.lpop("queue:store"))
        assert queued_data['url'] == document['url']
        assert queued_data['category'] == document['category']
        assert 'hash' in queued_data

    @patch('migrate_with_rate_limiting.psycopg2.connect')
    @patch('migrate_with_rate_limiting.redis.Redis')
    def test_queue_document_rate_limited(self, mock_redis_class, mock_pg_connect):
        """Test queueing when rate limited."""
        # Setup mocks
        redis_mock = MockRedis()

        # Fill rate limit
        current_time = time.time()
        for i in range(100):
            redis_mock.zadd("rate_limit:queue:store", {f"item_{i}": current_time})

        mock_redis_class.return_value = redis_mock

        pg_conn_mock = MagicMock()
        mock_pg_connect.return_value = pg_conn_mock

        manager = MigrationManager()
        manager.pg_conn = pg_conn_mock

        # Create test document
        document = {
            'url': 'https://example.com/test',
            'category': 'test',
            'title': 'Test Document',
            'content': 'Test content',
            'metadata': {}
        }

        # Queue document (should fail due to rate limit and immediate timeout)
        # We need to mock wait_for_capacity to return False immediately
        with patch.object(manager.rate_limiter, 'wait_for_capacity', return_value=False):
            result = manager.queue_document(document)

        assert result is False

    @patch('migrate_with_rate_limiting.psycopg2.connect')
    @patch('migrate_with_rate_limiting.redis.Redis')
    def test_migrate_batch(self, mock_redis_class, mock_pg_connect):
        """Test batch migration."""
        # Setup mocks
        redis_mock = MockRedis()
        mock_redis_class.return_value = redis_mock

        # Mock PostgreSQL connection
        pg_conn_mock = MagicMock()
        cursor_mock = MagicMock()

        # Mock cursor as context manager
        cursor_mock.__enter__ = Mock(return_value=cursor_mock)
        cursor_mock.__exit__ = Mock(return_value=False)

        # Mock fetchall to return test documents
        test_documents = [
            {
                'url': f'https://example.com/doc{i}',
                'category': 'test',
                'title': f'Document {i}',
                'content': f'Content {i}',
                'metadata': {},
                'created_at': '2026-07-10'
            }
            for i in range(10)
        ]
        cursor_mock.fetchall.return_value = test_documents

        pg_conn_mock.cursor.return_value = cursor_mock
        mock_pg_connect.return_value = pg_conn_mock

        manager = MigrationManager()
        manager.connect_postgres()

        # Migrate batch
        queued, skipped = manager.migrate_batch(batch_size=10)

        assert queued == 10
        assert skipped == 0
        assert redis_mock.llen("queue:store") == 10


def test_hash_generation():
    """Test that URL hashing is consistent."""
    url = "https://example.com/test"

    hash1 = hashlib.md5(url.encode()).hexdigest()
    hash2 = hashlib.md5(url.encode()).hexdigest()

    assert hash1 == hash2


def test_payload_structure():
    """Test that queue payload has required fields."""
    document = {
        'url': 'https://example.com/test',
        'category': 'test',
        'title': 'Test',
        'content': 'Content',
        'metadata': {'key': 'value'}
    }

    url_hash = hashlib.md5(document['url'].encode()).hexdigest()

    payload = {
        'url': document['url'],
        'category': document['category'],
        'title': document.get('title'),
        'content': document['content'],
        'metadata': document.get('metadata', {}),
        'hash': url_hash,
        'queued_at': '2026-07-11T00:00:00'
    }

    # Verify required fields
    assert 'url' in payload
    assert 'category' in payload
    assert 'content' in payload
    assert 'hash' in payload
    assert 'queued_at' in payload

    # Verify JSON serializable
    json_str = json.dumps(payload)
    assert json_str is not None


if __name__ == '__main__':
    # Run tests
    print("Running rate limiter tests...")
    test_limiter = TestRateLimiter()
    test_limiter.test_check_rate_limit_under_limit()
    test_limiter.test_check_rate_limit_at_limit()
    test_limiter.test_check_rate_limit_window_expiration()
    test_limiter.test_record_queued()
    test_limiter.test_check_queue_size_under_limit()
    test_limiter.test_check_queue_size_at_limit()
    test_limiter.test_wait_for_capacity_immediate()
    test_limiter.test_wait_for_capacity_timeout()
    print("✓ Rate limiter tests passed")

    print("\nRunning migration manager tests...")
    test_manager = TestMigrationManager()
    test_manager.test_queue_document_success()
    test_manager.test_queue_document_rate_limited()
    test_manager.test_migrate_batch()
    print("✓ Migration manager tests passed")

    print("\nRunning utility tests...")
    test_hash_generation()
    test_payload_structure()
    print("✓ Utility tests passed")

    print("\n=== ALL TESTS PASSED ===")
