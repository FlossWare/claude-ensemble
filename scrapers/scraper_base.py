#!/usr/bin/env python3
"""Base scraper framework — writes to disk AND enqueues to pipeline via REST API."""

import json
import os
import time
import hashlib
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
import logging
import signal
import sys

API_BASE = "http://aio-01:5000"


class BaseScraper:
    """Base class for all scrapers."""

    def __init__(self, source_name, base_dir, interval_seconds=900):
        self.source_name = source_name
        self.base_dir = Path(base_dir) / "scraped-data" / source_name
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.interval = interval_seconds
        self.running = True
        self.stats = {"fetched": 0, "enqueued": 0, "errors": 0,
                      "started": datetime.now(timezone.utc).isoformat()}
        self._enqueue_batch = []
        self._enqueue_batch_size = 20

        log_dir = Path(base_dir) / "scraped-data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format=f'%(asctime)s [{source_name}] %(levelname)s: %(message)s',
            handlers=[
                logging.FileHandler(log_dir / f"{source_name}.log"),
                logging.StreamHandler()
            ]
        )
        self.log = logging.getLogger(source_name)

        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def _shutdown(self, signum, frame):
        self.log.info(f"Shutdown signal received (signal {signum})")
        self.running = False
        self._flush_enqueue()

    def make_id(self, text):
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def fetch_url(self, url, headers=None, timeout=30):
        req = urllib.request.Request(url)
        req.add_header("User-Agent",
                       "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0")
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            self.log.error(f"Fetch failed for {url}: {e}")
            self.stats["errors"] += 1
            return None

    def fetch_json(self, url, headers=None, timeout=30):
        body = self.fetch_url(url, headers, timeout)
        if body:
            try:
                return json.loads(body)
            except json.JSONDecodeError as e:
                self.log.error(f"JSON parse failed: {e}")
                self.stats["errors"] += 1
        return None

    def _enqueue_to_pipeline(self, data):
        """Queue document for ingest pipeline (ingest->chunk->embed)."""
        content = data.get("content", data.get("text", data.get("abstract", "")))
        if not content or len(str(content).strip()) < 50:
            return

        url = data.get("url", "")
        title = data.get("title", "")[:500] or "Untitled"

        self._enqueue_batch.append({
            "content": str(content)[:50000],
            "url": url,
            "title": title,
            "source": self.source_name,
        })

        if len(self._enqueue_batch) >= self._enqueue_batch_size:
            self._flush_enqueue()

    def _flush_enqueue(self):
        """Flush pending batch to ingest:documents queue via REST API."""
        if not self._enqueue_batch:
            return
        try:
            batch = self._enqueue_batch[:self._enqueue_batch_size]
            self._enqueue_batch = self._enqueue_batch[self._enqueue_batch_size:]

            req = urllib.request.Request(
                f"{API_BASE}/pipeline/queues/ingest/enqueue",
                data=json.dumps({"items": batch}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
                added = result.get("enqueued", 0)
                self.stats["enqueued"] = self.stats.get("enqueued", 0) + added
                if added:
                    self.log.info(f"Pipeline: enqueued {added} to ingest queue")
        except Exception as e:
            self.log.warning(f"Pipeline enqueue failed (non-fatal): {e}")

    def save_item(self, item_id, data):
        """Save item to disk and enqueue to pipeline."""
        filepath = self.base_dir / f"{item_id}.json"
        if filepath.exists():
            return False
        data["_scraped_at"] = datetime.now(timezone.utc).isoformat()
        data["_source"] = self.source_name
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        self.stats["fetched"] += 1

        self._enqueue_to_pipeline(data)
        return True

    def save_stats(self):
        self.stats["last_run"] = datetime.now(timezone.utc).isoformat()
        stats_file = self.base_dir / "_stats.json"
        with open(stats_file, "w") as f:
            json.dump(self.stats, f, indent=2)

    def scrape(self):
        raise NotImplementedError

    def run(self):
        self.log.info(f"Starting {self.source_name} scraper (single-pass)")
        try:
            count = self.scrape()
            self._flush_enqueue()
            self.log.info(
                f"Scraped {count} new items (total: {self.stats['fetched']}, "
                f"enqueued: {self.stats.get('enqueued', 0)})"
            )
        except Exception as e:
            self.log.error(f"Scrape cycle failed: {e}")
            self.stats["errors"] += 1
        self._flush_enqueue()
        self.save_stats()
        self.log.info("Scraper complete")
