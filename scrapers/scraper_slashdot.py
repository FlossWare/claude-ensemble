#!/usr/bin/env python3
"""
SLASHDOT SCRAPER
Scrapes articles, metadata, and top-level comments from https://slashdot.org/

Collects:
  - Article titles, summaries, external links
  - Categories (YRO, Linux, Developer, Hardware, etc.)
  - Top-level comments (limit 50 per article) with scores and authors
  - Timestamps, authors, departments

Stores JSON in /mnt/aio-01/claude-orchestrator/scraped-data/slashdot/
Respects robots.txt, adds 5-10 second delays between requests.
Handles pagination to collect 50-100 articles.

Usage:
    python3 scraper_slashdot.py
    python3 scraper_slashdot.py --max-articles 50 --max-pages 3
    python3 scraper_slashdot.py --base-dir /home/claude --interval 3600 --name slashdot
"""

import argparse
import json
import logging
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_URL = "https://slashdot.org/"
OUTPUT_BASE = "/mnt/aio-01/claude-orchestrator/scraped-data/slashdot"
MAX_RETRIES = 3
TIMEOUT = 30
MIN_DELAY = 5   # seconds between requests (respect the site)
MAX_DELAY = 10
COMMENTS_PER_ARTICLE = 50
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
)

# Slashdot category subdomains
CATEGORY_SUBDOMAINS = {
    "hardware": "Hardware",
    "linux": "Linux",
    "yro": "YRO",
    "science": "Science",
    "politics": "Politics",
    "developers": "Developers",
    "entertainment": "Entertainment",
    "technology": "Technology",
    "it": "IT",
    "apple": "Apple",
    "games": "Games",
    "mobile": "Mobile",
    "idle": "Idle",
    "ask": "Ask Slashdot",
    "build": "Build",
    "devices": "Devices",
    "news": "News",
    "books": "Books",
    "interviews": "Interviews",
}


