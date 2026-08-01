#!/usr/bin/env python3
"""
Fleet Doc Site Scraper - Zero-dependency crawl of API documentation sites.

Crawls documentation sites, extracts text content, and POSTs to the
orchestrator's /store endpoint. Follows internal links within the same domain.

Usage:
    python3 fleet-doc-scraper.py [--api URL] [--max-pages N] [--delay SECS]

Zero external dependencies — runs on any fleet worker (pi-01, pi-02, etc.)
"""

import urllib.request
import urllib.parse
import json
import re
import html
import time
import sys
import hashlib
from collections import deque

API_URL = "http://aio-01:5000"
MAX_PAGES_PER_SITE = 200
CRAWL_DELAY = 1.0
USER_AGENT = "fleet-doc-scraper/1.0"

DOC_SITES = [
    {
        "name": "unstructured-transform",
        "start_urls": [
            "https://docs.unstructured.io/transform/overview",
            "https://docs.unstructured.io/transform/getting-started",
        ],
        "allowed_prefix": "https://docs.unstructured.io/transform",
        "category": "api-docs-unstructured",
    },
    {
        "name": "jina-api",
        "start_urls": [
            "https://docs.jina.ai/",
            "https://jina.ai/reranker",
            "https://jina.ai/embeddings",
            "https://jina.ai/reader",
            "https://jina.ai/segmenter",
        ],
        "allowed_prefix": "https://jina.ai/",
        "category": "api-docs-jina",
    },
    {
        "name": "chunkr",
        "start_urls": [
            "https://docs.chunkr.ai/",
            "https://docs.chunkr.ai/introduction",
        ],
        "allowed_prefix": "https://docs.chunkr.ai/",
        "category": "api-docs-chunkr",
    },
    {
        "name": "cohere-rerank",
        "start_urls": [
            "https://docs.cohere.com/docs/rerank-overview",
            "https://docs.cohere.com/reference/rerank",
            "https://docs.cohere.com/docs/rerank-best-practices",
        ],
        "allowed_prefix": "https://docs.cohere.com/",
        "category": "api-docs-cohere",
    },
    {
        "name": "voyage-rerank",
        "start_urls": [
            "https://docs.voyageai.com/docs/reranker",
            "https://docs.voyageai.com/docs/embeddings",
            "https://docs.voyageai.com/reference/rerank-api",
        ],
        "allowed_prefix": "https://docs.voyageai.com/",
        "category": "api-docs-voyage",
    },
    {
        "name": "openrouter",
        "start_urls": [
            "https://openrouter.ai/docs/api-reference/overview",
            "https://openrouter.ai/docs/api-reference/rerank",
        ],
        "allowed_prefix": "https://openrouter.ai/docs/",
        "category": "api-docs-openrouter",
    },
    {
        "name": "chonkie",
        "start_urls": [
            "https://docs.chonkie.ai/",
            "https://docs.chonkie.ai/getting-started/introduction",
        ],
        "allowed_prefix": "https://docs.chonkie.ai/",
        "category": "api-docs-chonkie",
    },
    {
        "name": "chunk-fit",
        "start_urls": [
            "https://chunk.fit/docs",
        ],
        "allowed_prefix": "https://chunk.fit/",
        "category": "api-docs-chunkfit",
    },
    {
        "name": "huggingface-rerankers",
        "start_urls": [
            "https://huggingface.co/BAAI/bge-reranker-v2-m3",
            "https://huggingface.co/BAAI/bge-reranker-base",
        ],
        "allowed_prefix": "https://huggingface.co/BAAI/bge-reranker",
        "category": "api-docs-huggingface-rerankers",
    },
]

TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
LINK_RE = re.compile(r'<a\s[^>]*href=["\']([^"\']+)["\']', re.IGNORECASE)
SCRIPT_STYLE_RE = re.compile(
    r"<(script|style|noscript)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE
)
NAV_FOOTER_RE = re.compile(
    r"<(nav|footer|header)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE
)


def fetch_page(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        if resp.headers.get_content_type() not in (
            "text/html",
            "application/xhtml+xml",
        ):
            return None
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")
    except Exception as e:
        print(f"  SKIP {url}: {e}")
        return None


def extract_text(raw_html):
    cleaned = SCRIPT_STYLE_RE.sub(" ", raw_html)
    cleaned = NAV_FOOTER_RE.sub(" ", cleaned)
    text = TAG_RE.sub(" ", cleaned)
    text = html.unescape(text)
    text = SPACE_RE.sub(" ", text).strip()
    return text


def extract_title(raw_html):
    m = re.search(r"<title[^>]*>([^<]+)</title>", raw_html, re.IGNORECASE)
    return html.unescape(m.group(1).strip()) if m else ""


def extract_links(raw_html, base_url):
    links = set()
    for match in LINK_RE.finditer(raw_html):
        href = match.group(1).split("#")[0].split("?")[0].strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:")):
            continue
        absolute = urllib.parse.urljoin(base_url, href)
        links.add(absolute)
    return links


def store_page(url, title, content, category, source):
    data = json.dumps(
        {
            "url": url,
            "title": title,
            "source": source,
            "content": content,
            "category": category,
        }
    ).encode()
    req = urllib.request.Request(
        f"{API_URL}/store",
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        return result.get("stored", False)
    except Exception as e:
        print(f"  STORE FAIL {url}: {e}")
        return False


def crawl_site(site_config, max_pages=MAX_PAGES_PER_SITE):
    name = site_config["name"]
    prefix = site_config["allowed_prefix"]
    category = site_config["category"]

    queue = deque(site_config["start_urls"])
    visited = set()
    stored = 0

    print(f"\n{'='*60}")
    print(f"Crawling: {name}")
    print(f"Prefix:   {prefix}")
    print(f"Seeds:    {len(site_config['start_urls'])}")
    print(f"{'='*60}")

    while queue and len(visited) < max_pages:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        raw = fetch_page(url)
        if not raw:
            continue

        title = extract_title(raw)
        text = extract_text(raw)

        if len(text) < 100:
            print(f"  SKIP (too short): {url}")
            continue

        if store_page(url, title, text, category, name):
            stored += 1
            print(f"  [{stored}/{len(visited)}] {title[:60]} ({len(text)} chars)")

        for link in extract_links(raw, url):
            if link.startswith(prefix) and link not in visited:
                queue.append(link)

        time.sleep(CRAWL_DELAY)

    print(f"\nDone: {name} — {stored} pages stored, {len(visited)} visited")
    return stored


def main():
    global API_URL, MAX_PAGES_PER_SITE, CRAWL_DELAY

    for arg in sys.argv[1:]:
        if arg.startswith("--api="):
            API_URL = arg.split("=", 1)[1]
        elif arg.startswith("--max-pages="):
            MAX_PAGES_PER_SITE = int(arg.split("=", 1)[1])
        elif arg.startswith("--delay="):
            CRAWL_DELAY = float(arg.split("=", 1)[1])

    print(f"Fleet Doc Scraper")
    print(f"API: {API_URL}")
    print(f"Max pages/site: {MAX_PAGES_PER_SITE}")
    print(f"Delay: {CRAWL_DELAY}s")
    print(f"Sites: {len(DOC_SITES)}")

    total = 0
    for site in DOC_SITES:
        try:
            count = crawl_site(site, MAX_PAGES_PER_SITE)
            total += count
        except Exception as e:
            print(f"ERROR crawling {site['name']}: {e}")

    print(f"\n{'='*60}")
    print(f"TOTAL: {total} pages stored across {len(DOC_SITES)} sites")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
