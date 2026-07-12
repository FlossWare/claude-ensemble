#!/usr/bin/env python3
"""
Queue Worker for Full-Content Scraping

Pulls URLs from the orchestrator REST API, fetches FULL page content,
and POSTs back to the API. No direct Redis/PostgreSQL access.

Architecture:
  1. GET /redis-queue/next from orchestrator API
  2. Fetch full page with requests
  3. Extract clean text (strip HTML tags)
  4. POST complete content to /store
  5. Report success/failure to API

Dependencies: requests only (no redis, no bs4 on nodes without it)

Usage:
  python3 redis-queue-worker.py [--hostname HOSTNAME]
"""

import sys
import os
import json
import time
import signal
import socket
import logging
import ipaddress
from datetime import datetime
from typing import Optional, Dict, Any
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests

# Configuration
API_BASE = "http://aio-01:5000"
STORE_ENDPOINT = f"{API_BASE}/store"
NEXT_ENDPOINT = f"{API_BASE}/redis-queue/next"
COMPLETE_ENDPOINT = f"{API_BASE}/redis-queue/complete"
FAILED_ENDPOINT = f"{API_BASE}/redis-queue/failed"
RATE_LIMIT_ENDPOINT = f"{API_BASE}/redis-queue/check-rate-limit"
POLL_INTERVAL = 2
MAX_RETRIES = 3

# Scraping settings
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
REQUEST_TIMEOUT = 30
MAX_CONTENT_SIZE = 10 * 1024 * 1024  # 10MB

PRIVATE_NETWORKS = [
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('169.254.0.0/16'),
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('fc00::/7'),
    ipaddress.ip_network('fe80::/10'),
]

# Logging
HOSTNAME = socket.gethostname()
LOG_DIR = os.path.expanduser("~/workers/logs")
LOG_FILE = f"{LOG_DIR}/scraper-worker-{HOSTNAME}.log"

handlers = [logging.StreamHandler(sys.stderr)]
try:
    os.makedirs(LOG_DIR, exist_ok=True)
    handlers.append(logging.FileHandler(LOG_FILE))
except OSError:
    print(f"Warning: cannot create log dir {LOG_DIR}, logging to stderr only", file=sys.stderr)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=handlers
)
logger = logging.getLogger(__name__)


class HTMLTextExtractor(HTMLParser):
    """Extract clean text from HTML without BeautifulSoup dependency."""

    SKIP_TAGS = {'script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript'}

    def __init__(self):
        super().__init__()
        self._text = []
        self._skip_depth = 0
        self.title = ''
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        if tag == 'title':
            self._in_title = True
        if tag == 'br':
            self._text.append('\n')

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag == 'title':
            self._in_title = False
        if tag in ('p', 'div', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'tr'):
            self._text.append('\n')

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._skip_depth == 0:
            self._text.append(data)

    def get_text(self):
        raw = ''.join(self._text)
        lines = [line.strip() for line in raw.split('\n') if line.strip()]
        return '\n'.join(lines)


def _is_private_ip(hostname: str) -> bool:
    """Check if hostname resolves to a private/reserved IP."""
    try:
        addr = socket.getaddrinfo(hostname, None)[0][4][0]
        ip = ipaddress.ip_address(addr)
        return any(ip in net for net in PRIVATE_NETWORKS)
    except (socket.gaierror, ValueError):
        return True


def _validate_url(url: str) -> bool:
    """Reject URLs targeting private networks or non-HTTP schemes."""
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return False
    if not parsed.hostname:
        return False
    if _is_private_ip(parsed.hostname):
        return False
    return True


