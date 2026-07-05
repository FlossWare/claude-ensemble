#!/usr/bin/env python3
"""
LeetCode Problem Scraper
Scrapes LeetCode problems via their public GraphQL API and saves to JSONL.

Usage:
    python3 leetcode_scraper.py --category computer_science
    python3 leetcode_scraper.py --category algorithms --limit 100
"""

import argparse
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Constants
LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"
BASE_URL = "https://leetcode.com"
OUTPUT_BASE = "/mnt/nas/web-scrape/categories"
DEFAULT_CATEGORY = "computer_science"
RATE_LIMIT_DELAY = 1.0  # seconds between requests
MAX_RETRIES = 3
TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# GraphQL Queries
PROBLEMSET_QUERY = """
query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
  problemsetQuestionList: questionList(
    categorySlug: $categorySlug
    limit: $limit
    skip: $skip
    filters: $filters
  ) {
    total: totalNum
    questions: data {
      questionId
      questionFrontendId
      title
      titleSlug
      difficulty
      isPaidOnly
      topicTags {
        name
        slug
      }
      stats
      acRate
    }
  }
}
"""

PROBLEM_DETAIL_QUERY = """
query questionData($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionId
    questionFrontendId
    title
    titleSlug
    content
    difficulty
    likes
    dislikes
    similarQuestions
    exampleTestcases
    topicTags {
      name
      slug
    }
    codeSnippets {
      lang
      langSlug
      code
    }
    stats
    hints
    solution {
      id
      canSeeDetail
    }
  }
}
"""


