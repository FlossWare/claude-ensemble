#!/usr/bin/env python3
"""
SEMANTIC SCHOLAR SCRAPER
AI-powered academic paper search across 200M+ papers
Uses FREE API (no auth needed for basic usage!)
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-semantic-scholar'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Research topics
TOPICS = [
    'machine learning', 'deep learning', 'natural language processing',
    'computer vision', 'reinforcement learning', 'neural networks',
    'distributed systems', 'cloud computing', 'cybersecurity',
    'quantum computing', 'blockchain', 'bioinformatics',
    'climate change', 'gene therapy', 'immunology',
    'economics', 'psychology', 'neuroscience',
]

class SemanticScholarScraper:
    def __init__(self):
        self.base_url = 'https://api.semanticscholar.org/graph/v1'

    def search_papers(self, query, limit=100):
        """Search papers by query"""
        url = f'{self.base_url}/paper/search'

        params = {
            'query': query,
            'limit': limit,
            'fields': 'title,abstract,authors,year,citationCount'
        }

        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            return data.get('data', [])
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return []

    def scrape(self, max_topics=15, papers_per_topic=100):
        """Scrape papers from Semantic Scholar"""
        print("="*70)
        print("SEMANTIC SCHOLAR SCRAPER - AI-POWERED PAPERS")
        print("="*70)
        print(f"Topics: {min(len(TOPICS), max_topics)}")
        print(f"Papers per topic: {papers_per_topic}")
        print("FREE API - 200M+ papers!")
        print("="*70)

        examples = []

        for i, topic in enumerate(TOPICS[:max_topics], 1):
            print(f"\n[{i}/{min(len(TOPICS), max_topics)}] {topic}")

            papers = self.search_papers(topic, papers_per_topic)
            print(f"  ✅ Found {len(papers)} papers")

            for paper in papers:
                if not paper.get('abstract'):
                    continue

                example = {
                    'input': f"Research paper: {paper.get('title', '')}",
                    'output': paper['abstract'][:2000],
                    'source': 'semantic_scholar',
                    'category': 'research_paper',
                    'topic': topic,
                    'year': paper.get('year'),
                    'citations': paper.get('citationCount', 0)
                }
                examples.append(example)

            time.sleep(1)  # Rate limiting

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'semantic_scholar_{timestamp}.jsonl'

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
    parser.add_argument('--max-topics', type=int, default=15, help='Max topics')
    parser.add_argument('--papers-per-topic', type=int, default=100, help='Papers per topic')

    args = parser.parse_args()

    scraper = SemanticScholarScraper()
    scraper.scrape(args.max_topics, args.papers_per_topic)

if __name__ == '__main__':
    main()
