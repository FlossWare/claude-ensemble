#!/usr/bin/env python3
"""
PUBMED SCRAPER
Scrapes medical/biomedical research from PubMed
Uses free NCBI E-utilities API (no authentication needed!)
"""

import json
import time
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-pubmed'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Medical/biomedical topics
PUBMED_TOPICS = [
    # Diseases
    'cancer treatment',
    'diabetes management',
    'heart disease',
    'alzheimers disease',
    'parkinsons disease',
    'covid-19',

    # Medical tech
    'gene therapy',
    'CRISPR',
    'immunotherapy',
    'stem cells',
    'mRNA vaccines',

    # General medicine
    'nutrition',
    'exercise physiology',
    'mental health',
    'antibiotics resistance',
    'clinical trials',
]

class PubMedScraper:
    def __init__(self):
        self.base_search = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
        self.base_fetch = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'

        # NCBI requests tool/email (polite usage)
        self.params = {
            'tool': 'research_bot',
            'email': 'research@example.com'
        }

    def search(self, query, max_results=20):
        """Search PubMed for articles"""
        params = {
            **self.params,
            'db': 'pubmed',
            'term': query,
            'retmax': max_results,
            'retmode': 'json'
        }

        try:
            response = requests.get(self.base_search, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            ids = data.get('esearchresult', {}).get('idlist', [])
            return ids
        except Exception as e:
            print(f"  ❌ Search error: {e}")
            return []

    def fetch_article(self, pmid):
        """Fetch article details"""
        params = {
            **self.params,
            'db': 'pubmed',
            'id': pmid,
            'retmode': 'xml'
        }

        try:
            response = requests.get(self.base_fetch, params=params, timeout=10)
            response.raise_for_status()

            # Parse XML
            root = ET.fromstring(response.content)

            article = root.find('.//Article')
            if article is None:
                return None

            # Extract fields
            title_elem = article.find('.//ArticleTitle')
            abstract_elem = article.find('.//AbstractText')

            if title_elem is None or abstract_elem is None:
                return None

            title = title_elem.text or ''
            abstract = abstract_elem.text or ''

            return {
                'pmid': pmid,
                'title': title,
                'abstract': abstract
            }
        except Exception as e:
            return None

    def scrape_topic(self, topic, max_articles=20):
        """Scrape articles for a topic"""
        print(f"\n{'='*70}")
        print(f"TOPIC: {topic.upper()}")
        print(f"{'='*70}\n")

        # Search
        print(f"  🔍 Searching PubMed...")
        pmids = self.search(topic, max_articles)
        print(f"  ✅ Found {len(pmids)} articles")

        examples = []

        for i, pmid in enumerate(pmids, 1):
            print(f"  [{i}/{len(pmids)}] Fetching PMID {pmid}...")

            article = self.fetch_article(pmid)
            if not article:
                print(f"    ⚠️  Failed to fetch")
                continue

            # Save raw
            raw_file = RAW_DIR / f"{topic.replace(' ', '_')}_{pmid}.json"
            with open(raw_file, 'w') as f:
                json.dump(article, f, indent=2)

            # Create training example (NO LLM API needed!)
            example = {
                'input': f"Summarize this medical research about {topic}:\nTitle: {article['title']}",
                'output': article['abstract'],
                'source': 'pubmed',
                'category': 'medical_research',
                'topic': topic,
                'pmid': pmid
            }
            examples.append(example)

            print(f"    ✅ {article['title'][:50]}...")

            # Rate limiting (NCBI recommends max 3 requests/sec)
            time.sleep(0.4)

        # Save examples
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_topic = topic.replace(' ', '_')
            data_file = DATA_DIR / f'pubmed_{safe_topic}_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n  💾 Saved {len(examples)} examples to {data_file.name}")

        return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-articles', type=int, default=20, help='Max articles per topic')
    parser.add_argument('--max-topics', type=int, default=15, help='Max topics to scrape')

    args = parser.parse_args()

    scraper = PubMedScraper()

    print("="*70)
    print("PUBMED SCRAPER - MEDICAL/BIOMEDICAL RESEARCH")
    print("="*70)
    print(f"Topics: {len(PUBMED_TOPICS)}")
    print(f"Max topics: {args.max_topics}")
    print(f"Articles per topic: {args.max_articles}")
    print(f"FREE NCBI E-utilities API (3 req/sec limit)")
    print("="*70)

    total = 0

    for topic in PUBMED_TOPICS[:args.max_topics]:
        count = scraper.scrape_topic(topic, args.max_articles)
        total += count

    print(f"\n{'='*70}")
    print(f"✅ COMPLETE! Scraped {min(len(PUBMED_TOPICS), args.max_topics)} topics")
    print(f"Generated {total} medical research examples")
    print(f"{'='*70}")

if __name__ == '__main__':
    main()