class LeetCodeScraper:
    """LeetCode problem scraper using GraphQL API."""

    def __init__(self, category: str, output_dir: Optional[str] = None):
        """
        Initialize scraper.

        Args:
            category: Category name for output directory
            output_dir: Optional custom output directory (defaults to OUTPUT_BASE/category)
        """
        self.category = category
        self.output_dir = Path(output_dir) if output_dir else Path(OUTPUT_BASE) / category
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Setup logging
        self.logger = self._setup_logging()

        # Setup session with retries
        self.session = self._create_session()

        # Stats
        self.stats = {
            "total_problems": 0,
            "scraped": 0,
            "skipped_paid": 0,
            "errors": 0,
            "start_time": datetime.now().isoformat(),
        }

    def _setup_logging(self) -> logging.Logger:
        """Configure logging to file and console."""
        logger = logging.getLogger("leetcode_scraper")
        logger.setLevel(logging.INFO)

        # File handler
        log_file = self.output_dir / f"scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)

        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        logger.addHandler(fh)
        logger.addHandler(ch)

        return logger

    def _create_session(self) -> requests.Session:
        """Create requests session with retry logic."""
        session = requests.Session()

        # Retry strategy
        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Headers
        session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json",
                "Referer": BASE_URL,
            }
        )

        return session

    def _graphql_request(
        self, query: str, variables: Dict[str, Any], retry_count: int = 0
    ) -> Optional[Dict]:
        """
        Execute GraphQL query with rate limiting and error handling.

        Args:
            query: GraphQL query string
            variables: Query variables
            retry_count: Current retry attempt

        Returns:
            Response data or None on failure
        """
        payload = {"query": query, "variables": variables}

        try:
            time.sleep(RATE_LIMIT_DELAY)  # Rate limiting
            response = self.session.post(
                LEETCODE_GRAPHQL_URL, json=payload, timeout=TIMEOUT
            )
            response.raise_for_status()

            data = response.json()

            if "errors" in data:
                self.logger.error(f"GraphQL errors: {data['errors']}")
                return None

            return data.get("data")

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # Rate limited
                wait_time = (2 ** retry_count) * RATE_LIMIT_DELAY
                self.logger.warning(
                    f"Rate limited. Waiting {wait_time}s before retry {retry_count + 1}/{MAX_RETRIES}"
                )
                time.sleep(wait_time)

                if retry_count < MAX_RETRIES:
                    return self._graphql_request(query, variables, retry_count + 1)
                else:
                    self.logger.error(f"Max retries exceeded for query: {variables}")
                    return None
            else:
                self.logger.error(f"HTTP error: {e}")
                return None

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            if retry_count < MAX_RETRIES:
                time.sleep((2 ** retry_count) * RATE_LIMIT_DELAY)
                return self._graphql_request(query, variables, retry_count + 1)
            return None

        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            return None

    def get_problem_list(self, limit: int = 50, skip: int = 0) -> Optional[Dict]:
        """
        Fetch problem list.

        Args:
            limit: Number of problems per page
            skip: Offset for pagination

        Returns:
            Problem list data or None
        """
        variables = {
            "categorySlug": "",
            "limit": limit,
            "skip": skip,
            "filters": {},
        }

        self.logger.debug(f"Fetching problem list (limit={limit}, skip={skip})")
        return self._graphql_request(PROBLEMSET_QUERY, variables)

    def get_problem_detail(self, title_slug: str) -> Optional[Dict]:
        """
        Fetch detailed problem information.

        Args:
            title_slug: Problem slug (URL-friendly title)

        Returns:
            Problem detail data or None
        """
        variables = {"titleSlug": title_slug}

        self.logger.debug(f"Fetching problem detail: {title_slug}")
        return self._graphql_request(PROBLEM_DETAIL_QUERY, variables)

    def parse_stats(self, stats_json: str) -> Dict[str, Any]:
        """Parse JSON-encoded stats string."""
        try:
            return json.loads(stats_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def format_problem(self, basic_info: Dict, detail: Dict) -> Dict[str, Any]:
        """
        Format problem data into JSONL schema.

        Args:
            basic_info: Basic problem info from list query
            detail: Detailed problem info

        Returns:
            Formatted problem dict
        """
        question = detail.get("question", {})
        stats = self.parse_stats(question.get("stats", "{}"))

        # Build problem text
        text_parts = [
            f"# {question.get('title', 'Unknown')}",
            f"Difficulty: {question.get('difficulty', 'Unknown')}",
            f"Problem ID: {question.get('questionFrontendId', 'N/A')}",
            "",
            "## Problem Description",
            question.get("content", "No description available"),
        ]

        # Add hints if available
        hints = question.get("hints", [])
        if hints:
            text_parts.extend(["", "## Hints"])
            text_parts.extend(f"{i+1}. {hint}" for i, hint in enumerate(hints))

        # Add example test cases
        example_tests = question.get("exampleTestcases", "")
        if example_tests:
            text_parts.extend(["", "## Example Test Cases", example_tests])

        # Add code snippets
        code_snippets = question.get("codeSnippets", [])
        if code_snippets:
            text_parts.extend(["", "## Code Templates"])
            for snippet in code_snippets[:3]:  # Limit to top 3 languages
                lang = snippet.get("lang", "Unknown")
                code = snippet.get("code", "")
                text_parts.extend([f"### {lang}", f"```{snippet.get('langSlug', '')}", code, "```"])

        text = "\n".join(text_parts)

        # Build metadata
        metadata = {
            "problem_id": question.get("questionId"),
            "frontend_id": question.get("questionFrontendId"),
            "title": question.get("title"),
            "title_slug": question.get("titleSlug"),
            "difficulty": question.get("difficulty"),
            "url": f"{BASE_URL}/problems/{question.get('titleSlug', '')}",
            "topics": [tag.get("name") for tag in question.get("topicTags", [])],
            "topic_slugs": [tag.get("slug") for tag in question.get("topicTags", [])],
            "likes": question.get("likes", 0),
            "dislikes": question.get("dislikes", 0),
            "acceptance_rate": basic_info.get("acRate", 0),
            "total_accepted": stats.get("totalAcceptedRaw", 0),
            "total_submission": stats.get("totalSubmissionRaw", 0),
            "similar_questions": question.get("similarQuestions", "[]"),
            "has_solution": question.get("solution", {}).get("canSeeDetail", False),
            "scraped_at": datetime.now().isoformat(),
        }

        return {
            "text": text,
            "source": "leetcode",
            "metadata": metadata,
        }

    def save_problem(self, problem_data: Dict[str, Any]):
        """
        Save problem to JSONL file.

        Args:
            problem_data: Formatted problem data
        """
        # One file per problem for easier incremental updates
        problem_id = problem_data["metadata"]["frontend_id"]
        title_slug = problem_data["metadata"]["title_slug"]
        filename = f"{problem_id}_{title_slug}.jsonl"
        filepath = self.output_dir / filename

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(json.dumps(problem_data, ensure_ascii=False) + "\n")

            self.logger.debug(f"Saved problem {problem_id}: {filepath}")

        except Exception as e:
            self.logger.error(f"Failed to save problem {problem_id}: {e}")
            raise

    def scrape_all(self, limit: Optional[int] = None):
        """
        Scrape all available problems.

        Args:
            limit: Optional limit on number of problems to scrape
        """
        self.logger.info("Starting LeetCode scraper")
        self.logger.info(f"Output directory: {self.output_dir}")

        # Get total count first
        initial_data = self.get_problem_list(limit=1, skip=0)
        if not initial_data or "problemsetQuestionList" not in initial_data:
            self.logger.error("Failed to fetch initial problem list")
            return

        total_available = initial_data["problemsetQuestionList"]["total"]
        self.stats["total_problems"] = min(total_available, limit) if limit else total_available

        self.logger.info(f"Total problems available: {total_available}")
        self.logger.info(f"Will scrape: {self.stats['total_problems']}")

        # Paginate through all problems
        page_size = 50
        skip = 0
        scraped_count = 0

        while scraped_count < self.stats["total_problems"]:
            # Fetch page
            data = self.get_problem_list(limit=page_size, skip=skip)
            if not data or "problemsetQuestionList" not in data:
                self.logger.error(f"Failed to fetch page at skip={skip}")
                break

            questions = data["problemsetQuestionList"]["questions"]
            if not questions:
                break

            # Process each problem
            for question in questions:
                if limit and scraped_count >= limit:
                    break

                # Skip paid-only problems
                if question.get("isPaidOnly", False):
                    self.logger.info(
                        f"Skipping paid-only problem: {question.get('questionFrontendId')} - {question.get('title')}"
                    )
                    self.stats["skipped_paid"] += 1
                    continue

                # Fetch detailed problem data
                title_slug = question.get("titleSlug")
                if not title_slug:
                    self.logger.warning(f"Missing titleSlug for problem: {question}")
                    continue

                detail_data = self.get_problem_detail(title_slug)
                if not detail_data:
                    self.logger.error(f"Failed to fetch detail for {title_slug}")
                    self.stats["errors"] += 1
                    continue

                try:
                    # Format and save
                    problem_data = self.format_problem(question, detail_data)
                    self.save_problem(problem_data)

                    scraped_count += 1
                    self.stats["scraped"] = scraped_count

                    self.logger.info(
                        f"[{scraped_count}/{self.stats['total_problems']}] "
                        f"Scraped: {question.get('questionFrontendId')} - {question.get('title')}"
                    )

                except Exception as e:
                    self.logger.error(
                        f"Error processing problem {title_slug}: {e}", exc_info=True
                    )
                    self.stats["errors"] += 1

            skip += page_size

            # Progress update
            self.logger.info(
                f"Progress: {scraped_count}/{self.stats['total_problems']} scraped, "
                f"{self.stats['skipped_paid']} skipped (paid), "
                f"{self.stats['errors']} errors"
            )

        # Final stats
        self.stats["end_time"] = datetime.now().isoformat()
        self._save_stats()

        self.logger.info("=" * 80)
        self.logger.info("Scraping complete!")
        self.logger.info(f"Total scraped: {self.stats['scraped']}")
        self.logger.info(f"Skipped (paid-only): {self.stats['skipped_paid']}")
        self.logger.info(f"Errors: {self.stats['errors']}")
        self.logger.info(f"Output directory: {self.output_dir}")
        self.logger.info("=" * 80)

    def _save_stats(self):
        """Save scraping statistics to JSON file."""
        stats_file = self.output_dir / "scraper_stats.json"
        try:
            with open(stats_file, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, indent=2)
            self.logger.info(f"Stats saved to: {stats_file}")
        except Exception as e:
            self.logger.error(f"Failed to save stats: {e}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Scrape LeetCode problems to JSONL format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape all free problems to computer_science category
  python3 leetcode_scraper.py --category computer_science

  # Scrape first 100 problems
  python3 leetcode_scraper.py --category algorithms --limit 100

  # Custom output directory
  python3 leetcode_scraper.py --category cs --output /tmp/leetcode
        """,
    )

    parser.add_argument(
        "--category",
        default=DEFAULT_CATEGORY,
        help=f"Category name for output directory (default: {DEFAULT_CATEGORY})",
    )

    parser.add_argument(
        "--output",
        help=f"Custom output directory (default: {OUTPUT_BASE}/{{category}})",
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of problems to scrape (default: all free problems)",
    )

    args = parser.parse_args()

    # Create and run scraper
    scraper = LeetCodeScraper(category=args.category, output_dir=args.output)
    scraper.scrape_all(limit=args.limit)


if __name__ == "__main__":
    main()
