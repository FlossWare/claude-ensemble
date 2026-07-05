#!/usr/bin/env python3
"""
HACKER NEWS SCRAPER
Scrapes top tech stories and discussions from HackerNews
Uses free Firebase API (no auth needed!)
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-hackernews'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

class HackerNewsScraper:
    def __init__(self):
        self.base_url = 'https://hacker-news.firebaseio.com/v0'

    def get_top_stories(self, limit=500):
        """Get top story IDs"""
        url = f'{self.base_url}/topstories.json'

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            story_ids = response.json()
            return story_ids[:limit]
        except Exception as e:
            print(f"❌ Error fetching top stories: {e}")
            return []

    def get_story(self, story_id):
        """Get story details"""
        url = f'{self.base_url}/item/{story_id}.json'

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except:
            return None

    def scrape(self, max_stories=500):
        """Scrape HackerNews stories"""
        print("="*70)
        print("HACKER NEWS SCRAPER - TECH DISCUSSIONS")
        print("="*70)
        print(f"Target: {max_stories} stories")
        print("FREE Firebase API")
        print("="*70)

        # Get top story IDs
        print("\n🔍 Fetching top stories...")
        story_ids = self.get_top_stories(max_stories)
        print(f"✅ Found {len(story_ids)} story IDs")

        examples = []

        for i, story_id in enumerate(story_ids, 1):
            if i % 50 == 0:
                print(f"\n[{i}/{len(story_ids)}] Progress...")

            story = self.get_story(story_id)
            if not story:
                continue

            # Only keep stories with text content
            if story.get('type') == 'story' and story.get('text'):
                example = {
                    'input': story.get('title', ''),
                    'output': story['text'][:2000],  # First 2000 chars
                    'source': 'hackernews',
                    'category': 'tech_discussion',
                    'score': story.get('score', 0),
                    'hn_id': story_id
                }
                examples.append(example)

            # Also collect Ask HN posts
            elif story.get('type') == 'story' and story.get('title', '').startswith('Ask HN:'):
                example = {
                    'input': story.get('title', ''),
                    'output': story.get('text', story.get('title', ''))[:2000],
                    'source': 'hackernews',
                    'category': 'tech_question',
                    'score': story.get('score', 0),
                    'hn_id': story_id
                }
                examples.append(example)

            time.sleep(0.1)  # Rate limiting

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'hackernews_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n{'='*70}")
            print(f"✅ COMPLETE! Scraped {len(story_ids)} stories")
            print(f"Generated {len(examples)} quality examples")
            print(f"💾 Saved to {data_file.name}")
            print(f"{'='*70}")

        return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-stories', type=int, default=500, help='Max stories to scrape')

    args = parser.parse_args()

    scraper = HackerNewsScraper()
    scraper.scrape(args.max_stories)

if __name__ == '__main__':
    main()
