#!/usr/bin/env python3
"""Wikibooks Cookbook scraper.

Uses the MediaWiki API to dynamically enumerate and scrape pages from
en.wikibooks.org. Covers the Cookbook: and Bartending: namespaces
plus a curated set of food science reference pages.

Max pages: 2000
Rate limit: 1.5s between page fetches, 0.5s between API calls
"""
import re
import time
import html as html_mod
import urllib.parse
from scraper_base import BaseScraper


class WikibooksCookbookScraper(BaseScraper):
    """Scrape Wikibooks Cookbook pages via the MediaWiki API."""

    API_URL = "https://en.wikibooks.org/w/api.php"
    BASE_URL = "https://en.wikibooks.org/wiki/"
    MAX_PAGES = 2000

    # Pages matching these patterns are skipped
    SKIP_PATTERNS = [
        re.compile(r'^Talk:', re.IGNORECASE),
        re.compile(r'^User:', re.IGNORECASE),
        re.compile(r'^User talk:', re.IGNORECASE),
        re.compile(r'^Wikibooks:', re.IGNORECASE),
        re.compile(r'^Wikibooks talk:', re.IGNORECASE),
        re.compile(r'^Template:', re.IGNORECASE),
        re.compile(r'^Template talk:', re.IGNORECASE),
        re.compile(r'^Category:', re.IGNORECASE),
        re.compile(r'^Help:', re.IGNORECASE),
        re.compile(r'^Module:', re.IGNORECASE),
        re.compile(r'^Subject:', re.IGNORECASE),
        re.compile(r'^File:', re.IGNORECASE),
    ]

    SOURCES = {
        "cookbook": {
            "pages": {}  # Populated dynamically via MediaWiki API with prefix "Cookbook:"
        },
        "bartending": {
            "pages": {}  # Populated dynamically via MediaWiki API with prefix "Bartending:"
        },
        "food-science": {
            "pages": {
                "https://en.wikibooks.org/wiki/Food_Science": "Food Science",
                "https://en.wikibooks.org/wiki/Cookbook:Food_preservation": "Food Preservation",
                "https://en.wikibooks.org/wiki/Cookbook:Cooking_techniques": "Cooking Techniques",
                "https://en.wikibooks.org/wiki/Cookbook:Kitchen_safety": "Kitchen Safety",
                "https://en.wikibooks.org/wiki/Cookbook:Nutrition": "Nutrition",
                "https://en.wikibooks.org/wiki/Cookbook:Food_storage": "Food Storage",
                "https://en.wikibooks.org/wiki/Cookbook:Equipment": "Equipment",
                "https://en.wikibooks.org/wiki/Cookbook:Ingredients": "Ingredients",
                "https://en.wikibooks.org/wiki/Cookbook:Glossary": "Glossary",
                "https://en.wikibooks.org/wiki/Cookbook:Table_of_Contents": "Table of Contents",
                "https://en.wikibooks.org/wiki/Cookbook:Cuisine": "Cuisine Overview",
                "https://en.wikibooks.org/wiki/Cookbook:Baking": "Baking",
                "https://en.wikibooks.org/wiki/Cookbook:Grilling": "Grilling",
                "https://en.wikibooks.org/wiki/Cookbook:Steaming": "Steaming",
                "https://en.wikibooks.org/wiki/Cookbook:Frying": "Frying",
                "https://en.wikibooks.org/wiki/Cookbook:Boiling": "Boiling",
                "https://en.wikibooks.org/wiki/Cookbook:Roasting": "Roasting",
                "https://en.wikibooks.org/wiki/Cookbook:Braising": "Braising",
                "https://en.wikibooks.org/wiki/Cookbook:Sauteing": "Sauteing",
                "https://en.wikibooks.org/wiki/Cookbook:Poaching": "Poaching",
            },
        },
    }

    # Map source keys to their MediaWiki API prefix for dynamic enumeration
    DYNAMIC_PREFIXES = {
        "cookbook": "Cookbook:",
        "bartending": "Bartending:",
    }

    def __init__(self, base_dir, source_key=None):
        name = f"wikibooks-cookbook-{source_key}" if source_key else "wikibooks-cookbook"
        super().__init__(name, base_dir, interval_seconds=7200)
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
            for suffix in [' - Wikibooks, open books for an open world', ' - Wikibooks']:
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

    def _enumerate_pages(self, prefix):
        """Use MediaWiki API to enumerate pages with given prefix."""
        pages = []
        apcontinue = None
        batch = 0

        while len(pages) < self.MAX_PAGES and self.running:
            params = {
                "action": "query",
                "list": "allpages",
                "aplimit": "50",
                "apnamespace": "0",
                "apprefix": prefix,
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

        if source_key in self.DYNAMIC_PREFIXES:
            # Dynamic enumeration via MediaWiki API
            prefix = self.DYNAMIC_PREFIXES[source_key]
            self.log.info(f"Enumerating pages via MediaWiki API (prefix: {prefix})...")
            page_titles = self._enumerate_pages(prefix)

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
                            "category": f"wikibooks-cookbook-{source_key}",
                            "type": "documentation",
                        }):
                            count += 1
                            self.log.info(f"  {source_key}: {page_title}")

                time.sleep(1.5)  # Rate limit
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
                            "category": f"wikibooks-cookbook-{source_key}",
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
            self.log.info(f"=== Scraping wikibooks-cookbook/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    WikibooksCookbookScraper(base, source_key).run()
