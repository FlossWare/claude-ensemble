#!/usr/bin/env python3
"""Sumo Logic documentation scraper.

Discovers all doc pages from the sitemap at:
  https://www.sumologic.com/help/sitemap.xml

Covers ~2,100+ pages across all sections:
  alerts, apm, cloud-soar, cse (Cloud SIEM), dashboards, get-started,
  integrations, manage, metrics, observability, platform-services,
  search, security, send-data, api, and more.

Usage:
    python3 scraper_sumologic.py                # all docs
    python3 scraper_sumologic.py search         # only /docs/search/* pages
    python3 scraper_sumologic.py cse            # only /docs/cse/* pages
"""
import re
import time
import html as html_mod
import xml.etree.ElementTree as ET
from scraper_base import BaseScraper


SITEMAP_URL = "https://www.sumologic.com/help/sitemap.xml"
DOCS_PREFIX = "https://www.sumologic.com/help/docs/"


class SumoLogicScraper(BaseScraper):
    """Scrape Sumo Logic official documentation via sitemap discovery."""

    def __init__(self, base_dir, section_filter=None):
        name = f"sumologic-{section_filter}" if section_filter else "sumologic"
        super().__init__(name, base_dir, interval_seconds=3600)
        self.section_filter = section_filter

    def _fetch_doc_urls(self):
        """Fetch all /docs/ URLs from the sitemap, excluding tag pages."""
        self.log.info(f"Fetching sitemap: {SITEMAP_URL}")
        xml_content = self.fetch_url(SITEMAP_URL, timeout=60)
        if not xml_content:
            self.log.error("Failed to fetch sitemap")
            return []

        root = ET.fromstring(xml_content)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        urls = []
        for url_elem in root.findall("sm:url", ns):
            loc = url_elem.find("sm:loc", ns)
            if loc is not None and loc.text:
                u = loc.text.strip()
                if u.startswith(DOCS_PREFIX) and "/tags/" not in u:
                    urls.append(u)

        if self.section_filter:
            prefix = f"{DOCS_PREFIX}{self.section_filter}/"
            urls = [u for u in urls if u.startswith(prefix)]

        self.log.info(f"Found {len(urls)} doc pages"
                      + (f" (filter: {self.section_filter})" if self.section_filter else ""))
        return sorted(urls)

    def _derive_section(self, url):
        """Extract section name from URL for logging."""
        after = url[len(DOCS_PREFIX):]
        return after.split("/")[0] if "/" in after else after

    def _strip_html(self, html_content):
        """Remove HTML tags, scripts, styles and normalize whitespace."""
        text = html_content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
        text = re.sub(r'<header[^>]*>.*?</header>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_mod.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_title(self, html_content):
        """Extract page title from HTML <title> tag."""
        match = re.search(
            r'<title[^>]*>([^<]+)</title>', html_content, re.IGNORECASE
        )
        if match:
            title = match.group(1).strip()
            for suffix in [' | Sumo Logic Docs', ' - Sumo Logic']:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            return title
        return None

    def _extract_description(self, html_content):
        """Extract meta description."""
        match = re.search(
            r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']',
            html_content, re.IGNORECASE,
        )
        if match:
            return html_mod.unescape(match.group(1).strip())
        return ""

    def scrape(self):
        """Discover pages via sitemap and scrape each one."""
        urls = self._fetch_doc_urls()
        if not urls:
            return 0

        total = 0
        current_section = ""

        for i, url in enumerate(urls):
            if not self.running:
                break

            section = self._derive_section(url)
            if section != current_section:
                current_section = section
                self.log.info(f"=== Section: {section} ===")

            item_id = self.make_id(url)
            content = self.fetch_url(url)

            if content and len(content) > 500:
                text = self._strip_html(content)
                if len(text) > 100:
                    title = self._extract_title(content) or section
                    description = self._extract_description(content)

                    if self.save_item(item_id, {
                        "title": title,
                        "description": description,
                        "content": text[:50000],
                        "url": url,
                        "category": "sumologic",
                        "section": section,
                        "type": "documentation",
                    }):
                        total += 1

            if (i + 1) % 50 == 0:
                self.log.info(f"Progress: {i + 1}/{len(urls)} pages, {total} new")

            time.sleep(0.8)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    section_filter = sys.argv[1] if len(sys.argv) > 1 else None
    SumoLogicScraper(base, section_filter).run()
