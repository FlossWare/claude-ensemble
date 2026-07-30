#!/usr/bin/env python3
"""Zig language documentation scraper.

Covers:
  - Language reference: comptime, error unions, optionals, async, allocators,
    packed structs, sentinel-terminated types, inline assembly
  - Standard library: os, net, crypto, mem, debug, fmt, fs, math, heap, http
  - Build system: build.zig, cross-compilation, C interop, release notes
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class ZigScraper(BaseScraper):
    """Scrape Zig language documentation from ziglang.org."""

    SOURCES = {
        "language-reference": {
            "pages": {
                # Main language reference (comprehensive single-page doc)
                "https://ziglang.org/documentation/master/": "Zig Language Reference",
                # Learning resources with distinct page content
                "https://ziglang.org/learn/": "Learn Zig",
                "https://ziglang.org/learn/overview/": "Why Zig?",
                "https://ziglang.org/learn/build-system/": "Zig Build System",
                # Release notes (each is a distinct page)
                "https://ziglang.org/download/0.11.0/release-notes/": "Release Notes 0.11.0",
                "https://ziglang.org/download/0.12.0/release-notes/": "Release Notes 0.12.0",
                "https://ziglang.org/download/0.13.0/release-notes/": "Release Notes 0.13.0",
                # Community
                "https://ziglang.org/zsf/": "Zig Software Foundation",
            },
        },
        "standard-library": {
            "pages": {
                # Standard library top-level (auto-generated docs, distinct pages)
                "https://ziglang.org/documentation/master/std/": "Zig Standard Library Overview",
                # Individual module pages (each is a separate HTML page)
                "https://ziglang.org/documentation/master/std/#std.os": "std.os",
                "https://ziglang.org/documentation/master/std/#std.net": "std.net",
                "https://ziglang.org/documentation/master/std/#std.crypto": "std.crypto",
                "https://ziglang.org/documentation/master/std/#std.mem": "std.mem",
                "https://ziglang.org/documentation/master/std/#std.debug": "std.debug",
                "https://ziglang.org/documentation/master/std/#std.fmt": "std.fmt",
                "https://ziglang.org/documentation/master/std/#std.fs": "std.fs",
                "https://ziglang.org/documentation/master/std/#std.math": "std.math",
                "https://ziglang.org/documentation/master/std/#std.heap": "std.heap",
                "https://ziglang.org/documentation/master/std/#std.http": "std.http",
                "https://ziglang.org/documentation/master/std/#std.json": "std.json",
                "https://ziglang.org/documentation/master/std/#std.io": "std.io",
                "https://ziglang.org/documentation/master/std/#std.log": "std.log",
                "https://ziglang.org/documentation/master/std/#std.testing": "std.testing",
                "https://ziglang.org/documentation/master/std/#std.Thread": "std.Thread",
                "https://ziglang.org/documentation/master/std/#std.ArrayList": "std.ArrayList",
                "https://ziglang.org/documentation/master/std/#std.HashMap": "std.HashMap",
                "https://ziglang.org/documentation/master/std/#std.sort": "std.sort",
                "https://ziglang.org/documentation/master/std/#std.process": "std.process",
                "https://ziglang.org/documentation/master/std/#std.ChildProcess": "std.ChildProcess",
                "https://ziglang.org/documentation/master/std/#std.compress": "std.compress",
                "https://ziglang.org/documentation/master/std/#std.time": "std.time",
                "https://ziglang.org/documentation/master/std/#std.rand": "std.rand",
            },
        },
        "build-system": {
            "pages": {
                # Zig build system guide (separate from language ref)
                "https://ziglang.org/documentation/master/#Build-System": "Build System Reference",
                "https://ziglang.org/documentation/master/#Zig-Build-System": "Zig Build System Details",
                "https://ziglang.org/documentation/master/#C-Interop": "C Interop",
                "https://ziglang.org/documentation/master/#WebAssembly": "WebAssembly Support",
                "https://ziglang.org/download/": "Zig Downloads",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"zig-{source_key}" if source_key else "zig"
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
            for suffix in [' - Zig', ' | Zig', ' - The Zig Programming Language']:
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
                        "category": f"zig-{source_key}",
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
            self.log.info(f"=== Scraping zig/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    ZigScraper(base, source_key).run()