class QueueWorker:
    """Worker that processes URLs via the orchestrator REST API."""

    # Sentinel: distinguishes "empty queue" from "API error" in get_next_url
    API_ERROR = object()

    def __init__(self, hostname: Optional[str] = None):
        self.hostname = hostname or HOSTNAME
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
        self._shutdown = False

        self.stats = {
            'processed': 0,
            'succeeded': 0,
            'failed': 0,
            'start_time': datetime.now().isoformat()
        }

    def get_next_url(self):
        """Fetch next URL from the orchestrator API.

        Returns:
            dict with at least 'url' key on success,
            None when queue is empty,
            self.API_ERROR on connection/API failure.
        """
        try:
            resp = self.session.get(
                NEXT_ENDPOINT,
                params={'worker_id': self.hostname},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and data.get('url'):
                    return data
                logger.debug("API returned 200 but no url field")
                return None
            if resp.status_code == 204:
                return None
            logger.debug(f"No items: HTTP {resp.status_code}")
            return None
        except Exception as e:
            logger.warning(f"Failed to get next URL: {e}")
            return self.API_ERROR

    def report_complete(self, url: str):
        """Report successful processing to API."""
        try:
            self.session.post(
                COMPLETE_ENDPOINT,
                json={'url': url, 'worker_id': self.hostname},
                timeout=5
            )
        except Exception as e:
            logger.warning(f"Failed to report complete for {url}: {e}")

    def report_failed(self, url: str, error: str):
        """Report failed processing to API."""
        try:
            self.session.post(
                FAILED_ENDPOINT,
                json={'url': url, 'error': error[:500], 'worker_id': self.hostname},
                timeout=5
            )
        except Exception as e:
            logger.warning(f"Failed to report failure for {url}: {e}")

    def check_rate_limit(self, domain: str) -> bool:
        """Check if domain is rate-limited via API."""
        try:
            resp = self.session.get(
                f"{RATE_LIMIT_ENDPOINT}/{domain}",
                timeout=5
            )
            if resp.status_code == 200:
                return resp.json().get('allowed', True)
            return True
        except Exception:
            return True

    def fetch_page_content(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch page content and extract clean text."""
        if not _validate_url(url):
            logger.warning(f"Rejected URL (private/invalid): {url}")
            return None

        try:
            logger.info(f"Fetching {url}")
            resp = self.session.get(
                url,
                timeout=REQUEST_TIMEOUT,
                stream=True,
                allow_redirects=True
            )
            resp.raise_for_status()

            content_length = int(resp.headers.get('Content-Length', 0))
            if content_length > MAX_CONTENT_SIZE:
                logger.warning(f"Content too large: {content_length} bytes for {url}")
                return None

            raw_chunks = []
            total_bytes = 0
            for chunk in resp.iter_content(chunk_size=65536):
                total_bytes += len(chunk)
                if total_bytes > MAX_CONTENT_SIZE:
                    logger.warning(f"Content exceeded size limit for {url}")
                    return None
                raw_chunks.append(chunk)
            html = b''.join(raw_chunks).decode('utf-8', errors='replace')

            content_type = resp.headers.get('Content-Type', '')
            if 'text/plain' in content_type:
                clean_text = html.strip()
                title = urlparse(url).path.split('/')[-1]
            else:
                extractor = HTMLTextExtractor()
                extractor.feed(html)
                clean_text = extractor.get_text()
                title = extractor.title.strip() or urlparse(url).path

            if len(clean_text) < 50:
                logger.warning(f"Content too short ({len(clean_text)} chars) for {url}")
                return None

            logger.info(f"Fetched {len(clean_text)} chars from {url}")

            return {
                'content': clean_text,
                'title': title,
                'fetched_at': datetime.now().isoformat(),
                'content_type': content_type,
                'url': resp.url
            }

        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching {url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            return None

    def store_content(self, url: str, category: str, page_data: Dict[str, Any]) -> bool:
        """POST content to /store endpoint."""
        try:
            payload = {
                'url': page_data['url'],
                'source': 'queue-worker',
                'category': category,
                'content': page_data['content'],
                'title': page_data['title'],
                'fetched_at': page_data['fetched_at'],
                'original_url': url,
                'worker': self.hostname,
                'content_type': page_data.get('content_type', '')
            }

            resp = self.session.post(STORE_ENDPOINT, json=payload, timeout=10)

            if resp.status_code in [200, 201, 202]:
                result = resp.json()
                logger.info(f"Stored {url} → {result.get('path', 'ok')}")
                return True
            else:
                logger.error(f"Store failed for {url}: HTTP {resp.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error storing {url}: {e}")
            return False

    def process_item(self, item: Dict[str, Any]) -> bool:
        """Process a single queue item."""
        url = item.get('url', '')
        category = item.get('category', 'unknown')

        if not url:
            return False

        domain = urlparse(url).netloc
        if not self.check_rate_limit(domain):
            logger.warning(f"Rate limited: {domain}")
            self.report_failed(url, f'Rate limited for domain: {domain}')
            time.sleep(10)
            return False

        page_data = self.fetch_page_content(url)
        if not page_data:
            self.report_failed(url, 'Failed to fetch content')
            return False

        stored = self.store_content(url, category, page_data)
        if stored:
            self.report_complete(url)
        else:
            self.report_failed(url, 'Failed to store content')

        return stored

    def run(self):
        """Main worker loop."""
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, '_shutdown', True))

        logger.info(f"Worker starting on {self.hostname}")
        logger.info(f"API: {API_BASE}")
        logger.info(f"Logging to {LOG_FILE}")

        api_backoff = 1
        try:
            while not self._shutdown:
                item = self.get_next_url()

                if item is self.API_ERROR:
                    logger.warning(f"API unreachable, backing off {api_backoff}s")
                    time.sleep(min(api_backoff, 60))
                    api_backoff *= 2
                    continue

                if item is None:
                    time.sleep(POLL_INTERVAL)
                    api_backoff = 1
                    continue

                api_backoff = 1
                self.stats['processed'] += 1

                try:
                    success = self.process_item(item)
                except Exception as e:
                    logger.error(f"Unhandled error processing {item.get('url', '?')}: {e}")
                    success = False

                if success:
                    self.stats['succeeded'] += 1
                else:
                    self.stats['failed'] += 1

                if self.stats['processed'] % 10 == 0:
                    logger.info(
                        f"Stats: {self.stats['processed']} processed, "
                        f"{self.stats['succeeded']} succeeded, "
                        f"{self.stats['failed']} failed"
                    )

        except KeyboardInterrupt:
            logger.info("Worker stopping (Ctrl+C)")
        finally:
            logger.info(
                f"Final stats: {self.stats['processed']} processed, "
                f"{self.stats['succeeded']} succeeded, "
                f"{self.stats['failed']} failed"
            )


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Queue worker for full-content scraping")
    parser.add_argument('--hostname', help='Override hostname')
    args = parser.parse_args()

    worker = QueueWorker(hostname=args.hostname)
    worker.run()


if __name__ == '__main__':
    main()
