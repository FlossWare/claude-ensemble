#!/usr/bin/env python3
"""
Cross-Session Context Inheritance Manager
Stores and retrieves session context in PostgreSQL for continuity across sessions
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent to path for postgres_adapter
sys.path.insert(0, str(Path.home() / '.claude' / 'learning'))

try:
    from postgres_adapter import get_db
except ImportError:
    print("Error: postgres_adapter not found. Make sure it exists in ~/.claude/learning/")
    sys.exit(1)


class SessionContextManager:
    """Manages cross-session context storage and retrieval"""

    def __init__(self):
        """Initialize with PostgreSQL connection"""
        self.db = get_db()
        self._ensure_schema()

    def _ensure_schema(self):
        """Create session_context table if it doesn't exist"""
        # Check if table exists first to avoid permission errors
        try:
            rows = self.db.query("""
                SELECT COUNT(*) as cnt
                FROM information_schema.tables
                WHERE table_name = 'session_context'
            """)
            if rows and rows[0]['cnt'] > 0:
                return  # Table exists, skip creation
        except:
            pass  # Continue to creation if check fails

        # Only try to create if table doesn't exist
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS session_context (
                session_id VARCHAR(255) PRIMARY KEY,
                context_data JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                last_accessed TIMESTAMP DEFAULT NOW(),
                metadata JSONB DEFAULT '{}'::jsonb
            )
        """)

        # Create index for faster lookups
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_context_updated
            ON session_context(updated_at DESC)
        """)

    def save_context(self, session_id: str, context_data: dict, metadata: dict = None):
        """
        Save session context to database

        Args:
            session_id: Unique session identifier
            context_data: Dictionary of context to save (files, tasks, state, etc)
            metadata: Optional metadata (tags, description, etc)

        Returns:
            bool: True if saved successfully
        """
        try:
            self.db.execute("""
                INSERT INTO session_context
                (session_id, context_data, metadata, updated_at, last_accessed)
                VALUES (%s, %s, %s, NOW(), NOW())
                ON CONFLICT (session_id)
                DO UPDATE SET
                    context_data = EXCLUDED.context_data,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW(),
                    last_accessed = NOW()
            """, (session_id, json.dumps(context_data), json.dumps(metadata or {})))

            return True
        except Exception as e:
            print(f"Error saving context: {e}")
            return False

    def load_context(self, session_id: str):
        """
        Load session context from database

        Args:
            session_id: Session identifier to load

        Returns:
            dict or None: Context data if found, None otherwise
        """
        try:
            rows = self.db.query("""
                SELECT context_data, metadata, created_at, updated_at
                FROM session_context
                WHERE session_id = %s
            """, (session_id,))

            if not rows:
                return None

            row = rows[0]

            # Update last_accessed timestamp
            self.db.execute("""
                UPDATE session_context
                SET last_accessed = NOW()
                WHERE session_id = %s
            """, (session_id,))

            return {
                'context': row['context_data'] if isinstance(row['context_data'], dict) else json.loads(row['context_data']),
                'metadata': row['metadata'] if isinstance(row['metadata'], dict) else json.loads(row['metadata']),
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }

        except Exception as e:
            print(f"Error loading context: {e}")
            return None

    def get_recent_sessions(self, limit: int = 10):
        """
        Get most recently updated sessions

        Args:
            limit: Maximum number of sessions to return

        Returns:
            list: List of session info dictionaries
        """
        try:
            rows = self.db.query("""
                SELECT session_id, metadata, updated_at, last_accessed
                FROM session_context
                ORDER BY updated_at DESC
                LIMIT %s
            """, (limit,))

            return [
                {
                    'session_id': row['session_id'],
                    'metadata': row['metadata'] if isinstance(row['metadata'], dict) else json.loads(row['metadata']),
                    'updated_at': row['updated_at'],
                    'last_accessed': row['last_accessed']
                }
                for row in rows
            ]

        except Exception as e:
            print(f"Error getting recent sessions: {e}")
            return []

    def delete_context(self, session_id: str):
        """
        Delete session context

        Args:
            session_id: Session to delete

        Returns:
            bool: True if deleted successfully
        """
        try:
            self.db.execute("""
                DELETE FROM session_context
                WHERE session_id = %s
            """, (session_id,))
            return True
        except Exception as e:
            print(f"Error deleting context: {e}")
            return False

    def cleanup_old_sessions(self, days: int = 30):
        """
        Delete sessions not accessed in the specified number of days

        Args:
            days: Number of days of inactivity before deletion

        Returns:
            int: Number of sessions deleted
        """
        try:
            result = self.db.execute("""
                DELETE FROM session_context
                WHERE last_accessed < NOW() - INTERVAL '%s days'
            """ % days)

            # Get row count from result if available
            return result if isinstance(result, int) else 0

        except Exception as e:
            print(f"Error cleaning up old sessions: {e}")
            return 0


# Example usage
if __name__ == "__main__":
    manager = SessionContextManager()

    # Example 1: Save context
    print("=== Example 1: Save Session Context ===")
    session_id = "test-session-001"
    context = {
        'working_directory': '/home/user/project',
        'open_files': ['main.py', 'utils.py'],
        'current_task': 'Implement login feature',
        'completed_tasks': ['Setup database', 'Create models'],
        'environment': {'PYTHON_VERSION': '3.11', 'DEBUG': True}
    }
    metadata = {
        'project': 'web-app',
        'tags': ['backend', 'authentication']
    }

    success = manager.save_context(session_id, context, metadata)
    print(f"Saved: {success}")
    print()

    # Example 2: Load context
    print("=== Example 2: Load Session Context ===")
    loaded = manager.load_context(session_id)
    if loaded:
        print(f"Context: {json.dumps(loaded['context'], indent=2)}")
        print(f"Metadata: {loaded['metadata']}")
        print(f"Last updated: {loaded['updated_at']}")
    print()

    # Example 3: Get recent sessions
    print("=== Example 3: Recent Sessions ===")
    recent = manager.get_recent_sessions(5)
    for session in recent:
        print(f"- {session['session_id']}: {session['metadata'].get('project', 'unknown')}")
    print()

    # Example 4: Cleanup
    print("=== Example 4: Cleanup Old Sessions ===")
    deleted = manager.cleanup_old_sessions(days=90)
    print(f"Deleted {deleted} old sessions")
