#!/usr/bin/env python3
"""
Enhanced Firmware Documentation Crawler
Uses sitemap.xml, special pages, and API endpoints where available.
"""

import requests
import re
import json
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from typing import Set, List, Dict
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedFirmwareDocCrawler:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.firmware_urls: Dict[str, Set[str]] = {
            'ddwrt': set(),
            'tomato': set(),
            'openwrt': set()
        }

    def fetch_url(self, url: str, timeout: int = 10) -> str:
        """Fetch URL content with retry."""
        for attempt in range(3):
            try:
                response = self.session.get(url, timeout=timeout)
                response.raise_for_status()
                return response.text
            except Exception as e:
                if attempt == 2:
                    logger.error(f"Failed to fetch {url}: {e}")
                    return ""
                time.sleep(1)
        return ""

    def crawl_ddwrt_allpages(self) -> Set[str]:
        """Use MediaWiki Special:AllPages to get all DD-WRT pages."""
        logger.info("=== Crawling DD-WRT via Special:AllPages ===")
        urls = set()

        # Try Special:AllPages
        base_url = "https://wiki.dd-wrt.com/wiki/index.php/Special:AllPages"

        try:
            html = self.fetch_url(base_url)
            soup = BeautifulSoup(html, 'html.parser')

            # Find all page links
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/wiki/' in href and 'Special:' not in href:
                    full_url = urljoin("https://wiki.dd-wrt.com", href)
                    urls.add(full_url)

            logger.info(f"Found {len(urls)} DD-WRT URLs from Special:AllPages")
        except Exception as e:
            logger.error(f"Error crawling DD-WRT AllPages: {e}")

        # Also try known category pages
        categories = [
            'Category:Router_Database',
            'Category:Basic_Tutorials',
            'Category:Advanced_Tutorials',
            'Category:Scripting',
            'Category:Networking',
            'Category:VPN',
        ]

        for cat in categories:
            cat_url = f"https://wiki.dd-wrt.com/wiki/index.php/{cat}"
            html = self.fetch_url(cat_url)
            if html:
                soup = BeautifulSoup(html, 'html.parser')
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if '/wiki/' in href and 'Special:' not in href:
                        full_url = urljoin("https://wiki.dd-wrt.com", href)
                        urls.add(full_url)

        return urls

    def crawl_openwrt_via_api(self) -> Set[str]:
        """Use DokuWiki API to get all OpenWrt pages."""
        logger.info("=== Crawling OpenWrt via index ===")
        urls = set()

        # Known documentation sections
        doc_sections = [
            '/docs/guide-quick-start/',
            '/docs/guide-user/',
            '/docs/guide-developer/',
            '/toh/',
            '/packages/',
        ]

        for section in doc_sections:
            # Try to get index page
            index_url = f"https://openwrt.org{section}start"
            html = self.fetch_url(index_url)
            if html:
                soup = BeautifulSoup(html, 'html.parser')
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if href.startswith(section) or href.startswith('/docs/'):
                        full_url = urljoin("https://openwrt.org", href)
                        # Remove anchors
                        full_url = full_url.split('#')[0]
                        urls.add(full_url)

        logger.info(f"Found {len(urls)} OpenWrt URLs")
        return urls

    def crawl_tomato_comprehensive(self) -> Set[str]:
        """Comprehensive Tomato crawl using sitemap."""
        logger.info("=== Crawling FreshTomato comprehensively ===")
        urls = set()

        # Get sitemap/index
        sitemap_url = "https://wiki.freshtomato.org/doku.php?do=index"
        html = self.fetch_url(sitemap_url)

        if html:
            soup = BeautifulSoup(html, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'doku.php' in href and 'do=login' not in href and 'do=register' not in href:
                    full_url = urljoin("https://wiki.freshtomato.org", href)
                    # Remove query params except id
                    parsed = urlparse(full_url)
                    if parsed.query:
                        params = parse_qs(parsed.query)
                        if 'id' in params:
                            full_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?id={params['id'][0]}"
                        else:
                            full_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    urls.add(full_url)

        # Also crawl from main documentation pages
        doc_pages = [
            'https://wiki.freshtomato.org/doku.php/documentation',
            'https://wiki.freshtomato.org/doku.php/basic-documentation',
            'https://wiki.freshtomato.org/doku.php/advanced-documentation',
            'https://wiki.freshtomato.org/doku.php/howtos',
        ]

        for page in doc_pages:
            html = self.fetch_url(page)
            if html:
                soup = BeautifulSoup(html, 'html.parser')
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if 'doku.php' in href:
                        full_url = urljoin("https://wiki.freshtomato.org", href)
                        parsed = urlparse(full_url)
                        if parsed.query:
                            params = parse_qs(parsed.query)
                            if 'id' in params:
                                full_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?id={params['id'][0]}"
                        urls.add(full_url)

        logger.info(f"Found {len(urls)} Tomato URLs")
        return urls

    def crawl_all(self) -> Dict[str, List[str]]:
        """Crawl all firmware documentation sites."""
        self.firmware_urls['ddwrt'] = self.crawl_ddwrt_allpages()
        self.firmware_urls['tomato'] = self.crawl_tomato_comprehensive()
        self.firmware_urls['openwrt'] = self.crawl_openwrt_via_api()

        # Convert sets to lists
        return {k: list(v) for k, v in self.firmware_urls.items()}

    def save_results(self, output_file: str = '/tmp/firmware-urls-enhanced.json'):
        """Save collected URLs to JSON file."""
        results = {k: list(v) for k, v in self.firmware_urls.items()}
        total = sum(len(urls) for urls in results.values())

        output = {
            'total_urls': total,
            'by_firmware': {
                'ddwrt': len(results['ddwrt']),
                'tomato': len(results['tomato']),
                'openwrt': len(results['openwrt'])
            },
            'urls': results
        }

        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)

        logger.info(f"Saved {total} URLs to {output_file}")
        return output

def main():
    crawler = EnhancedFirmwareDocCrawler()
    results = crawler.crawl_all()
    output = crawler.save_results()

    print("\n=== ENHANCED CRAWL SUMMARY ===")
    print(f"Total URLs found: {output['total_urls']}")
    print(f"  DD-WRT:   {output['by_firmware']['ddwrt']}")
    print(f"  Tomato:   {output['by_firmware']['tomato']}")
    print(f"  OpenWrt:  {output['by_firmware']['openwrt']}")

    print("\nSample URLs:")
    for firmware, urls in results.items():
        print(f"\n{firmware.upper()}:")
        for url in list(urls)[:5]:
            print(f"  - {url}")

if __name__ == '__main__':
    main()
