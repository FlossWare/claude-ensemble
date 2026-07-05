#!/usr/bin/env python3
"""
NEWSAPI SCRAPER
Scrapes current news from NewsAPI
Uses free tier (100 requests/day)
Requires API key: https://newsapi.org/
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime
import os

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-news'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# News categories
CATEGORIES = [
    'technology', 'science', 'business', 'health'
]

class NewsAPIScraper:
    def __init__(self):
        # Check for API key
        self.api_key = os.getenv('NEWSAPI_KEY')

        if not self.api_key:
            print("⚠️  WARNING: No NEWSAPI_KEY found in environment")
            print("   Get free key at: https://newsapi.org/")
            print("   Will generate placeholder data instead")
            self.api_key = None

    def get_top_headlines(self, category, page_size=25):
        """Get top headlines for a category"""
        if not self.api_key:
            return []

        url = 'https://newsapi.org/v2/top-headlines'

        params = {
            'apiKey': self.api_key,
            'category': category,
            'language': 'en',
            'pageSize': page_size
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data['status'] != 'ok':
                print(f"  ❌ API error: {data.get('message', 'Unknown')}")
                return []

            return data.get('articles', [])

        except Exception as e:
            print(f"  ❌ Error: {e}")
            return []

    def scrape(self, max_categories=4, articles_per_category=25):
        """Scrape news articles"""
        print("="*70)
        print("NEWSAPI SCRAPER - CURRENT NEWS")
        print("="*70)

        if not self.api_key:
            print("NO API KEY - Skipping NewsAPI")
            print("Set NEWSAPI_KEY environment variable to enable")
            print("="*70)
            return 0

        print(f"Categories: {min(len(CATEGORIES), max_categories)}")
        print(f"Articles per category: {articles_per_category}")
        print(f"FREE tier: 100 requests/day")
        print("="*70)

        examples = []

        for i, category in enumerate(CATEGORIES[:max_categories], 1):
            print(f"\n[{i}/{min(len(CATEGORIES), max_categories)}] Category: {category}")

            articles = self.get_top_headlines(category, articles_per_category)
            print(f"  ✅ Found {len(articles)} articles")

            for article in articles:
                if not article.get('description'):
                    continue

                example = {
                    'input': article['title'],
                    'output': article['description'] + '\n\n' + (article.get('content', '') or '')[:1000],
                    'source': 'newsapi',
                    'category': f'news_{category}',
                    'published_at': article.get('publishedAt', ''),
                    'source_name': article.get('source', {}).get('name', '')
                }
                examples.append(example)

            time.sleep(1)  # Rate limiting

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'news_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n{'='*70}")
            print(f"✅ COMPLETE! Scraped {len(examples)} news articles")
            print(f"💾 Saved to {data_file.name}")
            print(f"{'='*70}")

        return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-categories', type=int, default=4, help='Max categories')
    parser.add_argument('--articles-per-category', type=int, default=25, help='Articles per category')

    args = parser.parse_args()

    scraper = NewsAPIScraper()
    scraper.scrape(args.max_categories, args.articles_per_category)

if __name__ == '__main__':
    main()
