#!/usr/bin/env python3
"""
Rosetta Code Scraper for LLM Training
Extracts 1000+ programming tasks with solutions in 50+ languages from rosettacode.org
"""

import os
import json
import requests
import time
import re
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Any

OUTPUT_DIR = '/mnt/nas/web-scrape/categories/computer_science'
API_BASE = 'https://rosettacode.org/mw/api.php'

class RosettaCodeScraper:
    """Scrape programming tasks and solutions from Rosetta Code wiki"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Educational-LLM-Training-Bot/1.0 (Contact: responsible-researcher)'
        })
        self.stats = {
            'tasks_scraped': 0,
            'solutions_extracted': 0,
            'languages_seen': set(),
            'api_calls': 0,
            'errors': 0
        }

    def log(self, msg: str, force: bool = False):
        """Print log message if verbose or forced"""
        if self.verbose or force:
            print(msg)

    def api_request(self, params: Dict[str, Any], retry_count: int = 3) -> Optional[Dict]:
        """
        Make MediaWiki API request with rate limiting and exponential backoff

        Args:
            params: API query parameters
            retry_count: Number of retries on failure

        Returns:
            JSON response or None on failure
        """
        base_delay = 1.0

        for attempt in range(retry_count):
            try:
                time.sleep(base_delay)
                response = self.session.get(API_BASE, params=params, timeout=30)
                self.stats['api_calls'] += 1

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    wait_time = base_delay * (2 ** attempt)
                    self.log(f"⚠ Rate limited, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    self.log(f"⚠ API error {response.status_code}")

            except requests.exceptions.Timeout:
                self.log(f"⚠ Timeout on attempt {attempt + 1}/{retry_count}")
                time.sleep(base_delay * (2 ** attempt))
            except Exception as e:
                self.log(f"⚠ Request error: {e}")
                self.stats['errors'] += 1
                time.sleep(base_delay * (2 ** attempt))

        return None

    def get_task_list(self, category: str = 'Programming_Tasks', limit: Optional[int] = None) -> List[str]:
        """
        Get list of task page titles from category

        Args:
            category: Wiki category name
            limit: Maximum tasks to fetch (None = all)

        Returns:
            List of task page titles
        """
        self.log(f"📋 Fetching task list from category: {category}", force=True)

        tasks = []
        continue_token = None

        while True:
            params = {
                'action': 'query',
                'list': 'categorymembers',
                'cmtitle': f'Category:{category}',
                'cmlimit': 500,
                'format': 'json'
            }

            if continue_token:
                params['cmcontinue'] = continue_token

            data = self.api_request(params)
            if not data:
                break

            members = data.get('query', {}).get('categorymembers', [])
            tasks.extend([m['title'] for m in members])

            self.log(f"  Found {len(tasks)} tasks so far...")

            if limit and len(tasks) >= limit:
                tasks = tasks[:limit]
                break

            continue_token = data.get('continue', {}).get('cmcontinue')
            if not continue_token:
                break

        self.log(f"✓ Found {len(tasks)} total tasks", force=True)
        return tasks

    def get_page_content(self, title: str) -> Optional[str]:
        """
        Get wiki markup content for a page

        Args:
            title: Page title

        Returns:
            Wiki markup text or None
        """
        params = {
            'action': 'query',
            'titles': title,
            'prop': 'revisions',
            'rvprop': 'content',
            'format': 'json'
        }

        data = self.api_request(params)
        if not data:
            return None

        pages = data.get('query', {}).get('pages', {})
        page = next(iter(pages.values()), {})
        revisions = page.get('revisions', [])

        if revisions:
            return revisions[0].get('*', '')
        return None

    def parse_wiki_markup(self, content: str) -> Dict[str, Any]:
        """
        Parse wiki markup to extract task description and language solutions

        Args:
            content: Raw wiki markup

        Returns:
            Dict with 'description' and 'solutions' list
        """
        lines = content.split('\n')
        description_lines = []
        solutions = []
        current_lang = None
        current_code = []
        in_code_block = False

        for line in lines:
            # Detect language headers (e.g., ==Python==, ===Java===)
            lang_match = re.match(r'^=+\s*([^=]+?)\s*=+$', line)
            if lang_match:
                # Save previous solution
                if current_lang and current_code:
                    code_text = '\n'.join(current_code).strip()
                    if code_text:
                        solutions.append({
                            'language': current_lang,
                            'code': code_text
                        })
                        self.stats['solutions_extracted'] += 1
                        self.stats['languages_seen'].add(current_lang)

                current_lang = lang_match.group(1).strip()
                current_code = []
                in_code_block = False
                continue

            # Collect description (before first language header)
            if not current_lang and not line.startswith('='):
                cleaned = re.sub(r'\[\[.*?\]\]', '', line)
                cleaned = re.sub(r'{{.*?}}', '', cleaned)
                cleaned = cleaned.strip()
                if cleaned:
                    description_lines.append(cleaned)

            # Extract code from various markup formats
            if current_lang:
                if line.strip().startswith('<lang ') or line.strip().startswith('<syntaxhighlight'):
                    in_code_block = True
                    continue
                elif line.strip() in ['</lang>', '</syntaxhighlight>']:
                    in_code_block = False
                    continue
                elif in_code_block:
                    current_code.append(line)
                elif line.strip().startswith('```'):
                    in_code_block = not in_code_block
                    continue
                elif in_code_block:
                    current_code.append(line)

        # Save final solution
        if current_lang and current_code:
            code_text = '\n'.join(current_code).strip()
            if code_text:
                solutions.append({
                    'language': current_lang,
                    'code': code_text
                })
                self.stats['solutions_extracted'] += 1
                self.stats['languages_seen'].add(current_lang)

        description = '\n'.join(description_lines[:20]).strip()

        return {
            'description': description if description else 'No description available',
            'solutions': solutions
        }

    def scrape_task(self, task_title: str) -> List[Dict[str, Any]]:
        """
        Scrape single task and extract all language solutions

        Args:
            task_title: Task page title

        Returns:
            List of JSONL-formatted training examples
        """
        self.log(f"  Scraping: {task_title}")

        content = self.get_page_content(task_title)
        if not content:
            self.log(f"    ⚠ No content for {task_title}")
            return []

        parsed = self.parse_wiki_markup(content)

        if not parsed['solutions']:
            self.log(f"    ⚠ No solutions found in {task_title}")
            return []

        examples = []
        base_url = f"https://rosettacode.org/wiki/{task_title.replace(' ', '_')}"

        for solution in parsed['solutions']:
            text = f"""Task: {task_title}

