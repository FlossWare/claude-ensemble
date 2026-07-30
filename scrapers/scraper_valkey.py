#!/usr/bin/env python3
"""Valkey (Redis fork) documentation scraper.

Covers:
  - Getting started: installation, configuration, quickstart
  - Administration: server management, replication, benchmarks, debugging
  - Commands: all major command groups (strings, lists, sets, hashes, sorted sets, streams)
  - Data types: strings, lists, sets, hashes, sorted sets, streams, bitmaps, HyperLogLog
  - Persistence: RDB snapshots, AOF, hybrid persistence
  - Clustering: cluster tutorial, specification, failover
  - Security: ACLs, TLS/SSL, migration from Redis
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class ValkeyScraper(BaseScraper):
    """Scrape Valkey documentation across all sections."""

    SOURCES = {
        "getting-started": {
            "pages": {
                "https://valkey.io/docs/": "Valkey Documentation Home",
                "https://valkey.io/docs/get-started/": "Get Started with Valkey",
                "https://valkey.io/docs/install/": "Install Valkey",
                "https://valkey.io/docs/install/install-valkey/": "Install Valkey from Source",
                "https://valkey.io/docs/install/install-valkey-on-linux/": "Install Valkey on Linux",
                "https://valkey.io/docs/install/install-valkey-on-mac-os/": "Install Valkey on macOS",
                "https://valkey.io/docs/install/install-valkey-from-source/": "Build from Source",
                "https://valkey.io/docs/faq/": "Valkey FAQ",
            },
        },
        "administration": {
            "pages": {
                "https://valkey.io/docs/management/config/": "Valkey Configuration",
                "https://valkey.io/docs/management/replication/": "Valkey Replication",
                "https://valkey.io/docs/management/sentinel/": "Valkey Sentinel",
                "https://valkey.io/docs/management/admin/": "Valkey Administration",
                "https://valkey.io/docs/management/optimization/benchmarks/": "Valkey Benchmarks",
                "https://valkey.io/docs/management/optimization/memory-optimization/": "Memory Optimization",
                "https://valkey.io/docs/management/debugging/": "Debugging Valkey",
            },
        },
        "commands": {
            "pages": {
                "https://valkey.io/commands/": "Valkey Commands Reference",
                "https://valkey.io/commands/set/": "SET Command",
                "https://valkey.io/commands/get/": "GET Command",
                "https://valkey.io/commands/mget/": "MGET Command",
                "https://valkey.io/commands/incr/": "INCR Command",
                "https://valkey.io/commands/lpush/": "LPUSH Command",
                "https://valkey.io/commands/lrange/": "LRANGE Command",
                "https://valkey.io/commands/rpop/": "RPOP Command",
                "https://valkey.io/commands/sadd/": "SADD Command",
                "https://valkey.io/commands/smembers/": "SMEMBERS Command",
                "https://valkey.io/commands/sinter/": "SINTER Command",
                "https://valkey.io/commands/hset/": "HSET Command",
                "https://valkey.io/commands/hgetall/": "HGETALL Command",
                "https://valkey.io/commands/zadd/": "ZADD Command",
                "https://valkey.io/commands/zrange/": "ZRANGE Command",
                "https://valkey.io/commands/zrangebyscore/": "ZRANGEBYSCORE Command",
                "https://valkey.io/commands/xadd/": "XADD Command",
                "https://valkey.io/commands/xread/": "XREAD Command",
                "https://valkey.io/commands/xrange/": "XRANGE Command",
                "https://valkey.io/commands/xgroup/": "XGROUP Command",
                "https://valkey.io/commands/del/": "DEL Command",
                "https://valkey.io/commands/expire/": "EXPIRE Command",
                "https://valkey.io/commands/scan/": "SCAN Command",
                "https://valkey.io/commands/info/": "INFO Command",
            },
        },
        "data-types": {
            "pages": {
                "https://valkey.io/docs/topics/data-types/": "Valkey Data Types Overview",
                "https://valkey.io/docs/topics/data-types/strings/": "Strings",
                "https://valkey.io/docs/topics/data-types/lists/": "Lists",
                "https://valkey.io/docs/topics/data-types/sets/": "Sets",
                "https://valkey.io/docs/topics/data-types/hashes/": "Hashes",
                "https://valkey.io/docs/topics/data-types/sorted-sets/": "Sorted Sets",
                "https://valkey.io/docs/topics/data-types/streams/": "Streams",
                "https://valkey.io/docs/topics/data-types/bitmaps/": "Bitmaps",
                "https://valkey.io/docs/topics/data-types/hyperloglogs/": "HyperLogLog",
                "https://valkey.io/docs/topics/data-types/geospatial/": "Geospatial Indexes",
            },
        },
        "persistence": {
            "pages": {
                "https://valkey.io/docs/topics/persistence/": "Valkey Persistence",
                "https://valkey.io/docs/management/config-file/": "Configuration File Reference",
                "https://valkey.io/commands/bgsave/": "BGSAVE Command",
                "https://valkey.io/commands/bgrewriteaof/": "BGREWRITEAOF Command",
                "https://valkey.io/commands/save/": "SAVE Command",
                "https://valkey.io/commands/lastsave/": "LASTSAVE Command",
            },
        },
        "clustering": {
            "pages": {
                "https://valkey.io/docs/topics/cluster-tutorial/": "Cluster Tutorial",
                "https://valkey.io/docs/topics/cluster-spec/": "Cluster Specification",
                "https://valkey.io/commands/cluster-info/": "CLUSTER INFO Command",
                "https://valkey.io/commands/cluster-nodes/": "CLUSTER NODES Command",
                "https://valkey.io/commands/cluster-failover/": "CLUSTER FAILOVER Command",
            },
        },
        "security": {
            "pages": {
                "https://valkey.io/docs/topics/acl/": "Access Control Lists (ACLs)",
                "https://valkey.io/docs/topics/encryption/": "TLS/SSL Encryption",
                "https://valkey.io/docs/topics/security/": "Valkey Security",
                "https://valkey.io/commands/acl-setuser/": "ACL SETUSER Command",
                "https://valkey.io/commands/acl-getuser/": "ACL GETUSER Command",
                "https://valkey.io/commands/acl-list/": "ACL LIST Command",
                "https://valkey.io/commands/acl-deluser/": "ACL DELUSER Command",
                "https://valkey.io/commands/auth/": "AUTH Command",
                "https://valkey.io/docs/topics/migration/": "Migrating from Redis to Valkey",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"valkey-{source_key}" if source_key else "valkey"
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
            for suffix in [' | Valkey', ' - Valkey', ' | Valkey Documentation']:
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
                        "category": f"valkey-{source_key}",
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
            self.log.info(f"=== Scraping valkey/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    ValkeyScraper(base, source_key).run()
