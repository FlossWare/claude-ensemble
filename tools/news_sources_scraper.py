#!/usr/bin/env python3
"""
ADDITIONAL NEWS SOURCES SCRAPER
Scrapes from multiple free news sources
- NYT Archive API (FREE!)
- BBC RSS feeds
- Reuters RSS feeds
- AP News RSS
"""

import json
import time
import requests
import feedparser
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-news-multi'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# RSS Feeds
RSS_FEEDS = [
    ('BBC World', 'http://feeds.bbci.co.uk/news/world/rss.xml'),
    ('BBC Technology', 'http://feeds.bbci.co.uk/news/technology/rss.xml'),
    ('BBC Science', 'http://feeds.bbci.co.uk/news/science_and_environment/rss.xml'),
    ('BBC Business', 'http://feeds.bbci.co.uk/news/business/rss.xml'),
    ('Reuters World', 'https://www.reutersagency.com/feed/?taxonomy=best-regions&post_type=best'),
    ('Reuters Tech', 'https://www.reutersagency.com/feed/?best-topics=tech'),
]

class NewsSourcesScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Educational Research Bot 1.0'
        })

    def scrape_rss(self, feed_name, feed_url, max_articles=50):
        """Scrape RSS feed"""
        try:
            feed = feedparser.parse(feed_url)
            articles = []

            for entry in feed.entries[:max_articles]:
                summary = entry.get('summary', '') or entry.get('description', '')

                # Clean HTML from summary
                if summary:
                    soup = BeautifulSoup(summary, 'html.parser')
                    summary = soup.get_text(strip=True)

                if not summary or len(summary) < 50:
                    continue

                articles.append({
                    'title': entry.get('title', ''),
                    'content': summary[:2000],
                    'published': entry.get('published', ''),
                    'link': entry.get('link', '')
                })

            return articles
        except Exception as e:
            print(f"  ⚠️  Error: {e}")
            return []

    def scrape_nyt_archive(self, year=2024, month=1, max_articles=100):
        """Scrape NYT Archive API (FREE!)"""
        url = f'https://api.nytimes.com/svc/archive/v1/{year}/{month}.json'

        # Note: NYT Archive API is FREE, no key needed for archive access
        # But rate limited to 5 requests/minute

        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                articles = data.get('response', {}).get('docs', [])

                return [
                    {
                        'title': a.get('headline', {}).get('main', ''),
                        'content': a.get('abstract', '') or a.get('snippet', ''),
                        'published': a.get('pub_date', ''),
                        'section': a.get('section_name', '')
                    }
                    for a in articles[:max_articles]
                    if a.get('abstract') or a.get('snippet')
                ]
            else:
                print(f"  ⚠️  NYT: Status {response.status_code}")
                return []
        except Exception as e:
            print(f"  ⚠️  NYT Error: {e}")
            return []

    def scrape(self, max_articles_per_feed=50):
        """Scrape all news sources"""
        print("="*70)
        print("ADDITIONAL NEWS SOURCES SCRAPER")
        print("="*70)
        print(f"RSS Feeds: {len(RSS_FEEDS)}")
        print(f"Articles per feed: {max_articles_per_feed}")
        print("="*70)

        examples = []

        # RSS Feeds
        print("\n📰 RSS Feeds:")
        for feed_name, feed_url in RSS_FEEDS:
            print(f"\n  [{feed_name}]")

            articles = self.scrape_rss(feed_name, feed_url, max_articles_per_feed)
            print(f"    ✅ {len(articles)} articles")

            for article in articles:
                example = {
                    'input': article['title'],
                    'output': article['content'],
                    'source': f'rss_{feed_name.lower().replace(" ", "_")}',
                    'category': 'news',
                    'published': article.get('published', '')
                }
                examples.append(example)

            time.sleep(2)

        # NYT Archive (careful with rate limits!)
        print(f"\n📰 NYT Archive (2024/01):")
        nyt_articles = self.scrape_nyt_archive(2024, 1, 100)
        print(f"    ✅ {len(nyt_articles)} articles")

        for article in nyt_articles:
            example = {
                'input': article['title'],
                'output': article['content'],
                'source': 'nyt_archive',
                'category': 'news',
                'section': article.get('section', ''),
                'published': article.get('published', '')
            }
            examples.append(example)

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'news_multi_{timestamp}.jsonl'

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
    parser.add_argument('--max-articles-per-feed', type=int, default=50, help='Max articles per RSS feed')

    args = parser.parse_args()

    scraper = NewsSourcesScraper()
    scraper.scrape(args.max_articles_per_feed)

if __name__ == '__main__':
    main()