Description:
{parsed['description']}

Language: {solution['language']}

{solution['code']}"""

            example = {
                'text': text,
                'source': 'rosetta_code',
                'metadata': {
                    'task': task_title,
                    'language': solution['language'],
                    'url': base_url,
                    'scraped_at': datetime.now().isoformat(),
                    'has_description': bool(parsed['description']),
                    'code_length': len(solution['code'])
                }
            }
            examples.append(example)

        self.stats['tasks_scraped'] += 1
        self.log(f"    ✓ Extracted {len(examples)} solutions")
        return examples

    def scrape(self, category: str = 'Programming_Tasks', limit: Optional[int] = None,
               output_file: Optional[str] = None) -> str:
        """
        Main scraping function

        Args:
            category: Wiki category to scrape
            limit: Maximum tasks to scrape
            output_file: Custom output path (optional)

        Returns:
            Path to output JSONL file
        """
        start_time = time.time()

        tasks = self.get_task_list(category, limit)
        if not tasks:
            raise ValueError(f"No tasks found in category: {category}")

        if not output_file:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d')
            output_file = f"{OUTPUT_DIR}/rosetta_code_{timestamp}.jsonl"

        self.log(f"\n🚀 Starting scrape: {len(tasks)} tasks", force=True)
        self.log(f"📁 Output: {output_file}", force=True)

        all_examples = []

        with open(output_file, 'w', encoding='utf-8') as f:
            for i, task in enumerate(tasks, 1):
                self.log(f"\n[{i}/{len(tasks)}] {task}", force=True)

                examples = self.scrape_task(task)
                all_examples.extend(examples)

                for example in examples:
                    f.write(json.dumps(example) + '\n')

                if i % 50 == 0:
                    self.log(f"\n📊 Progress: {i}/{len(tasks)} tasks, "
                            f"{len(all_examples)} examples", force=True)

        elapsed = time.time() - start_time

        self.log(f"\n{'='*60}", force=True)
        self.log(f"✅ SCRAPE COMPLETE", force=True)
        self.log(f"{'='*60}", force=True)
        self.log(f"Tasks scraped:     {self.stats['tasks_scraped']}", force=True)
        self.log(f"Solutions found:   {self.stats['solutions_extracted']}", force=True)
        self.log(f"Languages seen:    {len(self.stats['languages_seen'])}", force=True)
        self.log(f"API calls made:    {self.stats['api_calls']}", force=True)
        self.log(f"Errors:            {self.stats['errors']}", force=True)
        self.log(f"Time elapsed:      {elapsed/60:.1f} minutes", force=True)
        self.log(f"Output file:       {output_file}", force=True)
        self.log(f"File size:         {os.path.getsize(output_file)/1024/1024:.1f} MB", force=True)
        self.log(f"\nTop languages: {', '.join(sorted(self.stats['languages_seen'])[:20])}",
                force=True)
        self.log(f"{'='*60}", force=True)

        return output_file


def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(
        description='Scrape programming tasks from Rosetta Code for LLM training'
    )
    parser.add_argument('--category', default='Programming_Tasks',
                       help='Wiki category to scrape (default: Programming_Tasks)')
    parser.add_argument('--limit', type=int, default=None,
                       help='Maximum tasks to scrape (default: all)')
    parser.add_argument('--output', default=None,
                       help='Custom output file path')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')

    args = parser.parse_args()

    scraper = RosettaCodeScraper(verbose=args.verbose)

    try:
        output_file = scraper.scrape(
            category=args.category,
            limit=args.limit,
            output_file=args.output
        )
        print(f"\n✅ Success! Data saved to: {output_file}")
        return 0

    except KeyboardInterrupt:
        print("\n\n⚠ Scrape interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1


if __name__ == '__main__':
    exit(main())
