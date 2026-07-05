#!/usr/bin/env python3
"""
CORE SCRAPER
Scrapes from CORE (270M+ research papers)
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

TOPICS = [
    'artificial intelligence', 'machine learning', 'deep learning',
    'computer science', 'software engineering', 'data science',
    'cybersecurity', 'cloud computing', 'quantum computing',
    'biology', 'chemistry', 'physics', 'mathematics',
    'medicine', 'psychology', 'economics', 'sociology',
]

class COREScraper:
    def __init__(self):
        self.base_url = 'https://api.core.ac.uk/v3'

    def search_papers(self, query, limit=100):
        """Search CORE for papers"""
        url = f'{self.base_url}/search/works'

        params = {
            'q': query,
            'limit': limit
        }

        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            return data.get('results', [])
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return []

    def scrape(self, max_topics=15, papers_per_topic=100):
        """Scrape CORE"""
        print("="*70)
        print("CORE SCRAPER - 270M+ RESEARCH PAPERS")
        print("="*70)
        print(f"Topics: {min(len(TOPICS), max_topics)}")
        print(f"Papers per topic: {papers_per_topic}")
        print("FREE API")
        print("="*70)

        examples = []

        for i, topic in enumerate(TOPICS[:max_topics], 1):
            print(f"\n[{i}/{min(len(TOPICS), max_topics)}] {topic}")

            papers = self.search_papers(topic, papers_per_topic)
            print(f"  ✅ Found {len(papers)} papers")

            for paper in papers:
                abstract = paper.get('abstract', '')
                if not abstract or len(abstract) < 100:
                    continue

                example = {
                    'input': f"Research: {paper.get('title', '')}",
                    'output': abstract[:2000],
                    'source': 'core',
                    'category': 'research',
                    'topic': topic
                }
                examples.append(example)

            time.sleep(1)

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'core_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n{'='*70}")
            print(f"✅ COMPLETE! Scraped {len(examples)} papers")
            print(f"💾 Saved to {data_file.name}")
            print(f"{'='*70}")

        return len(examples)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-topics', type=int, default=15)
    parser.add_argument('--papers-per-topic', type=int, default=100)
    args = parser.parse_args()

    scraper = COREScraper()
    scraper.scrape(args.max_topics, args.papers_per_topic)

if __name__ == '__main__':
    main()
