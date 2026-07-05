#!/usr/bin/env python3
"""
REDDIT SCRAPER
Scrapes popular Reddit posts and comments for conversational training data
Uses Reddit's free JSON API (no authentication needed!)
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-reddit'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Popular subreddits with quality content
SUBREDDITS = [
    # Tech
    'programming', 'learnprogramming', 'webdev', 'machinelearning',
    'datascience', 'linux', 'sysadmin', 'devops',

    # Science
    'science', 'askscience', 'physics', 'biology', 'chemistry',

    # Education
    'explainlikeimfive', 'askhistorians', 'AskEngineers', 'math',

    # General
    'todayilearned', 'lifeprotips', 'productivity', 'fitness',

    # Creative
    'writing', 'books', 'philosophy', 'cooking',
]

class RedditScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Educational Research Bot 1.0'
        })

    def get_top_posts(self, subreddit, limit=25):
        """Get top posts from a subreddit"""
        url = f"https://www.reddit.com/r/{subreddit}/top.json"
        params = {
            'limit': limit,
            't': 'month'  # Top of the month
        }

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            posts = []
            for post in data['data']['children']:
                post_data = post['data']

                # Only keep text posts with substance
                if post_data.get('selftext') and len(post_data.get('selftext', '')) > 100:
                    posts.append({
                        'title': post_data['title'],
                        'selftext': post_data['selftext'],
                        'score': post_data['score'],
                        'num_comments': post_data['num_comments'],
                        'permalink': post_data['permalink']
                    })

            return posts
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return []

    def scrape_subreddit(self, subreddit, max_posts=25):
        """Scrape posts from a subreddit"""
        print(f"\n[r/{subreddit}]")

        posts = self.get_top_posts(subreddit, max_posts)
        if not posts:
            print(f"  ⚠️  No posts found")
            return 0

        print(f"  ✅ Found {len(posts)} quality posts")

        examples = []

        for post in posts:
            # Create training example (NO API calls!)
            example = {
                'input': post['title'],
                'output': post['selftext'][:2000],  # First 2000 chars
                'source': 'reddit',
                'category': 'discussion',
                'subreddit': subreddit,
                'score': post['score']
            }
            examples.append(example)

        # Save
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        data_file = DATA_DIR / f'reddit_{subreddit}_{timestamp}.jsonl'

        with open(data_file, 'w') as f:
            for ex in examples:
                f.write(json.dumps(ex) + '\n')

        print(f"  💾 Saved {len(examples)} posts")

        return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-posts', type=int, default=25, help='Max posts per subreddit')
    parser.add_argument('--max-subreddits', type=int, default=20, help='Max subreddits')

    args = parser.parse_args()

    scraper = RedditScraper()

    print("="*70)
    print("REDDIT SCRAPER - CONVERSATIONAL DATA")
    print("="*70)
    print(f"Subreddits: {len(SUBREDDITS)}")
    print(f"Max subreddits: {args.max_subreddits}")
    print(f"Posts per subreddit: {args.max_posts}")
    print("FREE Reddit JSON API (no auth needed)")
    print("="*70)

    total = 0

    for subreddit in SUBREDDITS[:args.max_subreddits]:
        count = scraper.scrape_subreddit(subreddit, args.max_posts)
        total += count
        time.sleep(2)  # Rate limiting

    print(f"\n{'='*70}")
    print(f"✅ COMPLETE! Scraped {min(len(SUBREDDITS), args.max_subreddits)} subreddits")
    print(f"Generated {total} discussion examples")
    print(f"{'='*70}")

if __name__ == '__main__':
    main()
