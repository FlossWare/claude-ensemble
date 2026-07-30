#!/usr/bin/env python3
"""OrientDB documentation scraper.

Covers:
  - Getting started and installation
  - SQL commands and queries
  - MATCH pattern queries for graph traversal
  - Console commands and administration
  - Java API and multi-model usage
  - Distributed architecture and clustering
  - Indexing and performance tuning
  - Security, authentication, and encryption
  - Graph API and Tinkerpop/Gremlin
  - Document API and schema management
  - Studio web interface
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class OrientDBScraper(BaseScraper):
    """Scrape OrientDB documentation across all sections."""

    SOURCES = {
        "getting-started": {
            "pages": {
                "https://orientdb.com/docs/3.2.x/": "OrientDB Manual",
                "https://orientdb.com/docs/3.2.x/gettingstarted/Tutorial-Installation.html": "Installation",
                "https://orientdb.com/docs/3.2.x/gettingstarted/Tutorial-Run-the-server.html": "Run the Server",
                "https://orientdb.com/docs/3.2.x/gettingstarted/Tutorial-Run-the-console.html": "Run the Console",
                "https://orientdb.com/docs/3.2.x/gettingstarted/demodb/": "Demo Database",
                "https://orientdb.com/docs/3.2.x/release/3.2/What-is-new.html": "What Is New in 3.2",
                "https://orientdb.com/docs/3.2.x/misc/Upgrade.html": "Upgrade Guide",
            },
        },
        "sql": {
            "pages": {
                "https://orientdb.com/docs/3.2.x/sql/": "SQL Overview",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Introduction.html": "SQL Introduction",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Query.html": "SELECT Query",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Insert.html": "INSERT Statement",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Update.html": "UPDATE Statement",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Delete.html": "DELETE Statement",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Create-Class.html": "CREATE CLASS",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Alter-Class.html": "ALTER CLASS",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Drop-Class.html": "DROP CLASS",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Create-Property.html": "CREATE PROPERTY",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Alter-Property.html": "ALTER PROPERTY",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Drop-Property.html": "DROP PROPERTY",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Create-Vertex.html": "CREATE VERTEX",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Create-Edge.html": "CREATE EDGE",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Delete-Vertex.html": "DELETE VERTEX",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Delete-Edge.html": "DELETE EDGE",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Match.html": "MATCH (Graph Patterns)",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Traverse.html": "TRAVERSE",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Create-Index.html": "CREATE INDEX",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Drop-Index.html": "DROP INDEX",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Rebuild-Index.html": "REBUILD INDEX",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Functions.html": "SQL Functions",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Methods.html": "SQL Methods",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Where.html": "WHERE Clause",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Projections.html": "Projections",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Pagination.html": "Pagination",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Batch.html": "SQL Batch",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Create-Cluster.html": "CREATE CLUSTER",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Alter-Cluster.html": "ALTER CLUSTER",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Drop-Cluster.html": "DROP CLUSTER",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Truncate-Class.html": "TRUNCATE CLASS",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Truncate-Cluster.html": "TRUNCATE CLUSTER",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Create-Sequence.html": "CREATE SEQUENCE",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Alter-Sequence.html": "ALTER SEQUENCE",
                "https://orientdb.com/docs/3.2.x/sql/SQL-Drop-Sequence.html": "DROP SEQUENCE",
            },
        },
        "console": {
            "pages": {
                "https://orientdb.com/docs/3.2.x/console/": "Console Overview",
                "https://orientdb.com/docs/3.2.x/console/Console-Commands.html": "Console Commands",
                "https://orientdb.com/docs/3.2.x/console/Console-Command-Connect.html": "Console Connect",
                "https://orientdb.com/docs/3.2.x/console/Console-Command-Create-Database.html": "Console Create Database",
                "https://orientdb.com/docs/3.2.x/console/Console-Command-Drop-Database.html": "Console Drop Database",
                "https://orientdb.com/docs/3.2.x/console/Console-Command-Info.html": "Console Info",
                "https://orientdb.com/docs/3.2.x/console/Console-Command-Export.html": "Console Export",
                "https://orientdb.com/docs/3.2.x/console/Console-Command-Import.html": "Console Import",
                "https://orientdb.com/docs/3.2.x/console/Console-Command-Backup.html": "Console Backup",
                "https://orientdb.com/docs/3.2.x/console/Console-Command-Restore.html": "Console Restore",
            },
        },
        "java-api": {
            "pages": {
                "https://orientdb.com/docs/3.2.x/java/": "Java API Overview",
                "https://orientdb.com/docs/3.2.x/java/Java-MultiModel-API.html": "Multi-Model API",
                "https://orientdb.com/docs/3.2.x/java/Document-API.html": "Document API (Java)",
                "https://orientdb.com/docs/3.2.x/java/Graph-API.html": "Graph API (Java)",
                "https://orientdb.com/docs/3.2.x/java/Java-API-Document.html": "Document Database Java API",
                "https://orientdb.com/docs/3.2.x/java/Java-Query-API.html": "Query API",
                "https://orientdb.com/docs/3.2.x/java/Java-Traverse.html": "Java Traverse",
                "https://orientdb.com/docs/3.2.x/java/Object-DB-Interface.html": "Object Database Interface",
                "https://orientdb.com/docs/3.2.x/java/Transactions.html": "Transactions",
                "https://orientdb.com/docs/3.2.x/java/Java-Hooks.html": "Java Hooks (Triggers)",
                "https://orientdb.com/docs/3.2.x/java/Live-Query.html": "Live Query",
            },
        },
        "distributed": {
            "pages": {
                "https://orientdb.com/docs/3.2.x/distributed/Distributed-Architecture.html": "Distributed Architecture",
                "https://orientdb.com/docs/3.2.x/distributed/Distributed-Configuration.html": "Distributed Configuration",
                "https://orientdb.com/docs/3.2.x/distributed/Replication.html": "Replication",
                "https://orientdb.com/docs/3.2.x/distributed/Distributed-Sharding.html": "Distributed Sharding",
                "https://orientdb.com/docs/3.2.x/distributed/Tutorial-Setup-a-Distributed-Database.html": "Setup Distributed Database",
                "https://orientdb.com/docs/3.2.x/distributed/Distributed-Lifecycle.html": "Distributed Lifecycle",
            },
        },
        "indexing": {
            "pages": {
                "https://orientdb.com/docs/3.2.x/indexing/": "Indexing Overview",
                "https://orientdb.com/docs/3.2.x/indexing/Indexes.html": "Indexes",
                "https://orientdb.com/docs/3.2.x/indexing/SB-Tree-index.html": "SB-Tree Index",
                "https://orientdb.com/docs/3.2.x/indexing/Hash-Index.html": "Hash Index",
                "https://orientdb.com/docs/3.2.x/indexing/Full-Text-Index.html": "Full-Text Index",
                "https://orientdb.com/docs/3.2.x/indexing/Lucene-Full-Text-Index.html": "Lucene Full-Text Index",
                "https://orientdb.com/docs/3.2.x/indexing/Lucene-Spatial-Index.html": "Lucene Spatial Index",
                "https://orientdb.com/docs/3.2.x/indexing/Index-Performance-Tuning.html": "Index Performance Tuning",
            },
        },
        "security": {
            "pages": {
                "https://orientdb.com/docs/3.2.x/security/": "Security Overview",
                "https://orientdb.com/docs/3.2.x/security/Security.html": "Security Configuration",
                "https://orientdb.com/docs/3.2.x/security/Database-Security.html": "Database Security",
                "https://orientdb.com/docs/3.2.x/security/Server-Security.html": "Server Security",
                "https://orientdb.com/docs/3.2.x/security/Database-Encryption.html": "Database Encryption",
                "https://orientdb.com/docs/3.2.x/security/Security-OrientDB-New-Security-Features.html": "New Security Features",
                "https://orientdb.com/docs/3.2.x/security/SSL-DB.html": "SSL for Database Connections",
                "https://orientdb.com/docs/3.2.x/security/Security-LDAP.html": "LDAP Authentication",
                "https://orientdb.com/docs/3.2.x/security/Security-Kerberos.html": "Kerberos Authentication",
            },
        },
        "graph-api": {
            "pages": {
                "https://orientdb.com/docs/3.2.x/gettingstarted/Tutorial-Working-with-graphs.html": "Working with Graphs Tutorial",
                "https://orientdb.com/docs/3.2.x/tinkerpop3/OrientDB-TinkerPop3.html": "TinkerPop 3 Integration",
                "https://orientdb.com/docs/3.2.x/tinkerpop3/Graph-Factory.html": "Graph Factory",
                "https://orientdb.com/docs/3.2.x/tinkerpop3/OrientDB-Gremlin.html": "Gremlin with OrientDB",
                "https://orientdb.com/docs/3.2.x/general/Types-of-Databases.html": "Types of Databases",
                "https://orientdb.com/docs/3.2.x/datamodeling/Graph-Schema.html": "Graph Schema",
            },
        },
        "document-api": {
            "pages": {
                "https://orientdb.com/docs/3.2.x/general/Concepts.html": "Core Concepts",
                "https://orientdb.com/docs/3.2.x/datamodeling/": "Data Modeling",
                "https://orientdb.com/docs/3.2.x/general/Schema.html": "Schema Management",
                "https://orientdb.com/docs/3.2.x/general/Clusters.html": "Clusters",
                "https://orientdb.com/docs/3.2.x/general/Record-IDs.html": "Record IDs (RIDs)",
                "https://orientdb.com/docs/3.2.x/general/Types.html": "Data Types",
                "https://orientdb.com/docs/3.2.x/general/Inheritance.html": "Class Inheritance",
                "https://orientdb.com/docs/3.2.x/general/Fetching-Strategies.html": "Fetching Strategies",
            },
        },
        "studio": {
            "pages": {
                "https://orientdb.com/docs/3.2.x/studio/": "Studio Overview",
                "https://orientdb.com/docs/3.2.x/studio/Working-with-Studio.html": "Working with Studio",
                "https://orientdb.com/docs/3.2.x/studio/Studio-Query.html": "Studio Query Editor",
                "https://orientdb.com/docs/3.2.x/studio/Studio-Schema.html": "Studio Schema Manager",
                "https://orientdb.com/docs/3.2.x/studio/Studio-Graph.html": "Studio Graph Editor",
                "https://orientdb.com/docs/3.2.x/studio/Studio-Security.html": "Studio Security Manager",
                "https://orientdb.com/docs/3.2.x/studio/Studio-Backup-Management.html": "Studio Backup Management",
                "https://orientdb.com/docs/3.2.x/studio/Studio-Server-Management.html": "Studio Server Management",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"orientdb-{source_key}" if source_key else "orientdb"
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
            for suffix in [' - OrientDB Manual', ' | OrientDB', ' - OrientDB']:
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
                        "category": f"orientdb-{source_key}",
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
            self.log.info(f"=== Scraping orientdb/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    OrientDBScraper(base, source_key).run()
