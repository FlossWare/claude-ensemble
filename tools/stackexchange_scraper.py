#!/usr/bin/env python3
"""
STACK EXCHANGE SCRAPER
Scrapes Q&A from Stack Exchange network (ServerFault, AskUbuntu, etc.)
Uses FREE API (no auth needed for basic usage!)
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-stackexchange'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Stack Exchange sites
SITES = [
    'serverfault', 'askubuntu', 'superuser', 'unix',
    'dba', 'security', 'devops', 'networkengineering',
    'datascience', 'stats', 'math', 'physics',
    'electronics',  # Electronics & EE!
    'robotics',     # Robotics (related to EE)
]

class StackExchangeScraper:
    def __init__(self):
        self.base_url = 'https://api.stackexchange.com/2.3'

    def get_questions(self, site, pagesize=100):
        """Get top questions from a site"""
        url = f'{self.base_url}/questions'

        params = {
            'site': site,
            'pagesize': pagesize,
            'order': 'desc',
            'sort': 'votes',
            'filter': 'withbody'
        }

        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            return data.get('items', [])
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return []

    def scrape(self, max_sites=10, questions_per_site=100):
        """Scrape Stack Exchange sites"""
        print("="*70)
        print("STACK EXCHANGE SCRAPER - 50M+ Q&A")
        print("="*70)
        print(f"Sites: {min(len(SITES), max_sites)}")
        print(f"Questions per site: {questions_per_site}")
        print("FREE API")
        print("="*70)

        examples = []

        for i, site in enumerate(SITES[:max_sites], 1):
            print(f"\n[{i}/{min(len(SITES), max_sites)}] {site}")

            questions = self.get_questions(site, questions_per_site)
            print(f"  ✅ Found {len(questions)} questions")

            for q in questions:
                if not q.get('body'):
                    continue

                example = {
                    'input': q.get('title', ''),
                    'output': q['body'][:2000],
                    'source': 'stackexchange',
                    'category': 'qa',
                    'site': site,
                    'score': q.get('score', 0),
                    'answers': q.get('answer_count', 0)
                }
                examples.append(example)

            time.sleep(2)  # Rate limiting (important for Stack Exchange!)

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'stackexchange_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n{'='*70}")
            print(f"✅ COMPLETE! Scraped {len(examples)} Q&A")
            print(f"💾 Saved to {data_file.name}")
            print(f"{'='*70}")

        return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-sites', type=int, default=10, help='Max sites')
    parser.add_argument('--questions-per-site', type=int, default=100, help='Questions per site')

    args = parser.parse_args()

    scraper = StackExchangeScraper()
    scraper.scrape(args.max_sites, args.questions_per_site)

if __name__ == '__main__':
    main()
