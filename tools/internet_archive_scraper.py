#!/usr/bin/env python3
"""
INTERNET ARCHIVE SCRAPER
Scrapes books and texts from Internet Archive
Uses FREE API
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Search topics
TOPICS = [
    'computer science', 'programming', 'mathematics',
    'physics', 'engineering', 'history', 'philosophy',
]

class InternetArchiveScraper:
    def __init__(self):
        self.base_url = 'https://archive.org'

    def search_texts(self, query, rows=50):
        """Search Internet Archive"""
        url = f'{self.base_url}/advancedsearch.php'

        params = {
            'q': query,
            'fl[]': ['identifier', 'title', 'description'],
            'rows': rows,
            'page': 1,
            'output': 'json',
            'mediatype': 'texts'
        }

        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            return data.get('response', {}).get('docs', [])
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return []

    def scrape(self, max_topics=7, items_per_topic=50):
        """Scrape Internet Archive"""
        print("="*70)
        print("INTERNET ARCHIVE SCRAPER - BOOKS & TEXTS")
        print("="*70)
        print(f"Topics: {min(len(TOPICS), max_topics)}")
        print(f"Items per topic: {items_per_topic}")
        print("="*70)

        examples = []

        for i, topic in enumerate(TOPICS[:max_topics], 1):
            print(f"\n[{i}/{min(len(TOPICS), max_topics)}] {topic}")

            items = self.search_texts(topic, items_per_topic)
            print(f"  ✅ Found {len(items)} items")

            for item in items:
                desc = item.get('description', '')
                if isinstance(desc, list):
                    desc = ' '.join(desc)

                if not desc or len(desc) < 50:
                    continue

                example = {
                    'input': item.get('title', ''),
                    'output': desc[:2000],
                    'source': 'internet_archive',
                    'category': 'historical_text',
                    'identifier': item.get('identifier', '')
                }
                examples.append(example)

            time.sleep(2)

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'internet_archive_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n{'='*70}")
            print(f"✅ COMPLETE! Scraped {len(examples)} texts")
            print(f"💾 Saved to {data_file.name}")
            print(f"{'='*70}")

        return len(examples)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-topics', type=int, default=7)
    parser.add_argument('--items-per-topic', type=int, default=50)
    args = parser.parse_args()

    scraper = InternetArchiveScraper()
    scraper.scrape(args.max_topics, args.items_per_topic)

if __name__ == '__main__':
    main()
