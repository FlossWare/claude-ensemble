#!/usr/bin/env python3
"""
DEV.TO SCRAPER
Scrapes developer articles from dev.to
Uses free public API (no auth needed!)
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-devto'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Popular tags
TAGS = [
    'python', 'javascript', 'react', 'webdev', 'tutorial',
    'beginners', 'programming', 'devops', 'ai', 'machinelearning',
    'docker', 'kubernetes', 'aws', 'security', 'database'
]

class DevToScraper:
    def __init__(self):
        self.base_url = 'https://dev.to/api'

    def get_articles(self, tag=None, per_page=30):
        """Get articles by tag or latest"""
        url = f'{self.base_url}/articles'

        params = {
            'per_page': per_page,
            'state': 'fresh'
        }

        if tag:
            params['tag'] = tag

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return []

    def get_article_content(self, article_id):
        """Get full article content"""
        url = f'{self.base_url}/articles/{article_id}'

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except:
            return None

    def scrape(self, max_tags=10, articles_per_tag=30):
        """Scrape dev.to articles"""
        print("="*70)
        print("DEV.TO SCRAPER - DEVELOPER TUTORIALS")
        print("="*70)
        print(f"Tags: {min(len(TAGS), max_tags)}")
        print(f"Articles per tag: {articles_per_tag}")
        print("FREE API")
        print("="*70)

        examples = []
        seen_ids = set()

        for i, tag in enumerate(TAGS[:max_tags], 1):
            print(f"\n[{i}/{min(len(TAGS), max_tags)}] Tag: {tag}")

            articles = self.get_articles(tag, articles_per_tag)
            print(f"  ✅ Found {len(articles)} articles")

            for article in articles[:10]:  # Top 10 per tag
                if article['id'] in seen_ids:
                    continue
                seen_ids.add(article['id'])

                # Get full content
                full_article = self.get_article_content(article['id'])
                if not full_article or not full_article.get('body_markdown'):
                    continue

                example = {
                    'input': article['title'],
                    'output': full_article['body_markdown'][:3000],  # First 3000 chars
                    'source': 'devto',
                    'category': 'tutorial',
                    'tags': article.get('tag_list', []),
                    'reading_time_minutes': article.get('reading_time_minutes', 0)
                }
                examples.append(example)

                time.sleep(0.5)  # Rate limiting

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'devto_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n{'='*70}")
            print(f"✅ COMPLETE! Scraped {len(examples)} articles")
            print(f"💾 Saved to {data_file.name}")
            print(f"{'='*70}")

        return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-tags', type=int, default=10, help='Max tags')
    parser.add_argument('--articles-per-tag', type=int, default=30, help='Articles per tag')

    args = parser.parse_args()

    scraper = DevToScraper()
    scraper.scrape(args.max_tags, args.articles_per_tag)

if __name__ == '__main__':
    main()
