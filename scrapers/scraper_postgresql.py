#!/usr/bin/env python3
"""PostgreSQL documentation scraper.

Covers:
  - Tutorial: getting started, SQL language, advanced features
  - SQL language: data types, functions, queries, DML, DDL, performance tips
  - Server admin: configuration, backup/recovery, monitoring, WAL, replication, HA
  - Client interfaces: libpq, large objects
  - Internals: system catalogs, query planning, indexing, MVCC, WAL internals
  - Reference: SQL commands (CREATE TABLE, SELECT, INSERT, UPDATE, DELETE, etc.)
  - Extensions: pgvector, PostGIS, pg_stat, contrib modules
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class PostgreSQLScraper(BaseScraper):
    """Scrape PostgreSQL official documentation."""

    SOURCES = {
        "tutorial": {
            "pages": {
                # Part I - Tutorial
                "https://www.postgresql.org/docs/current/tutorial.html": "PostgreSQL Tutorial",
                "https://www.postgresql.org/docs/current/tutorial-start.html": "Getting Started",
                "https://www.postgresql.org/docs/current/tutorial-install.html": "Installation",
                "https://www.postgresql.org/docs/current/tutorial-arch.html": "Architectural Fundamentals",
                "https://www.postgresql.org/docs/current/tutorial-createdb.html": "Creating a Database",
                "https://www.postgresql.org/docs/current/tutorial-accessdb.html": "Accessing a Database",
                "https://www.postgresql.org/docs/current/tutorial-sql.html": "The SQL Language",
                "https://www.postgresql.org/docs/current/tutorial-concepts.html": "Concepts",
                "https://www.postgresql.org/docs/current/tutorial-table.html": "Creating a New Table",
                "https://www.postgresql.org/docs/current/tutorial-populate.html": "Populating a Table with Rows",
                "https://www.postgresql.org/docs/current/tutorial-select.html": "Querying a Table",
                "https://www.postgresql.org/docs/current/tutorial-join.html": "Joins Between Tables",
                "https://www.postgresql.org/docs/current/tutorial-agg.html": "Aggregate Functions",
                "https://www.postgresql.org/docs/current/tutorial-update.html": "Updates",
                "https://www.postgresql.org/docs/current/tutorial-delete.html": "Deletions",
                "https://www.postgresql.org/docs/current/tutorial-advanced.html": "Advanced Features",
                "https://www.postgresql.org/docs/current/tutorial-views.html": "Views",
                "https://www.postgresql.org/docs/current/tutorial-fk.html": "Foreign Keys",
                "https://www.postgresql.org/docs/current/tutorial-transactions.html": "Transactions",
                "https://www.postgresql.org/docs/current/tutorial-window.html": "Window Functions",
                "https://www.postgresql.org/docs/current/tutorial-inheritance.html": "Inheritance",
            },
        },
        "sql-language": {
            "pages": {
                # Part II - The SQL Language
                "https://www.postgresql.org/docs/current/sql.html": "The SQL Language",
                "https://www.postgresql.org/docs/current/sql-syntax.html": "SQL Syntax",
                "https://www.postgresql.org/docs/current/sql-syntax-lexical.html": "Lexical Structure",
                "https://www.postgresql.org/docs/current/sql-expressions.html": "Value Expressions",
                "https://www.postgresql.org/docs/current/sql-syntax-calling-funcs.html": "Calling Functions",
                # Data Definition
                "https://www.postgresql.org/docs/current/ddl.html": "Data Definition",
                "https://www.postgresql.org/docs/current/ddl-basics.html": "Table Basics",
                "https://www.postgresql.org/docs/current/ddl-default.html": "Default Values",
                "https://www.postgresql.org/docs/current/ddl-generated-columns.html": "Generated Columns",
                "https://www.postgresql.org/docs/current/ddl-constraints.html": "Constraints",
                "https://www.postgresql.org/docs/current/ddl-system-columns.html": "System Columns",
                "https://www.postgresql.org/docs/current/ddl-alter.html": "Modifying Tables",
                "https://www.postgresql.org/docs/current/ddl-priv.html": "Privileges",
                "https://www.postgresql.org/docs/current/ddl-rowsecurity.html": "Row Security Policies",
                "https://www.postgresql.org/docs/current/ddl-schemas.html": "Schemas",
                "https://www.postgresql.org/docs/current/ddl-inherit.html": "Inheritance",
                "https://www.postgresql.org/docs/current/ddl-partitioning.html": "Table Partitioning",
                "https://www.postgresql.org/docs/current/ddl-foreign-data.html": "Foreign Data",
                # Data Manipulation
                "https://www.postgresql.org/docs/current/dml.html": "Data Manipulation",
                "https://www.postgresql.org/docs/current/dml-insert.html": "Inserting Data",
                "https://www.postgresql.org/docs/current/dml-update.html": "Updating Data",
                "https://www.postgresql.org/docs/current/dml-delete.html": "Deleting Data",
                "https://www.postgresql.org/docs/current/dml-returning.html": "Returning Data from Modified Rows",
                # Queries
                "https://www.postgresql.org/docs/current/queries.html": "Queries",
                "https://www.postgresql.org/docs/current/queries-overview.html": "Overview",
                "https://www.postgresql.org/docs/current/queries-table-expressions.html": "Table Expressions",
                "https://www.postgresql.org/docs/current/queries-select-lists.html": "Select Lists",
                "https://www.postgresql.org/docs/current/queries-union.html": "Combining Queries",
                "https://www.postgresql.org/docs/current/queries-order.html": "Sorting Rows",
                "https://www.postgresql.org/docs/current/queries-limit.html": "LIMIT and OFFSET",
                "https://www.postgresql.org/docs/current/queries-values.html": "VALUES Lists",
                "https://www.postgresql.org/docs/current/queries-with.html": "WITH Queries (Common Table Expressions)",
                # Data Types
                "https://www.postgresql.org/docs/current/datatype.html": "Data Types",
                "https://www.postgresql.org/docs/current/datatype-numeric.html": "Numeric Types",
                "https://www.postgresql.org/docs/current/datatype-money.html": "Monetary Types",
                "https://www.postgresql.org/docs/current/datatype-character.html": "Character Types",
                "https://www.postgresql.org/docs/current/datatype-binary.html": "Binary Data Types",
                "https://www.postgresql.org/docs/current/datatype-datetime.html": "Date/Time Types",
                "https://www.postgresql.org/docs/current/datatype-boolean.html": "Boolean Type",
                "https://www.postgresql.org/docs/current/datatype-enum.html": "Enumerated Types",
                "https://www.postgresql.org/docs/current/datatype-geometric.html": "Geometric Types",
                "https://www.postgresql.org/docs/current/datatype-net-types.html": "Network Address Types",
                "https://www.postgresql.org/docs/current/datatype-bit.html": "Bit String Types",
                "https://www.postgresql.org/docs/current/datatype-textsearch.html": "Text Search Types",
                "https://www.postgresql.org/docs/current/datatype-uuid.html": "UUID Type",
                "https://www.postgresql.org/docs/current/datatype-xml.html": "XML Type",
                "https://www.postgresql.org/docs/current/datatype-json.html": "JSON Types",
                "https://www.postgresql.org/docs/current/arrays.html": "Arrays",
                "https://www.postgresql.org/docs/current/rowtypes.html": "Composite Types",
                "https://www.postgresql.org/docs/current/rangetypes.html": "Range Types",
                "https://www.postgresql.org/docs/current/domains.html": "Domain Types",
                # Functions and Operators
                "https://www.postgresql.org/docs/current/functions.html": "Functions and Operators",
                "https://www.postgresql.org/docs/current/functions-comparison.html": "Comparison Functions and Operators",
                "https://www.postgresql.org/docs/current/functions-math.html": "Mathematical Functions and Operators",
                "https://www.postgresql.org/docs/current/functions-string.html": "String Functions and Operators",
                "https://www.postgresql.org/docs/current/functions-binarystring.html": "Binary String Functions and Operators",
                "https://www.postgresql.org/docs/current/functions-bitstring.html": "Bit String Functions and Operators",
                "https://www.postgresql.org/docs/current/functions-matching.html": "Pattern Matching",
                "https://www.postgresql.org/docs/current/functions-formatting.html": "Data Type Formatting Functions",
                "https://www.postgresql.org/docs/current/functions-datetime.html": "Date/Time Functions and Operators",
                "https://www.postgresql.org/docs/current/functions-enum.html": "Enum Support Functions",
                "https://www.postgresql.org/docs/current/functions-geometry.html": "Geometric Functions and Operators",
                "https://www.postgresql.org/docs/current/functions-net.html": "Network Address Functions and Operators",
                "https://www.postgresql.org/docs/current/functions-textsearch.html": "Text Search Functions and Operators",
                "https://www.postgresql.org/docs/current/functions-json.html": "JSON Functions and Operators",
                "https://www.postgresql.org/docs/current/functions-sequence.html": "Sequence Manipulation Functions",
                "https://www.postgresql.org/docs/current/functions-conditional.html": "Conditional Expressions",
                "https://www.postgresql.org/docs/current/functions-array.html": "Array Functions and Operators",
                "https://www.postgresql.org/docs/current/functions-range.html": "Range/Multirange Functions and Operators",
                "https://www.postgresql.org/docs/current/functions-aggregate.html": "Aggregate Functions",
                "https://www.postgresql.org/docs/current/functions-window.html": "Window Functions",
                "https://www.postgresql.org/docs/current/functions-subquery.html": "Subquery Expressions",
                "https://www.postgresql.org/docs/current/functions-trigger.html": "Trigger Functions",
                "https://www.postgresql.org/docs/current/functions-info.html": "System Information Functions",
                "https://www.postgresql.org/docs/current/functions-admin.html": "System Administration Functions",
                # Type Conversion
                "https://www.postgresql.org/docs/current/typeconv.html": "Type Conversion",
                # Indexes
                "https://www.postgresql.org/docs/current/indexes.html": "Indexes",
                "https://www.postgresql.org/docs/current/indexes-intro.html": "Introduction to Indexes",
                "https://www.postgresql.org/docs/current/indexes-types.html": "Index Types",
                "https://www.postgresql.org/docs/current/indexes-multicolumn.html": "Multicolumn Indexes",
                "https://www.postgresql.org/docs/current/indexes-ordering.html": "Indexes and ORDER BY",
                "https://www.postgresql.org/docs/current/indexes-unique.html": "Unique Indexes",
                "https://www.postgresql.org/docs/current/indexes-expressional.html": "Indexes on Expressions",
                "https://www.postgresql.org/docs/current/indexes-partial.html": "Partial Indexes",
                "https://www.postgresql.org/docs/current/indexes-examine.html": "Examining Index Usage",
                # Full Text Search
                "https://www.postgresql.org/docs/current/textsearch.html": "Full Text Search",
                "https://www.postgresql.org/docs/current/textsearch-intro.html": "Introduction to Full Text Search",
                "https://www.postgresql.org/docs/current/textsearch-tables.html": "Tables and Indexes",
                "https://www.postgresql.org/docs/current/textsearch-controls.html": "Controlling Text Search",
                # Concurrency Control
                "https://www.postgresql.org/docs/current/mvcc.html": "Concurrency Control",
                "https://www.postgresql.org/docs/current/mvcc-intro.html": "Introduction to MVCC",
                "https://www.postgresql.org/docs/current/transaction-iso.html": "Transaction Isolation",
                "https://www.postgresql.org/docs/current/explicit-locking.html": "Explicit Locking",
                "https://www.postgresql.org/docs/current/applevel-consistency.html": "Data Consistency Checks",
                # Performance Tips
                "https://www.postgresql.org/docs/current/performance-tips.html": "Performance Tips",
                "https://www.postgresql.org/docs/current/using-explain.html": "Using EXPLAIN",
                "https://www.postgresql.org/docs/current/planner-stats.html": "Statistics Used by the Planner",
                "https://www.postgresql.org/docs/current/explicit-joins.html": "Controlling the Planner with Explicit JOIN",
                "https://www.postgresql.org/docs/current/populate.html": "Populating a Database",
                "https://www.postgresql.org/docs/current/non-durability.html": "Non-Durable Settings",
                # Parallel Query
                "https://www.postgresql.org/docs/current/parallel-query.html": "Parallel Query",
            },
        },
        "server-admin": {
            "pages": {
                # Part III - Server Administration
                "https://www.postgresql.org/docs/current/admin.html": "Server Administration",
                # Installation
                "https://www.postgresql.org/docs/current/installation.html": "Installation from Source Code",
                "https://www.postgresql.org/docs/current/install-short.html": "Short Version",
                # Server Setup and Operation
                "https://www.postgresql.org/docs/current/runtime.html": "Server Setup and Operation",
                "https://www.postgresql.org/docs/current/creating-cluster.html": "Creating a Database Cluster",
                "https://www.postgresql.org/docs/current/server-start.html": "Starting the Database Server",
                "https://www.postgresql.org/docs/current/kernel-resources.html": "Kernel Resources",
                "https://www.postgresql.org/docs/current/server-shutdown.html": "Shutting Down the Server",
                "https://www.postgresql.org/docs/current/upgrading.html": "Upgrading a PostgreSQL Cluster",
                "https://www.postgresql.org/docs/current/pgupgrade.html": "pg_upgrade",
                # Server Configuration
                "https://www.postgresql.org/docs/current/runtime-config.html": "Server Configuration",
                "https://www.postgresql.org/docs/current/runtime-config-file-locations.html": "File Locations",
                "https://www.postgresql.org/docs/current/runtime-config-connection.html": "Connections and Authentication",
                "https://www.postgresql.org/docs/current/runtime-config-resource.html": "Resource Consumption",
                "https://www.postgresql.org/docs/current/runtime-config-wal.html": "Write Ahead Log",
                "https://www.postgresql.org/docs/current/runtime-config-replication.html": "Replication",
                "https://www.postgresql.org/docs/current/runtime-config-query.html": "Query Planning",
                "https://www.postgresql.org/docs/current/runtime-config-logging.html": "Error Reporting and Logging",
                "https://www.postgresql.org/docs/current/runtime-config-statistics.html": "Run-time Statistics",
                "https://www.postgresql.org/docs/current/runtime-config-autovacuum.html": "Automatic Vacuuming",
                "https://www.postgresql.org/docs/current/runtime-config-client.html": "Client Connection Defaults",
                "https://www.postgresql.org/docs/current/runtime-config-locks.html": "Lock Management",
                "https://www.postgresql.org/docs/current/runtime-config-compatible.html": "Version and Platform Compatibility",
                # Client Authentication
                "https://www.postgresql.org/docs/current/client-authentication.html": "Client Authentication",
                "https://www.postgresql.org/docs/current/auth-pg-hba-conf.html": "The pg_hba.conf File",
                "https://www.postgresql.org/docs/current/auth-password.html": "Password Authentication",
                "https://www.postgresql.org/docs/current/auth-cert.html": "Certificate Authentication",
                # Database Roles
                "https://www.postgresql.org/docs/current/user-manag.html": "Database Roles",
                "https://www.postgresql.org/docs/current/role-attributes.html": "Role Attributes",
                "https://www.postgresql.org/docs/current/role-membership.html": "Role Membership",
                "https://www.postgresql.org/docs/current/predefined-roles.html": "Predefined Roles",
                # Managing Databases
                "https://www.postgresql.org/docs/current/managing-databases.html": "Managing Databases",
                "https://www.postgresql.org/docs/current/manage-ag-createdb.html": "Creating a Database",
                "https://www.postgresql.org/docs/current/manage-ag-tablespaces.html": "Tablespaces",
                # Localization
                "https://www.postgresql.org/docs/current/charset.html": "Localization",
                "https://www.postgresql.org/docs/current/locale.html": "Locale Support",
                "https://www.postgresql.org/docs/current/multibyte.html": "Character Set Support",
                # Routine Database Maintenance
                "https://www.postgresql.org/docs/current/maintenance.html": "Routine Database Maintenance Tasks",
                "https://www.postgresql.org/docs/current/routine-vacuuming.html": "Routine Vacuuming",
                "https://www.postgresql.org/docs/current/routine-reindex.html": "Routine Reindexing",
                "https://www.postgresql.org/docs/current/logfile-maintenance.html": "Log File Maintenance",
                # Backup and Restore
                "https://www.postgresql.org/docs/current/backup.html": "Backup and Restore",
                "https://www.postgresql.org/docs/current/backup-dump.html": "SQL Dump",
                "https://www.postgresql.org/docs/current/backup-file.html": "File System Level Backup",
                "https://www.postgresql.org/docs/current/continuous-archiving.html": "Continuous Archiving and PITR",
                # High Availability
                "https://www.postgresql.org/docs/current/high-availability.html": "High Availability, Load Balancing, and Replication",
                "https://www.postgresql.org/docs/current/warm-standby.html": "Log-Shipping Standby Servers",
                "https://www.postgresql.org/docs/current/hot-standby.html": "Hot Standby",
                # Monitoring
                "https://www.postgresql.org/docs/current/monitoring.html": "Monitoring Database Activity",
                "https://www.postgresql.org/docs/current/monitoring-stats.html": "The Cumulative Statistics System",
                "https://www.postgresql.org/docs/current/monitoring-locks.html": "Viewing Locks",
                "https://www.postgresql.org/docs/current/dynamic-trace.html": "Dynamic Tracing",
                # Disk Usage
                "https://www.postgresql.org/docs/current/diskusage.html": "Monitoring Disk Usage",
                # Reliability and WAL
                "https://www.postgresql.org/docs/current/wal.html": "Reliability and the Write-Ahead Log",
                "https://www.postgresql.org/docs/current/wal-reliability.html": "Reliability",
                "https://www.postgresql.org/docs/current/wal-async-commit.html": "Asynchronous Commit",
                "https://www.postgresql.org/docs/current/wal-configuration.html": "WAL Configuration",
                "https://www.postgresql.org/docs/current/wal-internals.html": "WAL Internals",
                # Logical Replication
                "https://www.postgresql.org/docs/current/logical-replication.html": "Logical Replication",
                "https://www.postgresql.org/docs/current/logical-replication-publication.html": "Publication",
                "https://www.postgresql.org/docs/current/logical-replication-subscription.html": "Subscription",
                "https://www.postgresql.org/docs/current/logical-replication-conflicts.html": "Conflicts",
            },
        },
        "client-interfaces": {
            "pages": {
                # Client Interfaces
                "https://www.postgresql.org/docs/current/libpq.html": "libpq - C Library",
                "https://www.postgresql.org/docs/current/libpq-connect.html": "Database Connection Control Functions",
                "https://www.postgresql.org/docs/current/libpq-status.html": "Connection Status Functions",
                "https://www.postgresql.org/docs/current/libpq-exec.html": "Command Execution Functions",
                "https://www.postgresql.org/docs/current/libpq-async.html": "Asynchronous Command Processing",
                "https://www.postgresql.org/docs/current/libpq-copy.html": "Functions for COPY",
                "https://www.postgresql.org/docs/current/libpq-envars.html": "Environment Variables",
                "https://www.postgresql.org/docs/current/lo.html": "Large Objects",
                "https://www.postgresql.org/docs/current/lo-interfaces.html": "Client Interfaces for Large Objects",
                # ECPG
                "https://www.postgresql.org/docs/current/ecpg.html": "ECPG - Embedded SQL in C",
                # Information Schema
                "https://www.postgresql.org/docs/current/information-schema.html": "The Information Schema",
            },
        },
        "internals": {
            "pages": {
                # Part VII - Internals
                "https://www.postgresql.org/docs/current/internals.html": "Internals",
                "https://www.postgresql.org/docs/current/overview.html": "Overview of PostgreSQL Internals",
                "https://www.postgresql.org/docs/current/connect-estab.html": "How Connections Are Established",
                "https://www.postgresql.org/docs/current/parser-stage.html": "The Parser Stage",
                "https://www.postgresql.org/docs/current/rule-system.html": "The PostgreSQL Rule System",
                "https://www.postgresql.org/docs/current/planner-optimizer.html": "Planner/Optimizer",
                "https://www.postgresql.org/docs/current/executor.html": "Executor",
                # System Catalogs
                "https://www.postgresql.org/docs/current/catalogs.html": "System Catalogs",
                "https://www.postgresql.org/docs/current/catalog-pg-class.html": "pg_class",
                "https://www.postgresql.org/docs/current/catalog-pg-attribute.html": "pg_attribute",
                "https://www.postgresql.org/docs/current/catalog-pg-index.html": "pg_index",
                "https://www.postgresql.org/docs/current/catalog-pg-namespace.html": "pg_namespace",
                "https://www.postgresql.org/docs/current/catalog-pg-type.html": "pg_type",
                "https://www.postgresql.org/docs/current/catalog-pg-proc.html": "pg_proc",
                "https://www.postgresql.org/docs/current/catalog-pg-trigger.html": "pg_trigger",
                "https://www.postgresql.org/docs/current/catalog-pg-constraint.html": "pg_constraint",
                "https://www.postgresql.org/docs/current/catalog-pg-statistic.html": "pg_statistic",
                "https://www.postgresql.org/docs/current/views.html": "System Views",
                "https://www.postgresql.org/docs/current/view-pg-stats.html": "pg_stats",
                "https://www.postgresql.org/docs/current/view-pg-locks.html": "pg_locks",
                "https://www.postgresql.org/docs/current/view-pg-stat-activity.html": "pg_stat_activity",
                "https://www.postgresql.org/docs/current/view-pg-stat-all-tables.html": "pg_stat_all_tables",
                # Storage
                "https://www.postgresql.org/docs/current/storage.html": "Database Physical Storage",
                "https://www.postgresql.org/docs/current/storage-page-layout.html": "Database Page Layout",
                "https://www.postgresql.org/docs/current/storage-toast.html": "TOAST",
                # Index Access Method
                "https://www.postgresql.org/docs/current/indexam.html": "Index Access Method Interface Definition",
                "https://www.postgresql.org/docs/current/btree.html": "B-Tree Indexes",
                "https://www.postgresql.org/docs/current/hash-index.html": "Hash Indexes",
                "https://www.postgresql.org/docs/current/gist.html": "GiST Indexes",
                "https://www.postgresql.org/docs/current/spgist.html": "SP-GiST Indexes",
                "https://www.postgresql.org/docs/current/gin.html": "GIN Indexes",
                "https://www.postgresql.org/docs/current/brin.html": "BRIN Indexes",
                # GiST and GIN details
                "https://www.postgresql.org/docs/current/gist-extensibility.html": "GiST Extensibility",
                "https://www.postgresql.org/docs/current/gin-extensibility.html": "GIN Extensibility",
            },
        },
        "sql-commands": {
            "pages": {
                # SQL Commands Reference
                "https://www.postgresql.org/docs/current/sql-commands.html": "SQL Commands",
                "https://www.postgresql.org/docs/current/sql-abort.html": "ABORT",
                "https://www.postgresql.org/docs/current/sql-alteraggregate.html": "ALTER AGGREGATE",
                "https://www.postgresql.org/docs/current/sql-alterdatabase.html": "ALTER DATABASE",
                "https://www.postgresql.org/docs/current/sql-alterdefaultprivileges.html": "ALTER DEFAULT PRIVILEGES",
                "https://www.postgresql.org/docs/current/sql-alterextension.html": "ALTER EXTENSION",
                "https://www.postgresql.org/docs/current/sql-alterfunction.html": "ALTER FUNCTION",
                "https://www.postgresql.org/docs/current/sql-altergroup.html": "ALTER GROUP",
                "https://www.postgresql.org/docs/current/sql-alterindex.html": "ALTER INDEX",
                "https://www.postgresql.org/docs/current/sql-altermaterializedview.html": "ALTER MATERIALIZED VIEW",
                "https://www.postgresql.org/docs/current/sql-alterrole.html": "ALTER ROLE",
                "https://www.postgresql.org/docs/current/sql-alterschema.html": "ALTER SCHEMA",
                "https://www.postgresql.org/docs/current/sql-altersequence.html": "ALTER SEQUENCE",
                "https://www.postgresql.org/docs/current/sql-altertable.html": "ALTER TABLE",
                "https://www.postgresql.org/docs/current/sql-altertablespace.html": "ALTER TABLESPACE",
                "https://www.postgresql.org/docs/current/sql-altertrigger.html": "ALTER TRIGGER",
                "https://www.postgresql.org/docs/current/sql-altertype.html": "ALTER TYPE",
                "https://www.postgresql.org/docs/current/sql-alteruser.html": "ALTER USER",
                "https://www.postgresql.org/docs/current/sql-alterview.html": "ALTER VIEW",
                "https://www.postgresql.org/docs/current/sql-analyze.html": "ANALYZE",
                "https://www.postgresql.org/docs/current/sql-begin.html": "BEGIN",
                "https://www.postgresql.org/docs/current/sql-cluster.html": "CLUSTER",
                "https://www.postgresql.org/docs/current/sql-comment.html": "COMMENT",
                "https://www.postgresql.org/docs/current/sql-commit.html": "COMMIT",
                "https://www.postgresql.org/docs/current/sql-copy.html": "COPY",
                "https://www.postgresql.org/docs/current/sql-createaggregate.html": "CREATE AGGREGATE",
                "https://www.postgresql.org/docs/current/sql-createdatabase.html": "CREATE DATABASE",
                "https://www.postgresql.org/docs/current/sql-createextension.html": "CREATE EXTENSION",
                "https://www.postgresql.org/docs/current/sql-createfunction.html": "CREATE FUNCTION",
                "https://www.postgresql.org/docs/current/sql-creategroup.html": "CREATE GROUP",
                "https://www.postgresql.org/docs/current/sql-createindex.html": "CREATE INDEX",
                "https://www.postgresql.org/docs/current/sql-creatematerializedview.html": "CREATE MATERIALIZED VIEW",
                "https://www.postgresql.org/docs/current/sql-createprocedure.html": "CREATE PROCEDURE",
                "https://www.postgresql.org/docs/current/sql-createpublication.html": "CREATE PUBLICATION",
                "https://www.postgresql.org/docs/current/sql-createrole.html": "CREATE ROLE",
                "https://www.postgresql.org/docs/current/sql-createschema.html": "CREATE SCHEMA",
                "https://www.postgresql.org/docs/current/sql-createsequence.html": "CREATE SEQUENCE",
                "https://www.postgresql.org/docs/current/sql-createsubscription.html": "CREATE SUBSCRIPTION",
                "https://www.postgresql.org/docs/current/sql-createtable.html": "CREATE TABLE",
                "https://www.postgresql.org/docs/current/sql-createtableas.html": "CREATE TABLE AS",
                "https://www.postgresql.org/docs/current/sql-createtablespace.html": "CREATE TABLESPACE",
                "https://www.postgresql.org/docs/current/sql-createtrigger.html": "CREATE TRIGGER",
                "https://www.postgresql.org/docs/current/sql-createtype.html": "CREATE TYPE",
                "https://www.postgresql.org/docs/current/sql-createuser.html": "CREATE USER",
                "https://www.postgresql.org/docs/current/sql-createview.html": "CREATE VIEW",
                "https://www.postgresql.org/docs/current/sql-deallocate.html": "DEALLOCATE",
                "https://www.postgresql.org/docs/current/sql-declare.html": "DECLARE",
                "https://www.postgresql.org/docs/current/sql-delete.html": "DELETE",
                "https://www.postgresql.org/docs/current/sql-do.html": "DO",
                "https://www.postgresql.org/docs/current/sql-drop-owned.html": "DROP OWNED",
                "https://www.postgresql.org/docs/current/sql-dropaggregate.html": "DROP AGGREGATE",
                "https://www.postgresql.org/docs/current/sql-dropdatabase.html": "DROP DATABASE",
                "https://www.postgresql.org/docs/current/sql-dropextension.html": "DROP EXTENSION",
                "https://www.postgresql.org/docs/current/sql-dropfunction.html": "DROP FUNCTION",
                "https://www.postgresql.org/docs/current/sql-dropindex.html": "DROP INDEX",
                "https://www.postgresql.org/docs/current/sql-dropmaterializedview.html": "DROP MATERIALIZED VIEW",
                "https://www.postgresql.org/docs/current/sql-droprole.html": "DROP ROLE",
                "https://www.postgresql.org/docs/current/sql-dropschema.html": "DROP SCHEMA",
                "https://www.postgresql.org/docs/current/sql-dropsequence.html": "DROP SEQUENCE",
                "https://www.postgresql.org/docs/current/sql-droptable.html": "DROP TABLE",
                "https://www.postgresql.org/docs/current/sql-droptrigger.html": "DROP TRIGGER",
                "https://www.postgresql.org/docs/current/sql-droptype.html": "DROP TYPE",
                "https://www.postgresql.org/docs/current/sql-dropuser.html": "DROP USER",
                "https://www.postgresql.org/docs/current/sql-dropview.html": "DROP VIEW",
                "https://www.postgresql.org/docs/current/sql-end.html": "END",
                "https://www.postgresql.org/docs/current/sql-execute.html": "EXECUTE",
                "https://www.postgresql.org/docs/current/sql-explain.html": "EXPLAIN",
                "https://www.postgresql.org/docs/current/sql-fetch.html": "FETCH",
                "https://www.postgresql.org/docs/current/sql-grant.html": "GRANT",
                "https://www.postgresql.org/docs/current/sql-insert.html": "INSERT",
                "https://www.postgresql.org/docs/current/sql-listen.html": "LISTEN",
                "https://www.postgresql.org/docs/current/sql-lock.html": "LOCK",
                "https://www.postgresql.org/docs/current/sql-move.html": "MOVE",
                "https://www.postgresql.org/docs/current/sql-notify.html": "NOTIFY",
                "https://www.postgresql.org/docs/current/sql-prepare.html": "PREPARE",
                "https://www.postgresql.org/docs/current/sql-reassign-owned.html": "REASSIGN OWNED",
                "https://www.postgresql.org/docs/current/sql-refreshmaterializedview.html": "REFRESH MATERIALIZED VIEW",
                "https://www.postgresql.org/docs/current/sql-reindex.html": "REINDEX",
                "https://www.postgresql.org/docs/current/sql-revoke.html": "REVOKE",
                "https://www.postgresql.org/docs/current/sql-rollback.html": "ROLLBACK",
                "https://www.postgresql.org/docs/current/sql-savepoint.html": "SAVEPOINT",
                "https://www.postgresql.org/docs/current/sql-select.html": "SELECT",
                "https://www.postgresql.org/docs/current/sql-selectinto.html": "SELECT INTO",
                "https://www.postgresql.org/docs/current/sql-set.html": "SET",
                "https://www.postgresql.org/docs/current/sql-set-role.html": "SET ROLE",
                "https://www.postgresql.org/docs/current/sql-set-transaction.html": "SET TRANSACTION",
                "https://www.postgresql.org/docs/current/sql-show.html": "SHOW",
                "https://www.postgresql.org/docs/current/sql-truncate.html": "TRUNCATE",
                "https://www.postgresql.org/docs/current/sql-update.html": "UPDATE",
                "https://www.postgresql.org/docs/current/sql-vacuum.html": "VACUUM",
                "https://www.postgresql.org/docs/current/sql-values.html": "VALUES",
            },
        },
        "extensions": {
            "pages": {
                # Extensions and Contrib
                "https://www.postgresql.org/docs/current/contrib.html": "Additional Supplied Modules",
                "https://www.postgresql.org/docs/current/adminpack.html": "adminpack",
                "https://www.postgresql.org/docs/current/auto-explain.html": "auto_explain",
                "https://www.postgresql.org/docs/current/btree-gist.html": "btree_gist",
                "https://www.postgresql.org/docs/current/citext.html": "citext",
                "https://www.postgresql.org/docs/current/dblink.html": "dblink",
                "https://www.postgresql.org/docs/current/earthdistance.html": "earthdistance",
                "https://www.postgresql.org/docs/current/fuzzystrmatch.html": "fuzzystrmatch",
                "https://www.postgresql.org/docs/current/hstore.html": "hstore",
                "https://www.postgresql.org/docs/current/intarray.html": "intarray",
                "https://www.postgresql.org/docs/current/ltree.html": "ltree",
                "https://www.postgresql.org/docs/current/pageinspect.html": "pageinspect",
                "https://www.postgresql.org/docs/current/pgbuffercache.html": "pg_buffercache",
                "https://www.postgresql.org/docs/current/pgcrypto.html": "pgcrypto",
                "https://www.postgresql.org/docs/current/pgrowlocks.html": "pgrowlocks",
                "https://www.postgresql.org/docs/current/pgstatstatements.html": "pg_stat_statements",
                "https://www.postgresql.org/docs/current/pgtrgm.html": "pg_trgm",
                "https://www.postgresql.org/docs/current/postgres-fdw.html": "postgres_fdw",
                "https://www.postgresql.org/docs/current/tablefunc.html": "tablefunc",
                "https://www.postgresql.org/docs/current/tsm-system-rows.html": "tsm_system_rows",
                "https://www.postgresql.org/docs/current/tsm-system-time.html": "tsm_system_time",
                "https://www.postgresql.org/docs/current/unaccent.html": "unaccent",
                "https://www.postgresql.org/docs/current/uuid-ossp.html": "uuid-ossp",
                # PL/pgSQL
                "https://www.postgresql.org/docs/current/plpgsql.html": "PL/pgSQL - SQL Procedural Language",
                "https://www.postgresql.org/docs/current/plpgsql-overview.html": "PL/pgSQL Overview",
                "https://www.postgresql.org/docs/current/plpgsql-structure.html": "Structure of PL/pgSQL",
                "https://www.postgresql.org/docs/current/plpgsql-declarations.html": "Declarations",
                "https://www.postgresql.org/docs/current/plpgsql-expressions.html": "Expressions",
                "https://www.postgresql.org/docs/current/plpgsql-statements.html": "Basic Statements",
                "https://www.postgresql.org/docs/current/plpgsql-control-structures.html": "Control Structures",
                "https://www.postgresql.org/docs/current/plpgsql-cursors.html": "Cursors",
                "https://www.postgresql.org/docs/current/plpgsql-errors-and-messages.html": "Errors and Messages",
                "https://www.postgresql.org/docs/current/plpgsql-trigger.html": "Trigger Functions",
                # pgvector (external but commonly used)
                "https://github.com/pgvector/pgvector/blob/master/README.md": "pgvector README",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"postgresql-{source_key}" if source_key else "postgresql"
        super().__init__(name, base_dir, interval_seconds=3600)
        self.source_key = source_key

    def _strip_html(self, html_content):
        """Remove HTML tags, scripts, styles and normalize whitespace."""
        text = html_content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_mod.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_title(self, html_content, fallback):
        """Extract page title from HTML."""
        match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            for suffix in [' - PostgreSQL', ' :: PostgreSQL Documentation']:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            return title
        return fallback

    def _scrape_source(self, source_key, config):
        """Scrape all pages for a given source section."""
        count = 0
        pages = config.get("pages", {})

        for url, title in pages.items():
            if not self.running:
                break

            item_id = self.make_id(url)
            content = self.fetch_url(url)

            if content and len(content) > 500:
                text = self._strip_html(content)
                if len(text) > 100:
                    page_title = self._extract_title(content, title)

                    if self.save_item(item_id, {
                        "title": page_title,
                        "content": text[:50000],
                        "url": url,
                        "category": f"postgresql-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.0)

        return count

    def scrape(self):
        """Run scrape across all or a specific source."""
        total = 0

        if self.source_key:
            if self.source_key not in self.SOURCES:
                self.log.error(
                    f"Unknown source key: {self.source_key}. "
                    f"Available: {list(self.SOURCES.keys())}"
                )
                return 0
            sources = {self.source_key: self.SOURCES[self.source_key]}
        else:
            sources = self.SOURCES

        for key, config in sources.items():
            if not self.running:
                break
            self.log.info(f"=== Scraping postgresql/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    PostgreSQLScraper(base, source_key).run()
