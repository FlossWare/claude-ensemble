#!/usr/bin/env python3
"""Ghidra reverse engineering tool documentation scraper.

Covers:
  - Getting started: installation, project setup, basic navigation
  - Scripting: GhidraScript (Java), Python/Jython scripting, script manager
  - Analysis: headless analyzer, SLEIGH, decompiler, P-code, auto-analysis
  - API reference: Javadoc, Flat API, plugin development, version tracking
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class GhidraScraper(BaseScraper):
    """Scrape Ghidra documentation across all sections."""

    SOURCES = {
        "getting-started": {
            "pages": {
                "https://ghidra-sre.org/": "Ghidra Home",
                "https://ghidra-sre.org/InstallationGuide.html": "Ghidra Installation Guide",
                "https://ghidra-sre.org/CheatSheet.html": "Ghidra Cheat Sheet",
                "https://ghidra-sre.org/releaseNotes.html": "Ghidra Release Notes",
                "https://github.com/NationalSecurityAgency/ghidra/wiki": "Ghidra Wiki Home",
                "https://github.com/NationalSecurityAgency/ghidra/wiki/Frequently-asked-questions": "Ghidra FAQ",
                "https://github.com/NationalSecurityAgency/ghidra/wiki/Getting-Started": "Getting Started with Ghidra",
                "https://github.com/NationalSecurityAgency/ghidra/wiki/Installation-Guide": "Wiki Installation Guide",
                "https://github.com/NationalSecurityAgency/ghidra/wiki/Supported-Platforms": "Supported Platforms",
            },
        },
        "scripting": {
            "pages": {
                "https://github.com/NationalSecurityAgency/ghidra/wiki/GhidraScripting": "GhidraScript Overview",
                "https://github.com/NationalSecurityAgency/ghidra/wiki/Scripting-with-Python": "Python Scripting (Jython)",
                "https://github.com/NationalSecurityAgency/ghidra/wiki/Script-Manager": "Script Manager",
                "https://github.com/NationalSecurityAgency/ghidra/wiki/PyGhidra": "PyGhidra (CPython)",
                "https://ghidra.re/ghidra_docs/api/ghidra/app/script/GhidraScript.html": "GhidraScript API Class",
                "https://ghidra.re/ghidra_docs/api/ghidra/program/flatapi/FlatProgramAPI.html": "FlatProgramAPI Reference",
                "https://ghidra.re/ghidra_docs/api/ghidra/app/script/GhidraState.html": "GhidraState API",
                "https://ghidra.re/ghidra_docs/api/ghidra/program/flatapi/FlatDecompilerAPI.html": "FlatDecompilerAPI Reference",
            },
        },
        "analysis": {
            "pages": {
                "https://github.com/NationalSecurityAgency/ghidra/wiki/Headless-Analyzer": "Headless Analyzer",
                "https://github.com/NationalSecurityAgency/ghidra/wiki/Ghidra-from-the-command-line": "Ghidra Command Line",
                "https://github.com/NationalSecurityAgency/ghidra/wiki/SLEIGH": "SLEIGH Processor Specification",
                "https://ghidra.re/courses/languages/html/sleigh.html": "SLEIGH Language Reference",
                "https://ghidra.re/ghidra_docs/api/ghidra/app/decompiler/package-summary.html": "Decompiler Package",
                "https://ghidra.re/ghidra_docs/api/ghidra/program/model/pcode/package-summary.html": "P-code Package",
                "https://ghidra.re/ghidra_docs/api/ghidra/app/decompiler/DecompInterface.html": "DecompInterface API",
                "https://github.com/NationalSecurityAgency/ghidra/wiki/Auto-Analysis": "Auto-Analysis Overview",
                "https://github.com/NationalSecurityAgency/ghidra/wiki/Version-Tracking": "Version Tracking",
                "https://github.com/NationalSecurityAgency/ghidra/wiki/Debugger": "Ghidra Debugger",
                "https://ghidra.re/courses/languages/html/pcoderef.html": "P-code Reference Manual",
            },
        },
        "api-reference": {
            "pages": {
                "https://ghidra.re/ghidra_docs/api/": "Ghidra Javadoc Index",
                "https://ghidra.re/ghidra_docs/api/ghidra/program/model/listing/package-summary.html": "Listing Package (Program Model)",
                "https://ghidra.re/ghidra_docs/api/ghidra/program/model/mem/package-summary.html": "Memory Package",
                "https://ghidra.re/ghidra_docs/api/ghidra/program/model/symbol/package-summary.html": "Symbol Package",
                "https://ghidra.re/ghidra_docs/api/ghidra/program/model/data/package-summary.html": "Data Package",
                "https://ghidra.re/ghidra_docs/api/ghidra/program/model/address/package-summary.html": "Address Package",
                "https://ghidra.re/ghidra_docs/api/ghidra/framework/plugintool/package-summary.html": "Plugin Tool Framework",
                "https://ghidra.re/ghidra_docs/api/ghidra/app/plugin/core/analysis/package-summary.html": "Core Analysis Plugins",
                "https://github.com/NationalSecurityAgency/ghidra/wiki/Extension-Development": "Extension Development",
                "https://github.com/NationalSecurityAgency/ghidra/wiki/Ghidra-Plugin-Development": "Plugin Development Guide",
                "https://github.com/NationalSecurityAgency/ghidra/wiki/ChangeHistory": "Change History",
                "https://ghidra.re/ghidra_docs/api/ghidra/app/emulator/package-summary.html": "Emulator Package",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"ghidra-{source_key}" if source_key else "ghidra"
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
            for suffix in [' | Ghidra', ' - Ghidra', ' - NSA/ghidra Wiki']:
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
                        "category": f"ghidra-{source_key}",
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
            self.log.info(f"=== Scraping ghidra/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    GhidraScraper(base, source_key).run()
