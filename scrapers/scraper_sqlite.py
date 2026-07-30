#!/usr/bin/env python3
"""SQLite documentation scraper.

Covers:
  - SQL language: SELECT, INSERT, CREATE TABLE, triggers, views, CTEs, window functions
  - C API: interface overview, prepared statements, result values
  - Pragmas: journal mode, foreign keys, integrity check, WAL
  - Internals: file format, query planner, EXPLAIN, opcode reference
  - Extensions: FTS5, JSON1, virtual tables, R-Tree, compile-time options
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class SQLiteScraper(BaseScraper):
    """Scrape SQLite official documentation from sqlite.org."""

    SOURCES = {
        "sql-language": {
            "pages": {
                # Core SQL syntax
                "https://www.sqlite.org/lang.html": "SQL Language Reference",
                "https://www.sqlite.org/lang_select.html": "SELECT",
                "https://www.sqlite.org/lang_insert.html": "INSERT",
                "https://www.sqlite.org/lang_update.html": "UPDATE",
                "https://www.sqlite.org/lang_delete.html": "DELETE",
                "https://www.sqlite.org/lang_upsert.html": "UPSERT",
                # DDL
                "https://www.sqlite.org/lang_createtable.html": "CREATE TABLE",
                "https://www.sqlite.org/lang_altertable.html": "ALTER TABLE",
                "https://www.sqlite.org/lang_createindex.html": "CREATE INDEX",
                "https://www.sqlite.org/lang_createview.html": "CREATE VIEW",
                "https://www.sqlite.org/lang_createtrigger.html": "CREATE TRIGGER",
                "https://www.sqlite.org/lang_createvtab.html": "CREATE VIRTUAL TABLE",
                # Expressions and clauses
                "https://www.sqlite.org/lang_expr.html": "SQL Expressions",
                "https://www.sqlite.org/lang_with.html": "WITH Clause (Common Table Expressions)",
                "https://www.sqlite.org/windowfunctions.html": "Window Functions",
                "https://www.sqlite.org/lang_aggfunc.html": "Aggregate Functions",
                "https://www.sqlite.org/lang_corefunc.html": "Core Functions",
                "https://www.sqlite.org/lang_datefunc.html": "Date and Time Functions",
                "https://www.sqlite.org/lang_mathfunc.html": "Math Functions",
                # Transactions and constraints
                "https://www.sqlite.org/lang_transaction.html": "BEGIN TRANSACTION",
                "https://www.sqlite.org/lang_conflict.html": "ON CONFLICT Clause",
                "https://www.sqlite.org/foreignkeys.html": "Foreign Key Support",
                "https://www.sqlite.org/lang_returning.html": "RETURNING Clause",
                # Data types
                "https://www.sqlite.org/datatype3.html": "Datatypes in SQLite",
            },
        },
        "c-api": {
            "pages": {
                "https://www.sqlite.org/cintro.html": "Introduction to the C/C++ Interface",
                "https://www.sqlite.org/c3ref/intro.html": "C/C++ API Reference",
                "https://www.sqlite.org/c3ref/open.html": "sqlite3_open",
                "https://www.sqlite.org/c3ref/close.html": "sqlite3_close",
                "https://www.sqlite.org/c3ref/exec.html": "sqlite3_exec",
                "https://www.sqlite.org/c3ref/prepare.html": "sqlite3_prepare",
                "https://www.sqlite.org/c3ref/step.html": "sqlite3_step",
                "https://www.sqlite.org/c3ref/column_blob.html": "sqlite3_column Result Values",
                "https://www.sqlite.org/c3ref/bind_blob.html": "sqlite3_bind Parameter Binding",
                "https://www.sqlite.org/c3ref/finalize.html": "sqlite3_finalize",
                "https://www.sqlite.org/c3ref/errcode.html": "sqlite3_errcode / sqlite3_errmsg",
                "https://www.sqlite.org/c3ref/create_function.html": "sqlite3_create_function",
                "https://www.sqlite.org/c3ref/backup_finish.html": "Online Backup API",
            },
        },
        "pragmas": {
            "pages": {
                "https://www.sqlite.org/pragma.html": "PRAGMA Statements",
                "https://www.sqlite.org/wal.html": "Write-Ahead Logging (WAL)",
                "https://www.sqlite.org/vacuum.html": "VACUUM",
                "https://www.sqlite.org/lockingv3.html": "File Locking and Concurrency",
                "https://www.sqlite.org/threadsafe.html": "Using SQLite in Multi-Threaded Applications",
                "https://www.sqlite.org/inmemorydb.html": "In-Memory Databases",
            },
        },
        "internals": {
            "pages": {
                "https://www.sqlite.org/arch.html": "Architecture of SQLite",
                "https://www.sqlite.org/fileformat2.html": "Database File Format",
                "https://www.sqlite.org/queryplanner.html": "Query Planning",
                "https://www.sqlite.org/optoverview.html": "Query Optimizer Overview",
                "https://www.sqlite.org/eqp.html": "EXPLAIN QUERY PLAN",
                "https://www.sqlite.org/opcode.html": "VDBE Opcodes",
                "https://www.sqlite.org/vdbe.html": "The Virtual Database Engine (VDBE)",
                "https://www.sqlite.org/atomiccommit.html": "Atomic Commit in SQLite",
                "https://www.sqlite.org/limits.html": "Implementation Limits",
                "https://www.sqlite.org/compile.html": "Compile-Time Options",
            },
        },
        "extensions": {
            "pages": {
                "https://www.sqlite.org/fts5.html": "FTS5 Full-Text Search",
                "https://www.sqlite.org/json1.html": "JSON Functions",
                "https://www.sqlite.org/vtab.html": "Virtual Table Mechanism",
                "https://www.sqlite.org/rtree.html": "R-Tree Module",
                "https://www.sqlite.org/geopoly.html": "Geopoly Module",
                "https://www.sqlite.org/dbstat.html": "DBSTAT Virtual Table",
                "https://www.sqlite.org/csv.html": "CSV Virtual Table",
                "https://www.sqlite.org/series.html": "Generate Series Table-Valued Function",
                "https://www.sqlite.org/loadext.html": "Run-Time Loadable Extensions",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"sqlite-{source_key}" if source_key else "sqlite"
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
            for suffix in [' - SQLite', ' — SQLite']:
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
                        "category": f"sqlite-{source_key}",
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
            self.log.info(f"=== Scraping sqlite/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    SQLiteScraper(base, source_key).run()
