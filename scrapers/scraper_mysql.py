#!/usr/bin/env python3
"""MySQL reference manual scraper.

Covers:
  - SQL statements (DDL, DML, utility)
  - Data types, functions and operators
  - Optimization, InnoDB storage engine
  - Replication, security, administration
  - Stored programs, information/performance schema
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class MySQLScraper(BaseScraper):
    """Scrape MySQL reference manual from dev.mysql.com."""

    SOURCES = {
        "sql-statements": {
            "pages": {
                # DDL
                "https://dev.mysql.com/doc/refman/8.0/en/sql-data-definition-statements.html": "SQL Data Definition Statements",
                "https://dev.mysql.com/doc/refman/8.0/en/create-table.html": "CREATE TABLE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/alter-table.html": "ALTER TABLE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/drop-table.html": "DROP TABLE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/create-index.html": "CREATE INDEX Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/drop-index.html": "DROP INDEX Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/create-database.html": "CREATE DATABASE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/alter-database.html": "ALTER DATABASE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/drop-database.html": "DROP DATABASE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/create-view.html": "CREATE VIEW Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/alter-view.html": "ALTER VIEW Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/drop-view.html": "DROP VIEW Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/create-trigger.html": "CREATE TRIGGER Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/drop-trigger.html": "DROP TRIGGER Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/create-event.html": "CREATE EVENT Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/alter-event.html": "ALTER EVENT Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/drop-event.html": "DROP EVENT Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/create-procedure.html": "CREATE PROCEDURE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/alter-procedure.html": "ALTER PROCEDURE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/drop-procedure.html": "DROP PROCEDURE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/create-function.html": "CREATE FUNCTION Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/drop-function.html": "DROP FUNCTION Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/create-tablespace.html": "CREATE TABLESPACE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/alter-tablespace.html": "ALTER TABLESPACE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/drop-tablespace.html": "DROP TABLESPACE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/create-user.html": "CREATE USER Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/alter-user.html": "ALTER USER Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/drop-user.html": "DROP USER Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/create-role.html": "CREATE ROLE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/drop-role.html": "DROP ROLE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/rename-table.html": "RENAME TABLE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/truncate-table.html": "TRUNCATE TABLE Statement",
                # DML
                "https://dev.mysql.com/doc/refman/8.0/en/sql-data-manipulation-statements.html": "SQL Data Manipulation Statements",
                "https://dev.mysql.com/doc/refman/8.0/en/select.html": "SELECT Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/insert.html": "INSERT Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/update.html": "UPDATE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/delete.html": "DELETE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/replace.html": "REPLACE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/insert-select.html": "INSERT ... SELECT Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/insert-on-duplicate.html": "INSERT ... ON DUPLICATE KEY UPDATE",
                "https://dev.mysql.com/doc/refman/8.0/en/join.html": "JOIN Clause",
                "https://dev.mysql.com/doc/refman/8.0/en/union.html": "UNION Clause",
                "https://dev.mysql.com/doc/refman/8.0/en/subqueries.html": "Subqueries",
                "https://dev.mysql.com/doc/refman/8.0/en/correlated-subqueries.html": "Correlated Subqueries",
                "https://dev.mysql.com/doc/refman/8.0/en/derived-tables.html": "Derived Tables",
                "https://dev.mysql.com/doc/refman/8.0/en/with.html": "WITH (Common Table Expressions)",
                "https://dev.mysql.com/doc/refman/8.0/en/window-functions.html": "Window Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/window-function-descriptions.html": "Window Function Descriptions",
                "https://dev.mysql.com/doc/refman/8.0/en/group-by-modifiers.html": "GROUP BY Modifiers",
                "https://dev.mysql.com/doc/refman/8.0/en/group-by-handling.html": "GROUP BY Handling",
                "https://dev.mysql.com/doc/refman/8.0/en/order-by-optimization.html": "ORDER BY Optimization",
                "https://dev.mysql.com/doc/refman/8.0/en/limit-optimization.html": "LIMIT Query Optimization",
                "https://dev.mysql.com/doc/refman/8.0/en/load-data.html": "LOAD DATA Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/load-xml.html": "LOAD XML Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/do.html": "DO Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/handler.html": "HANDLER Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/call.html": "CALL Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/table.html": "TABLE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/values.html": "VALUES Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/parenthesized-query-expressions.html": "Parenthesized Query Expressions",
                "https://dev.mysql.com/doc/refman/8.0/en/except.html": "EXCEPT Clause",
                "https://dev.mysql.com/doc/refman/8.0/en/intersect.html": "INTERSECT Clause",
                # Utility / Transaction
                "https://dev.mysql.com/doc/refman/8.0/en/sql-transactional-statements.html": "SQL Transactional Statements",
                "https://dev.mysql.com/doc/refman/8.0/en/commit.html": "COMMIT Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/savepoint.html": "SAVEPOINT Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/lock-tables.html": "LOCK TABLES Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/set-transaction.html": "SET TRANSACTION Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/xa.html": "XA Transactions",
                "https://dev.mysql.com/doc/refman/8.0/en/xa-states.html": "XA Transaction States",
                "https://dev.mysql.com/doc/refman/8.0/en/grant.html": "GRANT Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/revoke.html": "REVOKE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/set-role.html": "SET ROLE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/set-password.html": "SET PASSWORD Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/show.html": "SHOW Statements",
                "https://dev.mysql.com/doc/refman/8.0/en/show-tables.html": "SHOW TABLES Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/show-columns.html": "SHOW COLUMNS Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/show-create-table.html": "SHOW CREATE TABLE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/show-databases.html": "SHOW DATABASES Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/show-index.html": "SHOW INDEX Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/show-status.html": "SHOW STATUS Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/show-variables.html": "SHOW VARIABLES Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/show-processlist.html": "SHOW PROCESSLIST Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/show-grants.html": "SHOW GRANTS Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/show-warnings.html": "SHOW WARNINGS Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/show-errors.html": "SHOW ERRORS Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/show-engines.html": "SHOW ENGINES Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/show-plugins.html": "SHOW PLUGINS Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/show-table-status.html": "SHOW TABLE STATUS Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/show-triggers.html": "SHOW TRIGGERS Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/show-events.html": "SHOW EVENTS Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/show-procedure-status.html": "SHOW PROCEDURE STATUS Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/show-function-status.html": "SHOW FUNCTION STATUS Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/show-binary-logs.html": "SHOW BINARY LOGS Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/show-binlog-events.html": "SHOW BINLOG EVENTS Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/show-replica-status.html": "SHOW REPLICA STATUS Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/describe.html": "DESCRIBE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/explain.html": "EXPLAIN Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/explain-output.html": "EXPLAIN Output Format",
                "https://dev.mysql.com/doc/refman/8.0/en/use.html": "USE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/set-variable.html": "SET Variable Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/prepare.html": "PREPARE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/execute.html": "EXECUTE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/deallocate-prepare.html": "DEALLOCATE PREPARE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/flush.html": "FLUSH Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/reset.html": "RESET Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/analyze-table.html": "ANALYZE TABLE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/check-table.html": "CHECK TABLE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/optimize-table.html": "OPTIMIZE TABLE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/repair-table.html": "REPAIR TABLE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/checksum-table.html": "CHECKSUM TABLE Statement",
            },
        },
        "data-types": {
            "pages": {
                "https://dev.mysql.com/doc/refman/8.0/en/data-types.html": "Data Types",
                "https://dev.mysql.com/doc/refman/8.0/en/numeric-types.html": "Numeric Data Types",
                "https://dev.mysql.com/doc/refman/8.0/en/integer-types.html": "Integer Types",
                "https://dev.mysql.com/doc/refman/8.0/en/fixed-point-types.html": "Fixed-Point Types (DECIMAL, NUMERIC)",
                "https://dev.mysql.com/doc/refman/8.0/en/floating-point-types.html": "Floating-Point Types (FLOAT, DOUBLE)",
                "https://dev.mysql.com/doc/refman/8.0/en/bit-type.html": "BIT Type",
                "https://dev.mysql.com/doc/refman/8.0/en/numeric-type-syntax.html": "Numeric Type Syntax",
                "https://dev.mysql.com/doc/refman/8.0/en/numeric-type-attributes.html": "Numeric Type Attributes",
                "https://dev.mysql.com/doc/refman/8.0/en/out-of-range-and-overflow.html": "Out-of-Range and Overflow Handling",
                "https://dev.mysql.com/doc/refman/8.0/en/date-and-time-types.html": "Date and Time Data Types",
                "https://dev.mysql.com/doc/refman/8.0/en/datetime.html": "DATE, DATETIME, and TIMESTAMP Types",
                "https://dev.mysql.com/doc/refman/8.0/en/date-and-time-type-syntax.html": "Date and Time Type Syntax",
                "https://dev.mysql.com/doc/refman/8.0/en/fractional-seconds.html": "Fractional Seconds in Time Values",
                "https://dev.mysql.com/doc/refman/8.0/en/timestamp-initialization.html": "Automatic Initialization and Updating for TIMESTAMP and DATETIME",
                "https://dev.mysql.com/doc/refman/8.0/en/time-zone-support.html": "Time Zone Support",
                "https://dev.mysql.com/doc/refman/8.0/en/string-types.html": "String Data Types",
                "https://dev.mysql.com/doc/refman/8.0/en/char.html": "CHAR and VARCHAR Types",
                "https://dev.mysql.com/doc/refman/8.0/en/binary-varbinary.html": "BINARY and VARBINARY Types",
                "https://dev.mysql.com/doc/refman/8.0/en/blob.html": "BLOB and TEXT Types",
                "https://dev.mysql.com/doc/refman/8.0/en/enum.html": "ENUM Type",
                "https://dev.mysql.com/doc/refman/8.0/en/set-type.html": "SET Type",
                "https://dev.mysql.com/doc/refman/8.0/en/json.html": "JSON Data Type",
                "https://dev.mysql.com/doc/refman/8.0/en/json-creation-functions.html": "JSON Creation Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/json-search-functions.html": "JSON Search Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/json-modification-functions.html": "JSON Modification Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/json-attribute-functions.html": "JSON Attribute Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/json-table-functions.html": "JSON Table Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/json-utility-functions.html": "JSON Utility Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/json-validation-functions.html": "JSON Validation Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/spatial-types.html": "Spatial Data Types",
                "https://dev.mysql.com/doc/refman/8.0/en/gis-geometry-class-hierarchy.html": "Geometry Class Hierarchy",
                "https://dev.mysql.com/doc/refman/8.0/en/spatial-function-reference.html": "Spatial Function Reference",
                "https://dev.mysql.com/doc/refman/8.0/en/type-conversion.html": "Type Conversion in Expression Evaluation",
                "https://dev.mysql.com/doc/refman/8.0/en/data-type-defaults.html": "Data Type Default Values",
                "https://dev.mysql.com/doc/refman/8.0/en/charset.html": "Character Sets and Collations",
                "https://dev.mysql.com/doc/refman/8.0/en/charset-unicode.html": "Unicode Support",
                "https://dev.mysql.com/doc/refman/8.0/en/charset-collations.html": "Collation Naming Conventions",
                "https://dev.mysql.com/doc/refman/8.0/en/charset-general.html": "Character Set and Collation General",
            },
        },
        "functions-operators": {
            "pages": {
                "https://dev.mysql.com/doc/refman/8.0/en/functions.html": "Functions and Operators",
                "https://dev.mysql.com/doc/refman/8.0/en/non-typed-operators.html": "Non-Typed Operators",
                "https://dev.mysql.com/doc/refman/8.0/en/arithmetic-functions.html": "Arithmetic Operators",
                "https://dev.mysql.com/doc/refman/8.0/en/mathematical-functions.html": "Mathematical Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/string-functions.html": "String Functions and Operators",
                "https://dev.mysql.com/doc/refman/8.0/en/string-comparison-functions.html": "String Comparison Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/regexp.html": "Regular Expressions",
                "https://dev.mysql.com/doc/refman/8.0/en/date-and-time-functions.html": "Date and Time Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/comparison-operators.html": "Comparison Functions and Operators",
                "https://dev.mysql.com/doc/refman/8.0/en/logical-operators.html": "Logical Operators",
                "https://dev.mysql.com/doc/refman/8.0/en/assignment-operators.html": "Assignment Operators",
                "https://dev.mysql.com/doc/refman/8.0/en/flow-control-functions.html": "Flow Control Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/cast-functions.html": "Cast Functions and Operators",
                "https://dev.mysql.com/doc/refman/8.0/en/bit-functions.html": "Bit Functions and Operators",
                "https://dev.mysql.com/doc/refman/8.0/en/encryption-functions.html": "Encryption and Compression Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/locking-functions.html": "Locking Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/information-functions.html": "Information Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/miscellaneous-functions.html": "Miscellaneous Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/aggregate-functions.html": "Aggregate Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/aggregate-functions-and-modifiers.html": "Aggregate Functions and Modifiers",
                "https://dev.mysql.com/doc/refman/8.0/en/group-by-functions.html": "GROUP BY Aggregate Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/window-function-descriptions.html": "Window Function Descriptions",
                "https://dev.mysql.com/doc/refman/8.0/en/window-functions-usage.html": "Window Functions Usage",
                "https://dev.mysql.com/doc/refman/8.0/en/window-functions-frames.html": "Window Function Frame Specification",
                "https://dev.mysql.com/doc/refman/8.0/en/window-functions-named-windows.html": "Named Windows",
                "https://dev.mysql.com/doc/refman/8.0/en/spatial-analysis-functions.html": "Spatial Analysis Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/spatial-geojson-functions.html": "Spatial GeoJSON Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/spatial-convenience-functions.html": "Spatial Convenience Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/spatial-relation-functions.html": "Spatial Relation Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/full-text-search.html": "Full-Text Search Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/fulltext-natural-language.html": "Natural Language Full-Text Searches",
                "https://dev.mysql.com/doc/refman/8.0/en/fulltext-boolean.html": "Boolean Full-Text Searches",
                "https://dev.mysql.com/doc/refman/8.0/en/fulltext-query-expansion.html": "Full-Text Searches with Query Expansion",
                "https://dev.mysql.com/doc/refman/8.0/en/fulltext-search-ngram.html": "ngram Full-Text Parser",
                "https://dev.mysql.com/doc/refman/8.0/en/xml-functions.html": "XML Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema-functions.html": "Performance Schema Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/internal-functions.html": "Internal Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/operator-precedence.html": "Operator Precedence",
                "https://dev.mysql.com/doc/refman/8.0/en/type-conversion.html": "Type Conversion in Expression Evaluation",
                "https://dev.mysql.com/doc/refman/8.0/en/control-flow-functions.html": "Control Flow Functions",
                "https://dev.mysql.com/doc/refman/8.0/en/numeric-functions.html": "Numeric Functions and Operators",
                "https://dev.mysql.com/doc/refman/8.0/en/date-calculations.html": "Date Calculations",
                "https://dev.mysql.com/doc/refman/8.0/en/pattern-matching.html": "Pattern Matching",
                "https://dev.mysql.com/doc/refman/8.0/en/built-in-function-reference.html": "Built-In Function Reference",
                "https://dev.mysql.com/doc/refman/8.0/en/loadable-function-reference.html": "Loadable Function Reference",
                "https://dev.mysql.com/doc/refman/8.0/en/expressions.html": "Expressions",
                "https://dev.mysql.com/doc/refman/8.0/en/user-variables.html": "User-Defined Variables",
                "https://dev.mysql.com/doc/refman/8.0/en/charset-binary-collations.html": "Binary Collation",
            },
        },
        "optimization": {
            "pages": {
                "https://dev.mysql.com/doc/refman/8.0/en/optimization.html": "Optimization Overview",
                "https://dev.mysql.com/doc/refman/8.0/en/statement-optimization.html": "Optimizing SQL Statements",
                "https://dev.mysql.com/doc/refman/8.0/en/select-optimization.html": "Optimizing SELECT Statements",
                "https://dev.mysql.com/doc/refman/8.0/en/where-optimization.html": "WHERE Clause Optimization",
                "https://dev.mysql.com/doc/refman/8.0/en/range-optimization.html": "Range Optimization",
                "https://dev.mysql.com/doc/refman/8.0/en/index-merge-optimization.html": "Index Merge Optimization",
                "https://dev.mysql.com/doc/refman/8.0/en/hash-joins.html": "Hash Join Optimization",
                "https://dev.mysql.com/doc/refman/8.0/en/engine-condition-pushdown-optimization.html": "Engine Condition Pushdown Optimization",
                "https://dev.mysql.com/doc/refman/8.0/en/index-condition-pushdown-optimization.html": "Index Condition Pushdown Optimization",
                "https://dev.mysql.com/doc/refman/8.0/en/nested-loop-joins.html": "Nested-Loop Join Algorithms",
                "https://dev.mysql.com/doc/refman/8.0/en/nested-join-optimization.html": "Nested Join Optimization",
                "https://dev.mysql.com/doc/refman/8.0/en/outer-join-optimization.html": "Outer Join Optimization",
                "https://dev.mysql.com/doc/refman/8.0/en/multi-range-read-optimization.html": "Multi-Range Read Optimization",
                "https://dev.mysql.com/doc/refman/8.0/en/block-nested-loop-join-algorithm.html": "Block Nested-Loop Join Algorithm",
                "https://dev.mysql.com/doc/refman/8.0/en/condition-filtering.html": "Condition Filtering",
                "https://dev.mysql.com/doc/refman/8.0/en/constant-folding-optimization.html": "Constant-Folding Optimization",
                "https://dev.mysql.com/doc/refman/8.0/en/is-null-optimization.html": "IS NULL Optimization",
                "https://dev.mysql.com/doc/refman/8.0/en/order-by-optimization.html": "ORDER BY Optimization",
                "https://dev.mysql.com/doc/refman/8.0/en/group-by-optimization.html": "GROUP BY Optimization",
                "https://dev.mysql.com/doc/refman/8.0/en/distinct-optimization.html": "DISTINCT Optimization",
                "https://dev.mysql.com/doc/refman/8.0/en/limit-optimization.html": "LIMIT Query Optimization",
                "https://dev.mysql.com/doc/refman/8.0/en/function-optimization.html": "Function Call Optimization",
                "https://dev.mysql.com/doc/refman/8.0/en/row-constructor-optimization.html": "Row Constructor Expression Optimization",
                "https://dev.mysql.com/doc/refman/8.0/en/table-elimination.html": "Table Elimination",
                "https://dev.mysql.com/doc/refman/8.0/en/subquery-optimization.html": "Optimizing Subqueries",
                "https://dev.mysql.com/doc/refman/8.0/en/subquery-materialization.html": "Subquery Materialization",
                "https://dev.mysql.com/doc/refman/8.0/en/derived-table-optimization.html": "Derived Table Optimization",
                "https://dev.mysql.com/doc/refman/8.0/en/optimization-indexes.html": "Optimization and Indexes",
                "https://dev.mysql.com/doc/refman/8.0/en/mysql-indexes.html": "How MySQL Uses Indexes",
                "https://dev.mysql.com/doc/refman/8.0/en/column-indexes.html": "Column Indexes",
                "https://dev.mysql.com/doc/refman/8.0/en/multiple-column-indexes.html": "Multiple-Column Indexes",
                "https://dev.mysql.com/doc/refman/8.0/en/verifying-index-usage.html": "Verifying Index Usage",
                "https://dev.mysql.com/doc/refman/8.0/en/index-btree-hash.html": "Comparison of B-Tree and Hash Indexes",
                "https://dev.mysql.com/doc/refman/8.0/en/query-cache.html": "Query Cache",
                "https://dev.mysql.com/doc/refman/8.0/en/buffering-caching.html": "Buffering and Caching",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-buffer-pool.html": "InnoDB Buffer Pool",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-buffer-pool-resize.html": "InnoDB Buffer Pool Resizing",
                "https://dev.mysql.com/doc/refman/8.0/en/optimizing-innodb.html": "Optimizing for InnoDB Tables",
                "https://dev.mysql.com/doc/refman/8.0/en/optimizing-innodb-transaction-management.html": "Optimizing InnoDB Transaction Management",
                "https://dev.mysql.com/doc/refman/8.0/en/optimizing-innodb-logging.html": "Optimizing InnoDB Redo Logging",
                "https://dev.mysql.com/doc/refman/8.0/en/optimizing-innodb-diskio.html": "Optimizing InnoDB Disk I/O",
                "https://dev.mysql.com/doc/refman/8.0/en/optimizing-innodb-configuration-variables.html": "Optimizing InnoDB Configuration Variables",
                "https://dev.mysql.com/doc/refman/8.0/en/optimizing-memory.html": "Optimizing Memory Use",
                "https://dev.mysql.com/doc/refman/8.0/en/optimizing-network.html": "Optimizing Network Use",
                "https://dev.mysql.com/doc/refman/8.0/en/optimize-benchmarking.html": "Optimizing for Benchmarks",
                "https://dev.mysql.com/doc/refman/8.0/en/controlling-optimizer.html": "Controlling the Query Optimizer",
                "https://dev.mysql.com/doc/refman/8.0/en/switchable-optimizations.html": "Switchable Optimizations",
                "https://dev.mysql.com/doc/refman/8.0/en/optimizer-hints.html": "Optimizer Hints",
                "https://dev.mysql.com/doc/refman/8.0/en/index-hints.html": "Index Hints",
                "https://dev.mysql.com/doc/refman/8.0/en/cost-model.html": "The Optimizer Cost Model",
                "https://dev.mysql.com/doc/refman/8.0/en/using-explain.html": "Understanding the Query Execution Plan",
                "https://dev.mysql.com/doc/refman/8.0/en/explain-output.html": "EXPLAIN Output Format",
                "https://dev.mysql.com/doc/refman/8.0/en/extended-explain.html": "Extended EXPLAIN Output Format",
                "https://dev.mysql.com/doc/refman/8.0/en/estimating-performance.html": "Estimating Query Performance",
            },
        },
        "innodb": {
            "pages": {
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-storage-engine.html": "InnoDB Storage Engine",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-introduction.html": "Introduction to InnoDB",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-benefits.html": "Benefits of Using InnoDB",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-check-availability.html": "Checking InnoDB Availability",
                "https://dev.mysql.com/doc/refman/8.0/en/using-innodb-tables.html": "Using InnoDB Tables",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-table-and-index.html": "InnoDB Tables and Indexes",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-index-types.html": "InnoDB Index Types",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-tablespace.html": "InnoDB Tablespaces",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-system-tablespace.html": "InnoDB System Tablespace",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-file-per-table-tablespaces.html": "File-Per-Table Tablespaces",
                "https://dev.mysql.com/doc/refman/8.0/en/general-tablespaces.html": "General Tablespaces",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-undo-tablespaces.html": "Undo Tablespaces",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-temporary-tablespace.html": "Temporary Tablespace",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-data-log-reconfiguration.html": "InnoDB Data and Log Reconfiguration",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-redo-log.html": "InnoDB Redo Log",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-undo-logs.html": "InnoDB Undo Logs",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-locking.html": "InnoDB Locking",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-lock-modes.html": "InnoDB Lock Modes",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-record-level-locks.html": "InnoDB Record-Level Locks",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-next-key-locking.html": "InnoDB Next-Key Locks",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-gap-locks.html": "InnoDB Gap Locks",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-insert-intention.html": "InnoDB Insert Intention Locks",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-auto-increment-handling.html": "InnoDB AUTO_INCREMENT Handling",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-deadlocks.html": "InnoDB Deadlocks",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-deadlock-detection.html": "InnoDB Deadlock Detection",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-deadlocks-handling.html": "Handling InnoDB Deadlocks",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-transaction-model.html": "InnoDB Transaction Model",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-transaction-isolation-levels.html": "InnoDB Transaction Isolation Levels",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-autocommit-commit-rollback.html": "InnoDB Autocommit, Commit, Rollback",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-consistent-read.html": "InnoDB Consistent Nonlocking Reads",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-locking-reads.html": "InnoDB Locking Reads",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-multi-versioning.html": "InnoDB Multi-Versioning",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-performance.html": "InnoDB Performance",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-row-format.html": "InnoDB Row Formats",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-compression.html": "InnoDB Table Compression",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-file-format.html": "InnoDB File Format",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-fulltext-index.html": "InnoDB Full-Text Indexes",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl.html": "InnoDB Online DDL",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-operations.html": "Online DDL Operations",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-performance.html": "Online DDL Performance",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-space-requirements.html": "Online DDL Space Requirements",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-in-memory-structures.html": "InnoDB In-Memory Structures",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-buffer-pool.html": "InnoDB Buffer Pool",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-change-buffer.html": "InnoDB Change Buffer",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-adaptive-hash.html": "InnoDB Adaptive Hash Index",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-log-buffer.html": "InnoDB Log Buffer",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-on-disk-structures.html": "InnoDB On-Disk Structures",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-doublewrite-buffer.html": "InnoDB Doublewrite Buffer",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-architecture.html": "InnoDB Architecture",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-recovery.html": "InnoDB Recovery",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-backup.html": "InnoDB Backup",
                "https://dev.mysql.com/doc/refman/8.0/en/innodb-monitors.html": "InnoDB Monitors",
            },
        },
        "replication": {
            "pages": {
                "https://dev.mysql.com/doc/refman/8.0/en/replication.html": "Replication",
                "https://dev.mysql.com/doc/refman/8.0/en/replication-configuration.html": "Replication Configuration",
                "https://dev.mysql.com/doc/refman/8.0/en/replication-howto.html": "Setting Up Replication",
                "https://dev.mysql.com/doc/refman/8.0/en/replication-howto-masterbaseconfig.html": "Setting the Replication Source Configuration",
                "https://dev.mysql.com/doc/refman/8.0/en/replication-howto-slavebaseconfig.html": "Setting the Replica Configuration",
                "https://dev.mysql.com/doc/refman/8.0/en/replication-gtids.html": "Replication with Global Transaction Identifiers",
                "https://dev.mysql.com/doc/refman/8.0/en/replication-gtids-concepts.html": "GTID Concepts",
                "https://dev.mysql.com/doc/refman/8.0/en/replication-gtids-howto.html": "Setting Up GTID Replication",
                "https://dev.mysql.com/doc/refman/8.0/en/replication-formats.html": "Replication Formats",
                "https://dev.mysql.com/doc/refman/8.0/en/replication-sbr-rbr.html": "Statement-Based and Row-Based Replication",
                "https://dev.mysql.com/doc/refman/8.0/en/replication-rbr-safe-unsafe.html": "Row-Based Replication Safe/Unsafe Statements",
                "https://dev.mysql.com/doc/refman/8.0/en/replication-semisync.html": "Semisynchronous Replication",
                "https://dev.mysql.com/doc/refman/8.0/en/replication-delayed.html": "Delayed Replication",
                "https://dev.mysql.com/doc/refman/8.0/en/replication-multi-source.html": "Multi-Source Replication",
                "https://dev.mysql.com/doc/refman/8.0/en/replication-channels.html": "Replication Channels",
                "https://dev.mysql.com/doc/refman/8.0/en/replication-solutions.html": "Replication Solutions",
                "https://dev.mysql.com/doc/refman/8.0/en/replication-solutions-backups.html": "Replication for Backups",
                "https://dev.mysql.com/doc/refman/8.0/en/replication-solutions-scaleout.html": "Replication for Scale-Out",
                "https://dev.mysql.com/doc/refman/8.0/en/replication-solutions-switch.html": "Switching Sources During Failover",
                "https://dev.mysql.com/doc/refman/8.0/en/replication-notes.html": "Replication Notes and Tips",
                "https://dev.mysql.com/doc/refman/8.0/en/replication-implementation.html": "Replication Implementation",
                "https://dev.mysql.com/doc/refman/8.0/en/replication-implementation-details.html": "Replication Implementation Details",
                "https://dev.mysql.com/doc/refman/8.0/en/binlog.html": "The Binary Log",
                "https://dev.mysql.com/doc/refman/8.0/en/binary-log.html": "Binary Log Overview",
                "https://dev.mysql.com/doc/refman/8.0/en/binary-log-formats.html": "Binary Logging Formats",
                "https://dev.mysql.com/doc/refman/8.0/en/binary-log-setting.html": "Setting Binary Log Format",
                "https://dev.mysql.com/doc/refman/8.0/en/group-replication.html": "Group Replication",
                "https://dev.mysql.com/doc/refman/8.0/en/group-replication-getting-started.html": "Getting Started with Group Replication",
                "https://dev.mysql.com/doc/refman/8.0/en/group-replication-deploying-in-single-primary-mode.html": "Group Replication Single-Primary Mode",
                "https://dev.mysql.com/doc/refman/8.0/en/group-replication-deploying-in-multi-primary-mode.html": "Group Replication Multi-Primary Mode",
                "https://dev.mysql.com/doc/refman/8.0/en/group-replication-requirements.html": "Group Replication Requirements",
                "https://dev.mysql.com/doc/refman/8.0/en/group-replication-configuring-instances.html": "Configuring Group Replication Instances",
                "https://dev.mysql.com/doc/refman/8.0/en/group-replication-primary-secondary-replication.html": "Group Replication Primary-Secondary",
                "https://dev.mysql.com/doc/refman/8.0/en/group-replication-performance.html": "Group Replication Performance",
                "https://dev.mysql.com/doc/refman/8.0/en/group-replication-security.html": "Group Replication Security",
                "https://dev.mysql.com/doc/refman/8.0/en/group-replication-monitoring.html": "Monitoring Group Replication",
                "https://dev.mysql.com/doc/refman/8.0/en/group-replication-operations.html": "Group Replication Operations",
                "https://dev.mysql.com/doc/refman/8.0/en/mysql-innodb-cluster-introduction.html": "MySQL InnoDB Cluster",
                "https://dev.mysql.com/doc/refman/8.0/en/change-replication-source-to.html": "CHANGE REPLICATION SOURCE TO Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/start-replica.html": "START REPLICA Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/stop-replica.html": "STOP REPLICA Statement",
            },
        },
        "security": {
            "pages": {
                "https://dev.mysql.com/doc/refman/8.0/en/security.html": "Security",
                "https://dev.mysql.com/doc/refman/8.0/en/general-security-issues.html": "General Security Issues",
                "https://dev.mysql.com/doc/refman/8.0/en/access-control.html": "Access Control and Account Management",
                "https://dev.mysql.com/doc/refman/8.0/en/privilege-system.html": "The MySQL Privilege System",
                "https://dev.mysql.com/doc/refman/8.0/en/privileges-provided.html": "Privileges Provided by MySQL",
                "https://dev.mysql.com/doc/refman/8.0/en/account-management-statements.html": "Account Management Statements",
                "https://dev.mysql.com/doc/refman/8.0/en/user-names.html": "Specifying Account Names",
                "https://dev.mysql.com/doc/refman/8.0/en/role-names.html": "Specifying Role Names",
                "https://dev.mysql.com/doc/refman/8.0/en/connection-access.html": "Connection Access Control",
                "https://dev.mysql.com/doc/refman/8.0/en/request-access.html": "Request Access Control",
                "https://dev.mysql.com/doc/refman/8.0/en/adding-users.html": "Adding User Accounts",
                "https://dev.mysql.com/doc/refman/8.0/en/removing-users.html": "Removing User Accounts",
                "https://dev.mysql.com/doc/refman/8.0/en/assigning-passwords.html": "Assigning Account Passwords",
                "https://dev.mysql.com/doc/refman/8.0/en/password-management.html": "Password Management",
                "https://dev.mysql.com/doc/refman/8.0/en/expired-password-handling.html": "Expired Password Handling",
                "https://dev.mysql.com/doc/refman/8.0/en/pluggable-authentication.html": "Pluggable Authentication",
                "https://dev.mysql.com/doc/refman/8.0/en/authentication-plugins.html": "Authentication Plugins",
                "https://dev.mysql.com/doc/refman/8.0/en/caching-sha2-pluggable-authentication.html": "Caching SHA-2 Pluggable Authentication",
                "https://dev.mysql.com/doc/refman/8.0/en/native-pluggable-authentication.html": "Native Pluggable Authentication",
                "https://dev.mysql.com/doc/refman/8.0/en/ldap-pluggable-authentication.html": "LDAP Pluggable Authentication",
                "https://dev.mysql.com/doc/refman/8.0/en/pam-pluggable-authentication.html": "PAM Pluggable Authentication",
                "https://dev.mysql.com/doc/refman/8.0/en/multifactor-authentication.html": "Multifactor Authentication",
                "https://dev.mysql.com/doc/refman/8.0/en/proxy-users.html": "Proxy Users",
                "https://dev.mysql.com/doc/refman/8.0/en/encrypted-connections.html": "Using Encrypted Connections",
                "https://dev.mysql.com/doc/refman/8.0/en/using-encrypted-connections.html": "Configuring Encrypted Connections",
                "https://dev.mysql.com/doc/refman/8.0/en/creating-ssl-files-using-openssl.html": "Creating SSL Files Using OpenSSL",
                "https://dev.mysql.com/doc/refman/8.0/en/audit-log.html": "MySQL Enterprise Audit Log",
                "https://dev.mysql.com/doc/refman/8.0/en/enterprise-encryption.html": "MySQL Enterprise Encryption",
                "https://dev.mysql.com/doc/refman/8.0/en/firewall.html": "MySQL Enterprise Firewall",
                "https://dev.mysql.com/doc/refman/8.0/en/data-masking.html": "MySQL Enterprise Data Masking",
                "https://dev.mysql.com/doc/refman/8.0/en/security-best-practices.html": "Security Best Practices",
                "https://dev.mysql.com/doc/refman/8.0/en/security-against-attack.html": "Making MySQL Secure Against Attackers",
            },
        },
        "administration": {
            "pages": {
                "https://dev.mysql.com/doc/refman/8.0/en/server-administration.html": "MySQL Server Administration",
                "https://dev.mysql.com/doc/refman/8.0/en/mysqld-server.html": "The MySQL Server (mysqld)",
                "https://dev.mysql.com/doc/refman/8.0/en/server-configuration.html": "Server Configuration",
                "https://dev.mysql.com/doc/refman/8.0/en/server-system-variables.html": "Server System Variables",
                "https://dev.mysql.com/doc/refman/8.0/en/server-status-variables.html": "Server Status Variables",
                "https://dev.mysql.com/doc/refman/8.0/en/server-options.html": "Server Command Options",
                "https://dev.mysql.com/doc/refman/8.0/en/using-system-variables.html": "Using System Variables",
                "https://dev.mysql.com/doc/refman/8.0/en/server-logs.html": "MySQL Server Logs",
                "https://dev.mysql.com/doc/refman/8.0/en/error-log.html": "The Error Log",
                "https://dev.mysql.com/doc/refman/8.0/en/general-query-log.html": "The General Query Log",
                "https://dev.mysql.com/doc/refman/8.0/en/slow-query-log.html": "The Slow Query Log",
                "https://dev.mysql.com/doc/refman/8.0/en/binary-log.html": "The Binary Log",
                "https://dev.mysql.com/doc/refman/8.0/en/relay-log.html": "The Relay Log",
                "https://dev.mysql.com/doc/refman/8.0/en/mysqladmin.html": "mysqladmin Client",
                "https://dev.mysql.com/doc/refman/8.0/en/mysql-command-options.html": "mysql Client Options",
                "https://dev.mysql.com/doc/refman/8.0/en/mysqldump.html": "mysqldump - Database Backup Program",
                "https://dev.mysql.com/doc/refman/8.0/en/mysqlimport.html": "mysqlimport - Data Import Program",
                "https://dev.mysql.com/doc/refman/8.0/en/mysqlpump.html": "mysqlpump - Database Backup Program",
                "https://dev.mysql.com/doc/refman/8.0/en/mysqlcheck.html": "mysqlcheck - Table Maintenance Program",
                "https://dev.mysql.com/doc/refman/8.0/en/mysqlbinlog.html": "mysqlbinlog - Binary Log Utility",
                "https://dev.mysql.com/doc/refman/8.0/en/mysqlshow.html": "mysqlshow - Database and Table Information",
                "https://dev.mysql.com/doc/refman/8.0/en/mysqlslap.html": "mysqlslap - Load Emulation Client",
                "https://dev.mysql.com/doc/refman/8.0/en/mysql-config-editor.html": "mysql_config_editor - Configuration Utility",
                "https://dev.mysql.com/doc/refman/8.0/en/backup-and-recovery.html": "Backup and Recovery",
                "https://dev.mysql.com/doc/refman/8.0/en/backup-types.html": "Backup Types",
                "https://dev.mysql.com/doc/refman/8.0/en/backup-methods.html": "Database Backup Methods",
                "https://dev.mysql.com/doc/refman/8.0/en/backup-strategy-example.html": "Example Backup and Recovery Strategy",
                "https://dev.mysql.com/doc/refman/8.0/en/point-in-time-recovery.html": "Point-in-Time Recovery",
                "https://dev.mysql.com/doc/refman/8.0/en/mysqldump-tips.html": "mysqldump Tips",
                "https://dev.mysql.com/doc/refman/8.0/en/mysql-enterprise-backup.html": "MySQL Enterprise Backup",
                "https://dev.mysql.com/doc/refman/8.0/en/server-shutdown.html": "The Server Shutdown Process",
                "https://dev.mysql.com/doc/refman/8.0/en/multiple-servers.html": "Running Multiple MySQL Instances",
                "https://dev.mysql.com/doc/refman/8.0/en/multiple-data-directories.html": "Using Multiple Data Directories",
                "https://dev.mysql.com/doc/refman/8.0/en/server-plugins.html": "MySQL Server Plugins",
                "https://dev.mysql.com/doc/refman/8.0/en/plugin-loading.html": "Installing and Uninstalling Plugins",
            },
        },
        "stored-programs": {
            "pages": {
                "https://dev.mysql.com/doc/refman/8.0/en/stored-routines.html": "Stored Routines",
                "https://dev.mysql.com/doc/refman/8.0/en/stored-routines-syntax.html": "Stored Routine Syntax",
                "https://dev.mysql.com/doc/refman/8.0/en/create-procedure.html": "CREATE PROCEDURE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/create-function.html": "CREATE FUNCTION Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/stored-routines-privileges.html": "Stored Routine Privileges",
                "https://dev.mysql.com/doc/refman/8.0/en/stored-routines-last-insert-id.html": "Stored Routines and LAST_INSERT_ID()",
                "https://dev.mysql.com/doc/refman/8.0/en/trigger-syntax.html": "Trigger Syntax and Examples",
                "https://dev.mysql.com/doc/refman/8.0/en/triggers.html": "Using Triggers",
                "https://dev.mysql.com/doc/refman/8.0/en/trigger-metadata.html": "Trigger Metadata",
                "https://dev.mysql.com/doc/refman/8.0/en/events.html": "Using the Event Scheduler",
                "https://dev.mysql.com/doc/refman/8.0/en/events-overview.html": "Event Scheduler Overview",
                "https://dev.mysql.com/doc/refman/8.0/en/events-syntax.html": "Event Syntax",
                "https://dev.mysql.com/doc/refman/8.0/en/events-metadata.html": "Event Metadata",
                "https://dev.mysql.com/doc/refman/8.0/en/views.html": "Using Views",
                "https://dev.mysql.com/doc/refman/8.0/en/view-syntax.html": "View Syntax",
                "https://dev.mysql.com/doc/refman/8.0/en/view-updatability.html": "Updatable and Insertable Views",
                "https://dev.mysql.com/doc/refman/8.0/en/view-algorithms.html": "View Processing Algorithms",
                "https://dev.mysql.com/doc/refman/8.0/en/stored-program-restrictions.html": "Stored Program Restrictions",
                "https://dev.mysql.com/doc/refman/8.0/en/declare.html": "DECLARE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/if.html": "IF Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/case.html": "CASE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/loop.html": "LOOP Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/while.html": "WHILE Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/repeat.html": "REPEAT Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/cursors.html": "Cursors",
                "https://dev.mysql.com/doc/refman/8.0/en/declare-handler.html": "DECLARE HANDLER Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/declare-condition.html": "DECLARE CONDITION Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/signal.html": "SIGNAL Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/resignal.html": "RESIGNAL Statement",
                "https://dev.mysql.com/doc/refman/8.0/en/get-diagnostics.html": "GET DIAGNOSTICS Statement",
            },
        },
        "information-schema": {
            "pages": {
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema.html": "INFORMATION_SCHEMA Tables",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-introduction.html": "INFORMATION_SCHEMA Introduction",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-columns-table.html": "INFORMATION_SCHEMA COLUMNS Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-key-column-usage-table.html": "INFORMATION_SCHEMA KEY_COLUMN_USAGE Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-tables-table.html": "INFORMATION_SCHEMA TABLES Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-statistics-table.html": "INFORMATION_SCHEMA STATISTICS Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-schemata-table.html": "INFORMATION_SCHEMA SCHEMATA Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-table-constraints-table.html": "INFORMATION_SCHEMA TABLE_CONSTRAINTS Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-views-table.html": "INFORMATION_SCHEMA VIEWS Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-routines-table.html": "INFORMATION_SCHEMA ROUTINES Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-triggers-table.html": "INFORMATION_SCHEMA TRIGGERS Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-events-table.html": "INFORMATION_SCHEMA EVENTS Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-partitions-table.html": "INFORMATION_SCHEMA PARTITIONS Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-processlist-table.html": "INFORMATION_SCHEMA PROCESSLIST Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-user-privileges-table.html": "INFORMATION_SCHEMA USER_PRIVILEGES Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-referential-constraints-table.html": "INFORMATION_SCHEMA REFERENTIAL_CONSTRAINTS Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-character-sets-table.html": "INFORMATION_SCHEMA CHARACTER_SETS Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-collations-table.html": "INFORMATION_SCHEMA COLLATIONS Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-engines-table.html": "INFORMATION_SCHEMA ENGINES Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-files-table.html": "INFORMATION_SCHEMA FILES Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-innodb-tables.html": "INFORMATION_SCHEMA InnoDB Tables",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-innodb-trx-table.html": "INFORMATION_SCHEMA INNODB_TRX Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-innodb-locks-table.html": "INFORMATION_SCHEMA INNODB_LOCKS Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-innodb-buffer-page-table.html": "INFORMATION_SCHEMA INNODB_BUFFER_PAGE Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-innodb-tablestats-table.html": "INFORMATION_SCHEMA INNODB_TABLESTATS Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-innodb-cmp-table.html": "INFORMATION_SCHEMA INNODB_CMP Table",
                "https://dev.mysql.com/doc/refman/8.0/en/information-schema-innodb-metrics-table.html": "INFORMATION_SCHEMA INNODB_METRICS Table",
            },
        },
        "performance-schema": {
            "pages": {
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema.html": "Performance Schema",
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema-quick-start.html": "Performance Schema Quick Start",
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema-build-configuration.html": "Performance Schema Build Configuration",
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema-startup-configuration.html": "Performance Schema Startup Configuration",
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema-runtime-configuration.html": "Performance Schema Runtime Configuration",
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema-queries.html": "Performance Schema Queries",
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema-wait-tables.html": "Performance Schema Wait Tables",
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema-stage-tables.html": "Performance Schema Stage Tables",
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema-statement-tables.html": "Performance Schema Statement Tables",
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema-transaction-tables.html": "Performance Schema Transaction Tables",
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema-memory-summary-tables.html": "Performance Schema Memory Summary Tables",
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema-error-summary-tables.html": "Performance Schema Error Summary Tables",
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema-status-variable-tables.html": "Performance Schema Status Variable Tables",
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema-system-variable-tables.html": "Performance Schema System Variable Tables",
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema-connection-tables.html": "Performance Schema Connection Tables",
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema-lock-tables.html": "Performance Schema Lock Tables",
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema-replication-tables.html": "Performance Schema Replication Tables",
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema-thread-table.html": "Performance Schema Thread Table",
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema-events-waits-current-table.html": "Performance Schema events_waits_current Table",
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema-events-stages-current-table.html": "Performance Schema events_stages_current Table",
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema-events-statements-current-table.html": "Performance Schema events_statements_current Table",
                "https://dev.mysql.com/doc/refman/8.0/en/performance-schema-events-transactions-current-table.html": "Performance Schema events_transactions_current Table",
                "https://dev.mysql.com/doc/refman/8.0/en/sys-schema.html": "MySQL sys Schema",
                "https://dev.mysql.com/doc/refman/8.0/en/sys-schema-views.html": "sys Schema Views",
                "https://dev.mysql.com/doc/refman/8.0/en/sys-schema-tables.html": "sys Schema Tables",
                "https://dev.mysql.com/doc/refman/8.0/en/sys-schema-procedures.html": "sys Schema Stored Procedures",
                "https://dev.mysql.com/doc/refman/8.0/en/sys-schema-functions.html": "sys Schema Stored Functions",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"mysql-{source_key}" if source_key else "mysql"
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
            for suffix in [' - MySQL 8.0 Reference Manual', ' :: MySQL 8.0 Reference Manual', ' - MySQL']:
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
                        "category": f"mysql-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.5)

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
            self.log.info(f"=== Scraping mysql/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    MySQLScraper(base, source_key).run()
