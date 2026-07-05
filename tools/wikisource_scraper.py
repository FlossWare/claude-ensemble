#!/usr/bin/env python3
"""
WIKISOURCE SCRAPER
Scrapes primary source documents and historical texts
Uses FREE MediaWiki API
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-wikisource'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Notable texts
TEXTS = [
    'The United States Constitution',
    'The Declaration of Independence',
    'Gettysburg Address',
    'I Have a Dream',
    'The Communist Manifesto',
    'The Art of War',
    'The Prince',
    'On the Origin of Species',
    'The Wealth of Nations',
    'Common Sense',
]

class WikisourceScraper:
    def __init__(self):
        self.base_url = 'https://en.wikisource.org/w/api.php'

    def get_page(self, title):
        """Get Wikisource page content"""
        params = {
            'action': 'query',
            'prop': 'extracts',
            'titles': title,
            'format': 'json',
            'explaintext': True
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            pages = data.get('query', {}).get('pages', {})
            for page_id, page in pages.items():
                if 'extract' in page:
                    return page['extract']

            return None
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return None

    def scrape(self, max_texts=10):
        """Scrape Wikisource texts"""
        print("="*70)
        print("WIKISOURCE SCRAPER - PRIMARY SOURCES")
        print("="*70)
        print(f"Texts: {min(len(TEXTS), max_texts)}")
        print("FREE MediaWiki API")
        print("="*70)

        examples = []

        for i, title in enumerate(TEXTS[:max_texts], 1):
            print(f"\n[{i}/{min(len(TEXTS), max_texts)}] {title}")

            content = self.get_page(title)
            if not content:
                continue

            example = {
                'input': f"What is \"{title}\"?",
                'output': content[:3000],
                'source': 'wikisource',
                'category': 'primary_source',
                'title': title
            }
            examples.append(example)

            print(f"  ✅ Scraped {len(content)} chars")

            time.sleep(2)

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'wikisource_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n{'='*70}")
            print(f"✅ COMPLETE! Scraped {len(examples)} historical texts")
            print(f"💾 Saved to {data_file.name}")
            print(f"{'='*70}")

        return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-texts', type=int, default=10, help='Max texts')

    args = parser.parse_args()

    scraper = WikisourceScraper()
    scraper.scrape(args.max_texts)

if __name__ == '__main__':
    main()
