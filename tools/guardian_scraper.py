#!/usr/bin/env python3
"""
THE GUARDIAN SCRAPER
Scrapes quality journalism from The Guardian
Uses FREE API tier (12,000 requests/day)
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime
import os

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-guardian'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Sections
SECTIONS = [
    'technology', 'science', 'world', 'business',
    'environment', 'education', 'health'
]

class GuardianScraper:
    def __init__(self):
        # Check for API key
        self.api_key = os.getenv('GUARDIAN_API_KEY')

        if not self.api_key:
            print("⚠️  WARNING: No GUARDIAN_API_KEY found")
            print("   Get free key at: https://open-platform.theguardian.com/")
            print("   Will skip Guardian scraping")
            self.api_key = None

    def search_articles(self, section, page_size=50):
        """Search articles by section"""
        if not self.api_key:
            return []

        url = 'https://content.guardianapis.com/search'

        params = {
            'api-key': self.api_key,
            'section': section,
            'page-size': page_size,
            'show-fields': 'bodyText',
            'order-by': 'relevance'
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get('response', {}).get('results', [])
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return []

    def scrape(self, max_sections=7, articles_per_section=50):
        """Scrape Guardian articles"""
        print("="*70)
        print("THE GUARDIAN SCRAPER - QUALITY JOURNALISM")
        print("="*70)

        if not self.api_key:
            print("NO API KEY - Skipping")
            print("="*70)
            return 0

        print(f"Sections: {min(len(SECTIONS), max_sections)}")
        print(f"Articles per section: {articles_per_section}")
        print("FREE tier: 12,000 requests/day")
        print("="*70)

        examples = []

        for i, section in enumerate(SECTIONS[:max_sections], 1):
            print(f"\n[{i}/{min(len(SECTIONS), max_sections)}] {section}")

            articles = self.search_articles(section, articles_per_section)
            print(f"  ✅ Found {len(articles)} articles")

            for article in articles:
                fields = article.get('fields', {})
                body = fields.get('bodyText', '')

                if not body:
                    continue

                example = {
                    'input': article.get('webTitle', ''),
                    'output': body[:2000],
                    'source': 'guardian',
                    'category': f'news_{section}',
                    'published': article.get('webPublicationDate', '')
                }
                examples.append(example)

            time.sleep(1)

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'guardian_{timestamp}.jsonl'

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
    parser.add_argument('--max-sections', type=int, default=7, help='Max sections')
    parser.add_argument('--articles-per-section', type=int, default=50, help='Articles per section')

    args = parser.parse_args()

    scraper = GuardianScraper()
    scraper.scrape(args.max_sections, args.articles_per_section)

if __name__ == '__main__':
    main()
