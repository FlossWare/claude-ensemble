#!/usr/bin/env python3
"""
Backfill missing titles for knowledge.documents via REST API.

Extracts titles from document content using category-specific heuristics:
  - arxiv_paper / dblp / huggingface_papers: "Title: ..." at start of content
  - queued: filename from "[Queued for processing: ...]" or metadata.file_path
  - rfc: RFC-specific header patterns
  - source code (os_source_code, ddwrt, raw-modern-langs, null):
    URL path, metadata.file_path, @file/@brief comments, first meaningful line
  - web-scrape (empty content): marks as "[No content]"

All DB access goes through REST API at aio-01:5000 (never direct PostgreSQL).
Runs on laptop-01/laptop-02 only (no fleet workers needed — pure text extraction).

Usage:
  python3 backfill-titles.py                # full run
  python3 backfill-titles.py --dry-run      # preview without writing
  python3 backfill-titles.py --batch 200    # custom batch size
  python3 backfill-titles.py --category rfc # process only one category
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse

import requests

# ============================================================================
# Configuration
# ============================================================================

API_BASE = "http://aio-01:5000"
QUERY_ENDPOINT = f"{API_BASE}/storage/query"
DEFAULT_BATCH = 500
MAX_TITLE_LEN = 300

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================================
# REST API helpers
# ============================================================================


def api_query(sql: str) -> Dict[str, Any]:
    """Execute a query via the REST API."""
    payload: Dict[str, Any] = {"query": sql}
    try:
        resp = requests.post(QUERY_ENDPOINT, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error("API request failed: %s", e)
        raise


# ============================================================================
# Title extraction strategies
# ============================================================================


def extract_title_from_prefix(content: str) -> Optional[str]:
    """Extract title from 'Title: ...' at start of content (arxiv, dblp, hf)."""
    if not content:
        return None
    # Match "Title: ..." up to the first newline or period-newline
    m = re.match(r"Title:\s*(.+?)(?:\n|$)", content, re.DOTALL)
    if m:
        title = m.group(1).strip()
        # Clean up multi-line titles (some span 2+ lines before next field)
        title = re.split(r"\n\s*\n|\nAuthors?:|\nSource:|\nAbstract:", title)[0].strip()
        if title:
            return title[:MAX_TITLE_LEN]
    return None


def extract_title_from_queued(content: str, metadata: Optional[Dict]) -> Optional[str]:
    """Extract title from queued placeholder or metadata."""
    # Try metadata.file_path first (more complete)
    if metadata and isinstance(metadata, dict):
        fpath = metadata.get("file_path", "")
        if fpath:
            # Use last 2 path segments for context
            parts = fpath.rstrip("/").split("/")
            if len(parts) >= 2:
                return f"{parts[-2]}/{parts[-1]}"
            return parts[-1] if parts else None

    # Fall back to content pattern: [Queued for processing: filename]
    if content:
        m = re.match(r"\[Queued for processing:\s*(.+?)\]", content)
        if m:
            return m.group(1).strip()[:MAX_TITLE_LEN]
    return None


def extract_title_from_rfc(content: str) -> Optional[str]:
    """Extract title from RFC document content."""
    if not content:
        return None
    # RFC texts often have a structured header, but our fragments may not
    # have the header. Try common patterns.

    # Pattern: "RFC NNNN - Title" or "RFC NNNN: Title"
    m = re.search(r"RFC\s+(\d+)\s*[-:]\s*(.+?)(?:\n|$)", content[:500])
    if m:
        return f"RFC {m.group(1)} - {m.group(2).strip()}"[:MAX_TITLE_LEN]

    # Pattern: First meaningful sentence (skip blank/short lines)
    lines = content.split("\n")
    for line in lines[:20]:
        line = line.strip()
        if len(line) > 20 and not line.startswith("//") and not line.startswith("/*"):
            return line[:MAX_TITLE_LEN]
    return None


def extract_title_from_url(url: str) -> Optional[str]:
    """Extract a title from a URL path."""
    if not url:
        return None
    parsed = urlparse(url)
    path = unquote(parsed.path).rstrip("/")
    if not path or path == "/":
        return parsed.netloc or None

    parts = path.split("/")
    # Use last path segment, or last two for context
    filename = parts[-1] if parts else None
    if not filename:
        return None

    # For file:// URLs, include parent dir for context
    if parsed.scheme == "file" and len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"

    # For github URLs, try to make it readable
    if "github.com" in (parsed.netloc or ""):
        # e.g., /TheAlgorithms/Python/blob/master/audio_filters/butterworth_filter.py
        # Return meaningful tail
        meaningful = [p for p in parts if p not in ("blob", "master", "main", "tree")]
        if len(meaningful) >= 2:
            return "/".join(meaningful[-2:])

    return filename[:MAX_TITLE_LEN]


def extract_title_from_source_code(content: str) -> Optional[str]:
    """Extract title from source code via comments, @file, first line."""
    if not content:
        return None

    # @file annotation (common in C/C++/Java)
    m = re.search(r"@file\s+(.+?)(?:\n|$)", content[:2000])
    if m:
        return m.group(1).strip()[:MAX_TITLE_LEN]

    # @brief annotation
    m = re.search(r"@brief\s+(.+?)(?:\n|$)", content[:2000])
    if m:
        return m.group(1).strip()[:MAX_TITLE_LEN]

    # C-style block comment first line: /* filename.c or description */
    m = re.match(r"/\*+\s*\n?\s*\*?\s*(.+?)(?:\n|\*/)", content[:1000])
    if m:
        line = m.group(1).strip().rstrip("*").strip()
        if len(line) > 5:
            return line[:MAX_TITLE_LEN]

    # Shell/Python/Ruby comment header: # filename or # Description
    m = re.match(r"#[!=]?[-=]*\s*\n?\s*#\s*(.+?)(?:\n|$)", content[:1000])
    if m:
        line = m.group(1).strip()
        if len(line) > 5 and not line.startswith("!"):
            return line[:MAX_TITLE_LEN]

    # CMake comment header: #===--- CMakeLists.txt - Description ---===
    m = re.match(r"#===[-=]*\s*(.+?)\s*[-=]*===", content[:500])
    if m:
        return m.group(1).strip()[:MAX_TITLE_LEN]

    # Markdown heading: # Title
    m = re.match(r"#\s+(.+?)(?:\n|$)", content[:500])
    if m:
        return m.group(1).strip()[:MAX_TITLE_LEN]

    # First meaningful non-empty line (at least 10 chars, not just symbols)
    for line in content.split("\n")[:15]:
        line = line.strip()
        # Skip empty, pure symbols, very short lines
        if len(line) >= 10 and re.search(r"[a-zA-Z]{3,}", line):
            # Trim common comment prefixes
            line = re.sub(r"^(/\*+|\*+/|//+|#+|--+)\s*", "", line).strip()
            if len(line) >= 10:
                return line[:MAX_TITLE_LEN]

    return None


def extract_title(doc: Dict) -> Optional[str]:
    """
    Extract a title from a document using category-aware strategies.

    Returns the extracted title or None if nothing useful can be extracted.
    """
    doc_id = doc.get("id")
    category = doc.get("category")
    content = doc.get("content") or ""
    url = doc.get("url")
    metadata = doc.get("metadata")

    # Parse metadata if it's a string
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = None

    # Strategy 1: Content starts with "Title: ..." (papers)
    if category in ("arxiv_paper", "dblp", "huggingface_papers"):
        title = extract_title_from_prefix(content)
        if title:
            return title

    # Strategy 2: Queued placeholder
    if category == "queued":
        title = extract_title_from_queued(content, metadata)
        if title:
            return title

    # Strategy 3: RFC documents
    if category == "rfc":
        title = extract_title_from_rfc(content)
        if title:
            return title

    # Strategy 4: URL-based title (for docs with URLs)
    if url:
        title = extract_title_from_url(url)
        if title:
            return title

    # Strategy 5: Metadata file_path
    if metadata and isinstance(metadata, dict):
        fpath = metadata.get("file_path", "")
        if fpath:
            parts = fpath.rstrip("/").split("/")
            if len(parts) >= 2:
                return f"{parts[-2]}/{parts[-1]}"[:MAX_TITLE_LEN]
            if parts:
                return parts[-1][:MAX_TITLE_LEN]

    # Strategy 6: Content-based extraction (source code, text)
    if content and len(content.strip()) > 10:
        # Try "Title: ..." even for unknown categories
        title = extract_title_from_prefix(content)
        if title:
            return title

        title = extract_title_from_source_code(content)
        if title:
            return title

    # Strategy 7: Empty content marker
    if not content or len(content.strip()) < 5:
        return "[No content available]"

    # Last resort: first 80 chars of content
    first_line = content.strip().split("\n")[0].strip()
    if first_line and len(first_line) > 5:
        return first_line[:MAX_TITLE_LEN]

    return None


# ============================================================================
# Batch processing
# ============================================================================


def fetch_batch(last_id: int, batch_size: int,
                category_filter: Optional[str] = None) -> List[Dict]:
    """
    Fetch a batch of documents missing titles using cursor-based pagination.

    Uses WHERE id > last_id instead of OFFSET to avoid skipping rows as
    updated documents drop out of the result set.
    """
    where = f"WHERE (d.title IS NULL OR d.title = '') AND d.id > {last_id}"
    if category_filter:
        # Escape single quotes in category
        safe_cat = category_filter.replace("'", "''")
        if category_filter == "NULL":
            where += " AND d.category IS NULL"
        else:
            where += f" AND d.category = '{safe_cat}'"

    sql = f"""
        SELECT d.id, d.category, d.url,
               LEFT(d.content, 3000) AS content,
               d.metadata
        FROM knowledge.documents d
        {where}
        ORDER BY d.id
        LIMIT {batch_size}
    """
    result = api_query(sql)
    if not result.get("success"):
        logger.error("Query failed: %s", result)
        return []

    rows = result.get("results", [])
    docs = []
    for row in rows:
        docs.append({
            "id": row[0],
            "category": row[1],
            "url": row[2],
            "content": row[3],
            "metadata": row[4],
        })
    return docs


def sql_escape(s: str) -> str:
    """
    Escape a string for inclusion in a SQL literal.

    Uses PostgreSQL dollar-quoting when the string contains problematic
    characters, falling back to standard single-quote escaping otherwise.
    """
    # Remove null bytes (PostgreSQL rejects them)
    s = s.replace("\x00", "")
    # Remove control characters except newline and tab
    s = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", s)
    # Standard SQL escaping: double single quotes
    return s.replace("'", "''")


def update_titles(updates: List[Tuple[int, str]]) -> int:
    """
    Batch-update titles via REST API. Returns number of rows updated.

    Splits into sub-batches of 100 to avoid overly large SQL statements.
    """
    if not updates:
        return 0

    total_rows = 0
    sub_batch_size = 100

    for i in range(0, len(updates), sub_batch_size):
        sub_batch = updates[i:i + sub_batch_size]

        # Build UPDATE using a VALUES list for efficiency
        values_parts = []
        for doc_id, title in sub_batch:
            safe_title = sql_escape(title)
            values_parts.append(f"({doc_id}, '{safe_title}')")

        values_str = ", ".join(values_parts)
        sql = f"""
            UPDATE knowledge.documents AS d
            SET title = v.title
            FROM (VALUES {values_str}) AS v(id, title)
            WHERE d.id = v.id
        """
        result = api_query(sql)
        if not result.get("success"):
            logger.error("Update failed for sub-batch %d-%d: %s",
                         i, i + len(sub_batch), result)
        else:
            total_rows += result.get("rowcount", 0)

    return total_rows


def get_total_count(category_filter: Optional[str] = None) -> int:
    """Get total count of documents missing titles."""
    where = "WHERE (title IS NULL OR title = '')"
    if category_filter:
        safe_cat = category_filter.replace("'", "''")
        if category_filter == "NULL":
            where += " AND category IS NULL"
        else:
            where += f" AND category = '{safe_cat}'"

    sql = f"SELECT COUNT(*) FROM knowledge.documents {where}"
    result = api_query(sql)
    if result.get("success") and result.get("results"):
        return result["results"][0][0]
    return 0


# ============================================================================
# Main
# ============================================================================


def main():
    parser = argparse.ArgumentParser(description="Backfill missing document titles")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview extractions without writing to DB")
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH,
                        help=f"Batch size (default: {DEFAULT_BATCH})")
    parser.add_argument("--category", type=str, default=None,
                        help="Process only this category (use NULL for null category)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max documents to process (0 = all)")
    parser.add_argument("--verbose", action="store_true",
                        help="Show each extracted title")
    args = parser.parse_args()

    total = get_total_count(args.category)
    logger.info("Documents missing titles: %d (category=%s)", total,
                args.category or "all")

    if total == 0:
        logger.info("Nothing to do.")
        return

    last_id = 0  # Cursor: fetch docs with id > last_id
    total_updated = 0
    total_skipped = 0
    total_extracted = 0
    batch_num = 0
    category_stats: Dict[str, int] = {}
    start_time = time.time()

    while True:
        if args.limit and total_extracted >= args.limit:
            logger.info("Reached limit of %d documents", args.limit)
            break

        batch = fetch_batch(last_id, args.batch, args.category)
        if not batch:
            break

        batch_num += 1
        updates: List[Tuple[int, str]] = []

        for doc in batch:
            # Advance cursor to highest id seen
            last_id = max(last_id, doc["id"])

            title = extract_title(doc)
            cat = doc["category"] or "NULL"

            if title:
                total_extracted += 1
                category_stats[cat] = category_stats.get(cat, 0) + 1

                if args.verbose:
                    logger.info("  [%d] (%s) -> %s", doc["id"], cat,
                                title[:80])

                if not args.dry_run:
                    updates.append((doc["id"], title))

                if args.limit and total_extracted >= args.limit:
                    break
            else:
                total_skipped += 1
                if args.verbose:
                    preview = (doc.get("content") or "")[:60]
                    logger.warning("  [%d] (%s) SKIP: %s", doc["id"], cat,
                                   preview)

        # Write batch
        if updates:
            rows = update_titles(updates)
            total_updated += rows
            logger.info("Batch %d (cursor>%d): extracted=%d, updated=%d, skipped=%d",
                        batch_num, last_id, len(updates), rows,
                        len(batch) - len(updates))

        # Progress
        elapsed = time.time() - start_time
        rate = total_extracted / elapsed if elapsed > 0 else 0
        logger.info("Progress: %d/%d extracted (%.0f docs/sec), %d updated, %d skipped",
                    total_extracted, total, rate, total_updated, total_skipped)

    # Summary
    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info("COMPLETE in %.1f seconds", elapsed)
    logger.info("  Total processed:  %d", total_extracted + total_skipped)
    logger.info("  Titles extracted:  %d", total_extracted)
    logger.info("  Titles written:    %d", total_updated)
    logger.info("  Skipped:           %d", total_skipped)
    logger.info("  By category:")
    for cat, count in sorted(category_stats.items(), key=lambda x: -x[1]):
        logger.info("    %-25s %d", cat, count)

    if args.dry_run:
        logger.info("  ** DRY RUN — no changes written **")


if __name__ == "__main__":
    main()
