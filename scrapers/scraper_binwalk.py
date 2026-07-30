#!/usr/bin/env python3
"""Binwalk firmware analysis tool documentation scraper.

Covers:
  - Usage: installation, basic scanning, extraction, entropy analysis
  - Modules: signature scanning, entropy, raw compression, custom signatures
  - API: Python binwalk module, programmatic scanning, plugins
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class BinwalkScraper(BaseScraper):
    """Scrape Binwalk documentation across all sections."""

    SOURCES = {
        "usage": {
            "pages": {
                "https://github.com/ReFirmLabs/binwalk": "Binwalk GitHub Home",
                "https://github.com/ReFirmLabs/binwalk/blob/master/README.md": "Binwalk README",
                "https://github.com/ReFirmLabs/binwalk/wiki": "Binwalk Wiki Home",
                "https://github.com/ReFirmLabs/binwalk/wiki/Quick-Start-Guide": "Quick Start Guide",
                "https://github.com/ReFirmLabs/binwalk/wiki/Installation": "Installation",
                "https://github.com/ReFirmLabs/binwalk/wiki/Usage": "Usage Guide",
                "https://github.com/ReFirmLabs/binwalk/wiki/Scanning-and-Extracting": "Scanning and Extracting",
                "https://binwalk.readthedocs.io/en/latest/": "Binwalk ReadTheDocs Home",
                "https://binwalk.readthedocs.io/en/latest/Installation/": "ReadTheDocs Installation",
            },
        },
        "modules": {
            "pages": {
                "https://github.com/ReFirmLabs/binwalk/wiki/Signature-Scanning": "Signature Scanning",
                "https://github.com/ReFirmLabs/binwalk/wiki/Entropy-Analysis": "Entropy Analysis",
                "https://github.com/ReFirmLabs/binwalk/wiki/Custom-Signatures": "Custom Signatures",
                "https://github.com/ReFirmLabs/binwalk/wiki/Extraction-Rules": "Extraction Rules",
                "https://github.com/ReFirmLabs/binwalk/wiki/Raw-Compression-Identification": "Raw Compression Identification",
                "https://github.com/ReFirmLabs/binwalk/wiki/Opcodes": "Opcode Scanning",
                "https://github.com/ReFirmLabs/binwalk/wiki/String-Search": "String Search Module",
            },
        },
        "api": {
            "pages": {
                "https://github.com/ReFirmLabs/binwalk/wiki/API": "Binwalk Python API",
                "https://github.com/ReFirmLabs/binwalk/wiki/Creating-Plugins": "Creating Plugins",
                "https://github.com/ReFirmLabs/binwalk/wiki/Module-Development": "Module Development",
                "https://binwalk.readthedocs.io/en/latest/API-Usage/": "ReadTheDocs API Usage",
                "https://binwalk.readthedocs.io/en/latest/Plugins/": "ReadTheDocs Plugins",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"binwalk-{source_key}" if source_key else "binwalk"
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
            for suffix in [' | Binwalk', ' - Binwalk', ' - ReFirmLabs/binwalk Wiki']:
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
                        "category": f"binwalk-{source_key}",
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
            self.log.info(f"=== Scraping binwalk/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    BinwalkScraper(base, source_key).run()
