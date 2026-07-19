#!/usr/bin/env python3
"""WikiChip scraper.

Uses the MediaWiki API to dynamically enumerate and scrape pages from
en.wikichip.org. Paginates through allpages, fetches each page's HTML,
strips it, and stores the content.

Key coverage: chips, microarchitectures, process nodes, companies
(Intel, AMD, TSMC, Samsung, ARM, NVIDIA, Qualcomm)

Max pages: 5000
Rate limit: 2.0s between fetches (be respectful, large site)
Est ~2000+ pages
"""
import re
import time
import html as html_mod
import urllib.parse
from scraper_base import BaseScraper


class WikiChipScraper(BaseScraper):
    """Scrape WikiChip pages via the MediaWiki API."""

    API_URL = "https://en.wikichip.org/w/api.php"
    BASE_URL = "https://en.wikichip.org/wiki/"
    MAX_PAGES = 5000

    # Pages matching these patterns are skipped
    SKIP_PATTERNS = [
        re.compile(r'^Talk:', re.IGNORECASE),
        re.compile(r'^User:', re.IGNORECASE),
        re.compile(r'^User talk:', re.IGNORECASE),
        re.compile(r'^WikiChip:', re.IGNORECASE),
        re.compile(r'^WikiChip talk:', re.IGNORECASE),
        re.compile(r'^Template:', re.IGNORECASE),
        re.compile(r'^Template talk:', re.IGNORECASE),
        re.compile(r'^Category:', re.IGNORECASE),
        re.compile(r'^Category talk:', re.IGNORECASE),
        re.compile(r'^Help:', re.IGNORECASE),
        re.compile(r'^Help talk:', re.IGNORECASE),
        re.compile(r'^File:', re.IGNORECASE),
        re.compile(r'^File talk:', re.IGNORECASE),
        re.compile(r'^MediaWiki:', re.IGNORECASE),
        re.compile(r'^Module:', re.IGNORECASE),
        re.compile(r'^Special:', re.IGNORECASE),
        re.compile(r'^Property:', re.IGNORECASE),
        re.compile(r'^Concept:', re.IGNORECASE),
        re.compile(r'^Form:', re.IGNORECASE),
        re.compile(r'^Widget:', re.IGNORECASE),
    ]

    SOURCES = {
        "wiki": {
            "pages": {}  # Populated dynamically via MediaWiki API
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"wikichip-{source_key}" if source_key else "wikichip"
        super().__init__(name, base_dir, interval_seconds=7200)
        self.source_key = source_key

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

    def _extract_title(self, html_content, fallback):
        """Extract page title from HTML."""
        match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            for suffix in [' - WikiChip', ' | WikiChip', ' - wikichip.org']:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            return title
        return fallback

    def _is_redirect_page(self, html_content):
        """Check if a page is a redirect."""
        if re.search(r'#REDIRECT', html_content[:2000], re.IGNORECASE):
            return True
        if re.search(r'class="mw-redirect"', html_content[:5000], re.IGNORECASE):
            return True
        return False

    def _is_disambiguation_page(self, html_content):
        """Check if a page is a disambiguation page."""
        if re.search(r'class="[^"]*disambiguation[^"]*"', html_content[:5000],
                      re.IGNORECASE):
            return True
        if re.search(r'disambiguation page', html_content[:5000], re.IGNORECASE):
            return True
        return False

    def _should_skip_title(self, title):
        """Check if a page title should be skipped based on namespace patterns."""
        for pattern in self.SKIP_PATTERNS:
            if pattern.match(title):
                return True
        return False

    def _enumerate_pages(self):
        """Use MediaWiki API to enumerate all pages in the main namespace."""
        pages = []
        apcontinue = None
        batch = 0

        while len(pages) < self.MAX_PAGES and self.running:
            params = {
                "action": "query",
                "list": "allpages",
                "aplimit": "50",
                "apnamespace": "0",
                "format": "json",
            }
            if apcontinue:
                params["apcontinue"] = apcontinue

            url = f"{self.API_URL}?{urllib.parse.urlencode(params)}"
            data = self.fetch_json(url)

            if not data:
                self.log.error("Failed to fetch page list from API")
                break

            query = data.get("query", {})
            allpages = query.get("allpages", [])

            for page in allpages:
                title = page.get("title", "")
                if title and not self._should_skip_title(title):
                    pages.append(title)
                    if len(pages) >= self.MAX_PAGES:
                        break

            batch += 1
            self.log.info(
                f"  API batch {batch}: got {len(allpages)} pages "
                f"(total collected: {len(pages)})"
            )

            cont = data.get("continue", {})
            apcontinue = cont.get("apcontinue")
            if not apcontinue:
                self.log.info("Reached end of page list")
                break

            time.sleep(0.5)  # Light rate limit on API calls

        self.log.info(f"Enumerated {len(pages)} pages total")
        return pages

    def _scrape_source(self, source_key, config):
        """Scrape all pages for a given source section."""
        count = 0

        if source_key == "wiki":
            # Dynamic enumeration via MediaWiki API
            self.log.info("Enumerating pages via MediaWiki API...")
            page_titles = self._enumerate_pages()

            for title in page_titles:
                if not self.running:
                    break

                encoded_title = urllib.parse.quote(title.replace(' ', '_'), safe='/:')
                url = f"{self.BASE_URL}{encoded_title}"
                item_id = self.make_id(url)

                content = self.fetch_url(url)

                if content and len(content) > 500:
                    # Skip redirects and disambiguation pages
                    if self._is_redirect_page(content):
                        continue
                    if self._is_disambiguation_page(content):
                        continue

                    text = self._strip_html(content)
                    if len(text) > 100:
                        page_title = self._extract_title(content, title)

                        if self.save_item(item_id, {
                            "title": page_title,
                            "content": text[:50000],
                            "url": url,
                            "category": "wikichip",
                            "type": "documentation",
                        }):
                            count += 1
                            self.log.info(f"  wiki: {page_title}")

                time.sleep(2.0)  # Respectful rate limit
        else:
            # Static pages from SOURCES dict
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
                            "category": "wikichip",
                            "type": "documentation",
                        }):
                            count += 1
                            self.log.info(f"  {source_key}: {title}")

                time.sleep(2.0)

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
            self.log.info(f"=== Scraping wikichip/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    WikiChipScraper(base, source_key).run()
