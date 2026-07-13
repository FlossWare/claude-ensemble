#!/usr/bin/env python3
"""
Firmware Documentation Crawler
Crawls DD-WRT, Tomato, and OpenWrt documentation sites to collect URLs.
"""

import requests
import re
import json
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import Set, List, Dict
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FirmwareDocCrawler:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.visited: Set[str] = set()
        self.firmware_urls: Dict[str, List[str]] = {
            'ddwrt': [],
            'tomato': [],
            'openwrt': []
        }

    def is_valid_doc_url(self, url: str, base_domain: str) -> bool:
        """Check if URL is a valid documentation page."""
        parsed = urlparse(url)

        # Must be from the same domain
        if base_domain not in parsed.netloc:
            return False

        # Skip non-documentation pages
        skip_patterns = [
            'special:', 'user:', 'talk:', 'file:', 'image:',
            'category:', 'template:', 'help:',
            'action=', 'do=login', 'do=register', 'do=media',
            '.png', '.jpg', '.gif', '.pdf', '.zip', '.tar.gz'
        ]

        url_lower = url.lower()
        for pattern in skip_patterns:
            if pattern in url_lower:
                return False

        return True

    def crawl_page(self, url: str, base_domain: str, max_depth: int = 3, current_depth: int = 0) -> Set[str]:
        """Recursively crawl a page and extract documentation URLs."""
        if current_depth > max_depth or url in self.visited:
            return set()

        self.visited.add(url)
        found_urls = {url}

        try:
            logger.info(f"Crawling (depth {current_depth}): {url}")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find all links
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(url, href)

                if self.is_valid_doc_url(full_url, base_domain) and full_url not in self.visited:
                    # Only recurse if we haven't hit max depth
                    if current_depth < max_depth:
                        found_urls.update(self.crawl_page(full_url, base_domain, max_depth, current_depth + 1))
                    else:
                        found_urls.add(full_url)

            time.sleep(0.5)  # Be polite

        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")

        return found_urls

    def crawl_ddwrt(self) -> List[str]:
        """Crawl DD-WRT wiki documentation."""
        logger.info("=== Crawling DD-WRT ===")

        # Start from known good pages (from web search)
        seed_urls = [
            'https://wiki.dd-wrt.com/wiki/index.php/Main_Page',
            'https://wiki.dd-wrt.com/wiki/What_is_DD-WRT%3F',
            'https://wiki.dd-wrt.com/wiki/Reset_And_Reboot',
            'https://wiki.dd-wrt.com/wiki/index.php/Installing_Entware',
            'https://wiki.dd-wrt.com/wiki/Additional_DNSMasq_Options',
            'https://wiki.dd-wrt.com/wiki/index.php/SmartDNS',
        ]

        all_urls = set()
        for seed in seed_urls:
            try:
                urls = self.crawl_page(seed, 'wiki.dd-wrt.com', max_depth=2)
                all_urls.update(urls)
                logger.info(f"Found {len(urls)} URLs from {seed}")
            except Exception as e:
                logger.error(f"Failed to crawl {seed}: {e}")

        self.firmware_urls['ddwrt'] = list(all_urls)
        logger.info(f"Total DD-WRT URLs: {len(all_urls)}")
        return list(all_urls)

    def crawl_tomato(self) -> List[str]:
        """Crawl FreshTomato wiki documentation."""
        logger.info("=== Crawling FreshTomato ===")

        seed_urls = [
            'https://wiki.freshtomato.org/doku.php/start',
            'https://wiki.freshtomato.org/doku.php/hardware_compatibility',
            'https://wiki.freshtomato.org/doku.php/basic-documentation',
            'https://wiki.freshtomato.org/doku.php/advanced-documentation',
            'https://wiki.freshtomato.org/doku.php/how-tos',
        ]

        all_urls = set()
        for seed in seed_urls:
            try:
                urls = self.crawl_page(seed, 'wiki.freshtomato.org', max_depth=2)
                all_urls.update(urls)
                logger.info(f"Found {len(urls)} URLs from {seed}")
            except Exception as e:
                logger.error(f"Failed to crawl {seed}: {e}")

        self.firmware_urls['tomato'] = list(all_urls)
        logger.info(f"Total Tomato URLs: {len(all_urls)}")
        return list(all_urls)

    def crawl_openwrt(self) -> List[str]:
        """Crawl OpenWrt documentation."""
        logger.info("=== Crawling OpenWrt ===")

        seed_urls = [
            'https://openwrt.org/docs/start',
            'https://openwrt.org/docs/guide-quick-start/start',
            'https://openwrt.org/docs/guide-user/start',
            'https://openwrt.org/docs/guide-developer/start',
            'https://openwrt.org/toh/start',  # Table of Hardware
            'https://openwrt.org/packages/start',
        ]

        all_urls = set()
        for seed in seed_urls:
            try:
                urls = self.crawl_page(seed, 'openwrt.org', max_depth=2)
                all_urls.update(urls)
                logger.info(f"Found {len(urls)} URLs from {seed}")
            except Exception as e:
                logger.error(f"Failed to crawl {seed}: {e}")

        self.firmware_urls['openwrt'] = list(all_urls)
        logger.info(f"Total OpenWrt URLs: {len(all_urls)}")
        return list(all_urls)

    def crawl_all(self) -> Dict[str, List[str]]:
        """Crawl all firmware documentation sites."""
        self.crawl_ddwrt()
        self.visited.clear()  # Reset for next crawl

        self.crawl_tomato()
        self.visited.clear()

        self.crawl_openwrt()

        return self.firmware_urls

    def save_results(self, output_file: str = 'firmware-urls.json'):
        """Save collected URLs to JSON file."""
        total = sum(len(urls) for urls in self.firmware_urls.values())

        output = {
            'total_urls': total,
            'by_firmware': {
                'ddwrt': len(self.firmware_urls['ddwrt']),
                'tomato': len(self.firmware_urls['tomato']),
                'openwrt': len(self.firmware_urls['openwrt'])
            },
            'urls': self.firmware_urls
        }

        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)

        logger.info(f"Saved {total} URLs to {output_file}")
        return output

def main():
    crawler = FirmwareDocCrawler()
    results = crawler.crawl_all()
    output = crawler.save_results('/tmp/firmware-urls.json')

    print("\n=== SUMMARY ===")
    print(f"Total URLs found: {output['total_urls']}")
    print(f"  DD-WRT:   {output['by_firmware']['ddwrt']}")
    print(f"  Tomato:   {output['by_firmware']['tomato']}")
    print(f"  OpenWrt:  {output['by_firmware']['openwrt']}")

    print("\nSample URLs:")
    for firmware, urls in results.items():
        print(f"\n{firmware.upper()}:")
        for url in urls[:5]:
            print(f"  - {url}")

if __name__ == '__main__':
    main()