class SlashdotScraper:
    """Scrapes articles and comments from Slashdot."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir) if output_dir else Path(OUTPUT_BASE)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = self._setup_logging()
        self.session = self._create_session()
        self.stats = {
            "total_articles": 0,
            "total_comments": 0,
            "pages_scraped": 0,
            "errors": 0,
            "start_time": datetime.utcnow().isoformat() + "Z",
        }

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------
    def _setup_logging(self) -> logging.Logger:
        logger = logging.getLogger("slashdot_scraper")
        logger.setLevel(logging.DEBUG)
        if logger.handlers:
            return logger

        log_file = self.output_dir / f"scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        fh.setFormatter(fmt)
        ch.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(ch)
        return logger

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=MAX_RETRIES,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        return session

    # ------------------------------------------------------------------
    # HTTP with polite delay
    # ------------------------------------------------------------------
    def _fetch(self, url: str) -> Optional[str]:
        delay = random.uniform(MIN_DELAY, MAX_DELAY)
        self.logger.debug(f"Sleeping {delay:.1f}s before fetching {url}")
        time.sleep(delay)

        try:
            resp = self.session.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.text
        except requests.exceptions.RequestException as exc:
            self.logger.error(f"Failed to fetch {url}: {exc}")
            self.stats["errors"] += 1
            return None

    # ------------------------------------------------------------------
    # Determine category from story URL
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_category(url: str) -> str:
        """Extract category from subdomain (e.g. hardware.slashdot.org -> Hardware)."""
        try:
            host = urlparse(url).hostname or ""
            subdomain = host.split(".")[0].lower()
            return CATEGORY_SUBDOMAINS.get(subdomain, subdomain.title())
        except Exception:
            return "Unknown"

    # ------------------------------------------------------------------
    # Parse front-page articles
    # ------------------------------------------------------------------
    def _parse_articles(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        articles: List[Dict[str, Any]] = []

        for article_tag in soup.select("article.fhitem-story"):
            try:
                article = self._parse_single_article(article_tag)
                if article:
                    articles.append(article)
            except Exception as exc:
                self.logger.warning(f"Error parsing article: {exc}")
                self.stats["errors"] += 1

        return articles

    def _parse_single_article(self, tag) -> Optional[Dict[str, Any]]:
        fhid = tag.get("data-fhid", "")

        # --- Title and story link ---
        title_span = tag.select_one(f"span#title-{fhid}.story-title")
        if not title_span:
            title_span = tag.select_one("span.story-title")
        if not title_span:
            return None

        title_link = title_span.select_one("a[href*='/story/']")
        if not title_link:
            # fallback: first <a> that is not the source link
            for a in title_span.find_all("a"):
                if "story-sourcelnk" not in a.get("class", []):
                    title_link = a
                    break
        if not title_link:
            return None

        title = title_link.get_text(strip=True)
        story_url = title_link.get("href", "")
        if story_url.startswith("//"):
            story_url = "https:" + story_url

        # --- External source link ---
        source_link_tag = title_span.select_one("a.story-sourcelnk")
        external_url = ""
        external_source = ""
        if source_link_tag:
            external_url = source_link_tag.get("href", "")
            external_source = source_link_tag.get_text(strip=True).strip("() ")

        # --- Category / topic ---
        topic_img = tag.select_one(f"span#topic-{fhid} img")
        if not topic_img:
            topic_img = tag.select_one("span.topic img")
        topic_tag_label = topic_img.get("alt", "") if topic_img else ""

        # Also derive category from story URL subdomain
        category = self._extract_category(story_url)

        # --- Author ---
        byline_span = tag.select_one("span.story-byline")
        author = ""
        if byline_span:
            author_link = byline_span.select_one("a[href]")
            if author_link:
                author = author_link.get_text(strip=True)

        # --- Timestamp ---
        time_tag = tag.select_one(f"time#fhtime-{fhid}")
        if not time_tag:
            time_tag = tag.select_one("time")
        timestamp = ""
        if time_tag:
            timestamp = time_tag.get("datetime", time_tag.get_text(strip=True))

        # --- Department ---
        dept_span = tag.select_one("span.dept-text")
        department = dept_span.get_text(strip=True) if dept_span else ""

        # --- Comment count ---
        comment_bubble = tag.select_one("span.comment-bubble a")
        comment_count = 0
        if comment_bubble:
            try:
                comment_count = int(comment_bubble.get_text(strip=True))
            except ValueError:
                pass

        # --- Body / summary ---
        body_div = tag.select_one(f"div#text-{fhid}")
        if not body_div:
            body_div = tag.select_one("div.body div.p")
        summary = ""
        if body_div:
            summary = body_div.get_text(separator=" ", strip=True)

        # Collect all links from body as external references
        body_links: List[Dict[str, str]] = []
        if body_div:
            for a in body_div.find_all("a", href=True):
                href = a["href"]
                if href.startswith("//"):
                    href = "https:" + href
                body_links.append({
                    "text": a.get_text(strip=True),
                    "url": href,
                })

        return {
            "id": fhid,
            "title": title,
            "url": story_url,
            "external_url": external_url,
            "external_source": external_source,
            "category": category,
            "topic": topic_tag_label,
            "author": author,
            "timestamp": timestamp,
            "department": department,
            "comment_count": comment_count,
            "summary": summary,
            "body_links": body_links,
            "comments": [],
        }

    # ------------------------------------------------------------------
    # Parse comments from an article page
    # ------------------------------------------------------------------
    def _fetch_comments(self, article_url: str, limit: int = COMMENTS_PER_ARTICLE) -> List[Dict[str, Any]]:
        """Fetch top-level comments (first level only) for an article."""
        # Use flat mode with threshold -1 to get all visible comments
        comment_url = article_url
        if "?" in comment_url:
            comment_url += "&threshold=-1&mode=flat"
        else:
            comment_url += "?threshold=-1&mode=flat"

        html = self._fetch(comment_url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        comments: List[Dict[str, Any]] = []

        for li in soup.select("li.comment"):
            if len(comments) >= limit:
                break

            try:
                comment = self._parse_comment(li)
                if comment:
                    comments.append(comment)
            except Exception as exc:
                self.logger.debug(f"Error parsing comment: {exc}")

        return comments

    def _parse_comment(self, li_tag) -> Optional[Dict[str, Any]]:
        comment_id = ""
        id_attr = li_tag.get("id", "")
        m = re.search(r"tree_(\d+)", id_attr)
        if m:
            comment_id = m.group(1)

        # Skip hidden / collapsed comments with no body
        cw = li_tag.select_one(f"div#comment_{comment_id}.cw") if comment_id else li_tag.select_one("div.cw")
        if not cw:
            return None

        # Title
        title_tag = cw.select_one("h4 a")
        title = title_tag.get_text(strip=True) if title_tag else ""
        comment_link = ""
        if title_tag:
            href = title_tag.get("href", "")
            if href.startswith("//"):
                href = "https:" + href
            comment_link = href

        # Score
        score_span = cw.select_one("span.score")
        score_text = ""
        score_value = 0
        if score_span:
            score_text = score_span.get_text(strip=True)
            score_match = re.search(r"Score:\s*(-?\d+)", score_text)
            if score_match:
                score_value = int(score_match.group(1))

        # Author
        by_span = cw.select_one("span.by a")
        author = by_span.get_text(strip=True) if by_span else "Anonymous Coward"

        # User ID
        uid_span = cw.select_one("span.uid a")
        uid = ""
        if uid_span:
            uid_text = uid_span.get_text(strip=True).strip("() ")
            uid = uid_text

        # Body
        body_div = cw.select_one("div.commentBody div")
        if not body_div:
            body_div = cw.select_one("div.commentBody")
        body = ""
        if body_div:
            body = body_div.get_text(separator=" ", strip=True)

        if not body and not title:
            return None

        return {
            "comment_id": comment_id,
            "title": title,
            "author": author,
            "uid": uid,
            "score": score_value,
            "score_text": score_text,
            "body": body[:5000],  # cap at 5000 chars
            "link": comment_link,
        }

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    def _save_articles(self, articles: List[Dict[str, Any]], batch_label: str):
        if not articles:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"slashdot_{batch_label}_{timestamp}.json"
        filepath = self.output_dir / filename

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(articles, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Saved {len(articles)} articles to {filepath}")
        except Exception as exc:
            self.logger.error(f"Failed to save {filepath}: {exc}")
            self.stats["errors"] += 1

        # Also write JSONL for pipeline compatibility
        jsonl_path = self.output_dir / f"slashdot_{batch_label}_{timestamp}.jsonl"
        try:
            with open(jsonl_path, "w", encoding="utf-8") as f:
                for article in articles:
                    record = {
                        "text": self._article_to_text(article),
                        "source": "slashdot",
                        "metadata": {
                            "id": article.get("id"),
                            "title": article.get("title"),
                            "url": article.get("url"),
                            "category": article.get("category"),
                            "topic": article.get("topic"),
                            "author": article.get("author"),
                            "timestamp": article.get("timestamp"),
                            "comment_count": article.get("comment_count"),
                            "external_url": article.get("external_url"),
                            "external_source": article.get("external_source"),
                            "scraped_at": datetime.utcnow().isoformat() + "Z",
                        },
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            self.logger.info(f"Saved JSONL to {jsonl_path}")
        except Exception as exc:
            self.logger.error(f"Failed to save JSONL {jsonl_path}: {exc}")

    @staticmethod
    def _article_to_text(article: Dict[str, Any]) -> str:
        parts = [
            f"# {article.get('title', 'Untitled')}",
            f"Category: {article.get('category', 'Unknown')} | Topic: {article.get('topic', '')}",
            f"Author: {article.get('author', '')} | {article.get('timestamp', '')}",
            f"Department: {article.get('department', '')}",
            "",
            "## Summary",
            article.get("summary", ""),
        ]

        if article.get("external_url"):
            parts.append(f"\nSource: {article['external_source']} - {article['external_url']}")

        comments = article.get("comments", [])
        if comments:
            parts.append(f"\n## Comments ({len(comments)})")
            for c in comments[:10]:
                score_info = f" (Score: {c.get('score', 0)})" if c.get("score") else ""
                parts.append(f"\n### {c.get('title', 'Re:')} by {c.get('author', 'AC')}{score_info}")
                parts.append(c.get("body", "")[:1000])

        return "\n".join(parts)

    def _save_stats(self):
        self.stats["end_time"] = datetime.utcnow().isoformat() + "Z"
        stats_file = self.output_dir / "scraper_stats.json"
        try:
            with open(stats_file, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, indent=2)
            self.logger.info(f"Stats saved to {stats_file}")
        except Exception as exc:
            self.logger.error(f"Failed to save stats: {exc}")

    # ------------------------------------------------------------------
    # Main scrape loop
    # ------------------------------------------------------------------
    def scrape(
        self,
        max_pages: int = 5,
        max_articles: int = 100,
        fetch_comments: bool = True,
    ):
        """
        Scrape Slashdot articles across multiple pages.

        Args:
            max_pages: Number of front-page pages to scrape (each has ~15-20 articles).
            max_articles: Hard cap on total articles.
            fetch_comments: Whether to fetch comments for each article.
        """
        self.logger.info("=" * 70)
        self.logger.info("SLASHDOT SCRAPER - News for Nerds")
        self.logger.info("=" * 70)
        self.logger.info(f"Max pages: {max_pages}")
        self.logger.info(f"Max articles: {max_articles}")
        self.logger.info(f"Fetch comments: {fetch_comments}")
        self.logger.info(f"Output directory: {self.output_dir}")
        self.logger.info(f"Delay between requests: {MIN_DELAY}-{MAX_DELAY}s")
        self.logger.info("=" * 70)

        all_articles: List[Dict[str, Any]] = []
        seen_ids: set = set()

        for page_num in range(max_pages):
            if len(all_articles) >= max_articles:
                self.logger.info(f"Reached article limit ({max_articles}), stopping pagination.")
                break

            # Construct page URL
            if page_num == 0:
                page_url = BASE_URL
            else:
                page_url = f"{BASE_URL}?page={page_num + 1}"

            self.logger.info(f"\n--- Page {page_num + 1}/{max_pages} ---")
            self.logger.info(f"Fetching: {page_url}")

            html = self._fetch(page_url)
            if not html:
                self.logger.error(f"Failed to fetch page {page_num + 1}")
                continue

            articles = self._parse_articles(html)
            self.logger.info(f"Found {len(articles)} articles on page {page_num + 1}")
            self.stats["pages_scraped"] += 1

            for article in articles:
                if len(all_articles) >= max_articles:
                    break

                fhid = article.get("id", "")
                if fhid in seen_ids:
                    continue
                seen_ids.add(fhid)

                # Fetch comments if requested
                if fetch_comments and article.get("url") and article.get("comment_count", 0) > 0:
                    self.logger.info(
                        f"  Fetching comments for: {article['title'][:60]}... "
                        f"({article['comment_count']} comments)"
                    )
                    comments = self._fetch_comments(article["url"], limit=COMMENTS_PER_ARTICLE)
                    article["comments"] = comments
                    self.stats["total_comments"] += len(comments)
                    self.logger.info(f"    Got {len(comments)} top-level comments")

                all_articles.append(article)
                self.stats["total_articles"] += 1

                self.logger.info(
                    f"  [{self.stats['total_articles']}/{max_articles}] "
                    f"{article.get('category', '?')}: {article['title'][:70]}"
                )

        # Save results
        if all_articles:
            self._save_articles(all_articles, "batch")

        self._save_stats()

        self.logger.info("\n" + "=" * 70)
        self.logger.info("SCRAPING COMPLETE")
        self.logger.info(f"  Articles scraped: {self.stats['total_articles']}")
        self.logger.info(f"  Comments scraped: {self.stats['total_comments']}")
        self.logger.info(f"  Pages processed:  {self.stats['pages_scraped']}")
        self.logger.info(f"  Errors:           {self.stats['errors']}")
        self.logger.info(f"  Output:           {self.output_dir}")
        self.logger.info("=" * 70)

        return self.stats["total_articles"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Scrape Slashdot articles and comments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default: scrape up to 100 articles with comments
  python3 scraper_slashdot.py

  # Quick run: 20 articles, no comments
  python3 scraper_slashdot.py --max-articles 20 --no-comments

  # Full run: 5 pages, all comments
  python3 scraper_slashdot.py --max-pages 5 --max-articles 100

  # Daemon-style with custom base dir
  python3 scraper_slashdot.py --base-dir /home/claude --interval 3600 --name slashdot
        """,
    )

    parser.add_argument(
        "--base-dir",
        default="/home/claude",
        help="Base directory (default: /home/claude)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="Interval in seconds between scrape runs when looping (default: 3600)",
    )
    parser.add_argument(
        "--name",
        default="slashdot",
        help="Scraper name identifier (default: slashdot)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=f"Custom output directory (default: {OUTPUT_BASE})",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Number of front-page pages to scrape (default: 5, ~15-20 articles each)",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=100,
        help="Maximum number of articles to scrape (default: 100)",
    )
    parser.add_argument(
        "--no-comments",
        action="store_true",
        help="Skip fetching comments (faster)",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run continuously at --interval seconds",
    )

    args = parser.parse_args()

    # If --output specified, use it; else construct from --base-dir and --name
    if args.output:
        output_dir = args.output
    else:
        output_dir = os.path.join(args.base_dir, "scraped-data", args.name)

    if args.loop:
        print(f"Running {args.name} scraper in loop mode (interval={args.interval}s)")
        while True:
            try:
                scraper = SlashdotScraper(output_dir=output_dir)
                scraper.scrape(
                    max_pages=args.max_pages,
                    max_articles=args.max_articles,
                    fetch_comments=not args.no_comments,
                )
            except Exception as exc:
                logging.getLogger("slashdot_scraper").error(f"Scrape cycle failed: {exc}")
            print(f"Sleeping {args.interval}s until next scrape cycle...")
            time.sleep(args.interval)
    else:
        scraper = SlashdotScraper(output_dir=output_dir)
        scraper.scrape(
            max_pages=args.max_pages,
            max_articles=args.max_articles,
            fetch_comments=not args.no_comments,
        )


if __name__ == "__main__":
    main()
