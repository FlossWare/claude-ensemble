#!/usr/bin/env python3
"""
Database Schema Validator for Performance Dashboard
Ensures required tables and columns exist before dashboard operation

Usage:
    from tools.schema_validator import SchemaValidator

    validator = SchemaValidator(host="aio-01", database="learning")
    if not validator.validate_schema():
        print("Schema validation failed")
        sys.exit(1)

    # Safe to proceed with dashboard operations
"""

import psycopg2
from psycopg2 import sql
import logging
import sys
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class SchemaValidator:
    """Validates database schema has all required tables and columns"""

    REQUIRED_TABLES = {
        'workflow.worker_results': [
            'id', 'workflow_id', 'worker_id', 'model', 'task_assigned',
            'outcome', 'quality_score', 'duration_ms', 'input_tokens',
            'output_tokens', 'cost_usd', 'ttft_ms', 'queue_wait_ms',
            'retry_overhead_ms', 'cache_hit', 'created_at', 'updated_at'
        ],
        'workflow.hourly_performance': [
            'id', 'measurement_date', 'hour_of_day', 'executions',
            'successes', 'errors', 'avg_duration_ms', 'success_rate',
            'period_type', 'created_at'
        ],
        'workflow.replays': [
            'id', 'original_workflow_id', 'replayed_at', 'verdict',
            'avg_confidence_delta', 'arbiter_confidence_delta',
            'total_cost_delta', 'notes', 'created_at'
        ],
        'workflow.schema_version': [
            'id', 'migration_name', 'applied_at', 'description'
        ]
    }

    def __init__(self, host: str = "aio-01", port: int = 5433,
                 database: str = "learning", user: str = "claude", password: str = None):
        """Initialize validator with database connection parameters"""
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.conn = None
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def connect(self) -> bool:
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            logger.info(f"Connected to database {self.database} on {self.host}")
            return True
        except psycopg2.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            self.errors.append(f"Database connection failed: {e}")
            return False

    def disconnect(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def table_exists(self, table_name: str) -> bool:
        """Check if table exists in database"""
        try:
            cursor = self.conn.cursor()

            # Parse schema and table name
            parts = table_name.split('.')
            if len(parts) == 2:
                schema, table = parts
            else:
                schema = 'public'
                table = table_name

            query = """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = %s AND table_name = %s
                )
            """
            cursor.execute(query, (schema, table))
            result = cursor.fetchone()[0]
            cursor.close()
            return result
        except psycopg2.Error as e:
            logger.error(f"Error checking table {table_name}: {e}")
            self.errors.append(f"Table check failed for {table_name}: {e}")
            return False

    def column_exists(self, table_name: str, column_name: str) -> bool:
        """Check if column exists in table"""
        try:
            cursor = self.conn.cursor()

            # Parse schema and table name
            parts = table_name.split('.')
            if len(parts) == 2:
                schema, table = parts
            else:
                schema = 'public'
                table = table_name

            query = """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s AND column_name = %s
                )
            """
            cursor.execute(query, (schema, table, column_name))
            result = cursor.fetchone()[0]
            cursor.close()
            return result
        except psycopg2.Error as e:
            logger.error(f"Error checking column {table_name}.{column_name}: {e}")
            self.errors.append(f"Column check failed for {table_name}.{column_name}: {e}")
            return False

    def get_column_type(self, table_name: str, column_name: str) -> Optional[str]:
        """Get data type of column"""
        try:
            cursor = self.conn.cursor()

            # Parse schema and table name
            parts = table_name.split('.')
            if len(parts) == 2:
                schema, table = parts
            else:
                schema = 'public'
                table = table_name

            query = """
                SELECT data_type FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s AND column_name = %s
            """
            cursor.execute(query, (schema, table, column_name))
            result = cursor.fetchone()
            cursor.close()
            return result[0] if result else None
        except psycopg2.Error as e:
            logger.error(f"Error getting column type for {table_name}.{column_name}: {e}")
            return None

    def validate_schema(self) -> bool:
        """
        Validate complete schema

        Returns:
            True if all required tables and columns exist, False otherwise
        """
        if not self.connect():
            return False

        try:
            all_valid = True

            for table_name, required_columns in self.REQUIRED_TABLES.items():
                if not self.table_exists(table_name):
                    self.errors.append(f"Missing required table: {table_name}")
                    all_valid = False
                    continue

                logger.info(f"✓ Table exists: {table_name}")

                # Check required columns
                for column_name in required_columns:
                    if not self.column_exists(table_name, column_name):
                        self.errors.append(
                            f"Missing required column: {table_name}.{column_name}"
                        )
                        all_valid = False
                    else:
                        col_type = self.get_column_type(table_name, column_name)
                        logger.debug(f"  ✓ Column: {column_name} ({col_type})")

            return all_valid

        finally:
            self.disconnect()

    def get_schema_version(self) -> Optional[List[Tuple[str, str]]]:
        """Get list of applied migrations"""
        if not self.connect():
            return None

        try:
            cursor = self.conn.cursor()
            query = """
                SELECT migration_name, applied_at
                FROM workflow.schema_version
                ORDER BY applied_at DESC
            """
            cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            return results
        except psycopg2.Error as e:
            logger.error(f"Error fetching schema versions: {e}")
            return None
        finally:
            self.disconnect()

    def print_report(self):
        """Print validation report"""
        print("\n" + "="*80)
        print("DATABASE SCHEMA VALIDATION REPORT")
        print("="*80 + "\n")

        if self.errors:
            print(f"ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  ✗ {error}")
            print()

        if self.warnings:
            print(f"WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  ⚠ {warning}")
            print()

        if not self.errors and not self.warnings:
            print("✓ Schema validation PASSED\n")

            # Show schema versions
            versions = self.get_schema_version()
            if versions:
                print("Applied Migrations:")
                for migration_name, applied_at in versions:
                    print(f"  • {migration_name} (applied: {applied_at})")
            print()


def main():
    """Command-line interface for schema validation"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate database schema for performance dashboard"
    )
    parser.add_argument('--host', default='aio-01', help='Database host')
    parser.add_argument('--port', type=int, default=5433, help='Database port')
    parser.add_argument('--database', default='learning', help='Database name')
    parser.add_argument('--user', default='claude', help='Database user')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run validation
    validator = SchemaValidator(
        host=args.host,
        port=args.port,
        database=args.database,
        user=args.user
    )

    if validator.validate_schema():
        validator.print_report()
        sys.exit(0)
    else:
        validator.print_report()
        sys.exit(1)


if __name__ == '__main__':
    main()
