#!/usr/bin/env python3
"""
PhD THESIS SCRAPER
Scrapes PhD theses from open repositories (mostly PDFs)
Sources: ProQuest Open, university repositories, arXiv theses
"""

import json
import requests
from pathlib import Path
from datetime import datetime
import PyPDF2
import time

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-theses'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Open access thesis URLs (some universities make theses publicly available)
THESIS_SOURCES = [
    # These are example URLs - in reality you'd search repositories
    # Using arXiv as it has many PhD-level papers
]

# arXiv categories that often contain thesis-level work
THESIS_CATEGORIES = [
    'cs.AI',      # Artificial Intelligence
    'cs.LG',      # Machine Learning
    'math.ST',    # Statistics Theory
    'physics.comp-ph',  # Computational Physics
    'q-bio.QM',   # Quantitative Methods in Biology
    'econ.EM',    # Econometrics
]

class ThesisScraper:
    def __init__(self):
        self.session = requests.Session()

    def search_arxiv_theses(self, category, max_results=50):
        """Search arXiv for thesis-level papers"""
        base_url = 'http://export.arxiv.org/api/query'

        # Search for papers (many are PhD thesis level)
        search_query = f'cat:{category}'

        params = {
            'search_query': search_query,
            'start': 0,
            'max_results': max_results,
            'sortBy': 'relevance',
            'sortOrder': 'descending'
        }

        try:
            response = self.session.get(base_url, params=params, timeout=30)
            response.raise_for_status()

            # Parse XML (arXiv returns Atom XML)
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)

            papers = []
            for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
                title_elem = entry.find('{http://www.w3.org/2005/Atom}title')
                summary_elem = entry.find('{http://www.w3.org/2005/Atom}summary')

                if title_elem is not None and summary_elem is not None:
                    papers.append({
                        'title': title_elem.text.strip(),
                        'abstract': summary_elem.text.strip(),
                        'category': category
                    })

            return papers
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return []

    def scrape_category(self, category, max_papers=50):
        """Scrape thesis-level papers from a category"""
        print(f"\n{'='*70}")
        print(f"CATEGORY: {category.upper()}")
        print(f"{'='*70}\n")

        print(f"  🔍 Searching arXiv...")
        papers = self.search_arxiv_theses(category, max_papers)
        print(f"  ✅ Found {len(papers)} papers")

        examples = []

        for i, paper in enumerate(papers, 1):
            print(f"  [{i}/{len(papers)}] {paper['title'][:60]}...")

            # Create training example (NO LLM API needed!)
            example = {
                'input': f"Summarize this research paper about {category}:\nTitle: {paper['title']}",
                'output': paper['abstract'],
                'source': 'thesis_arxiv',
                'category': 'phd_research',
                'arxiv_category': category
            }
            examples.append(example)

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_cat = category.replace('.', '_').replace('/', '_')
            data_file = DATA_DIR / f'thesis_{safe_cat}_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"  💾 Saved {len(examples)} examples")

        return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-papers', type=int, default=50, help='Max papers per category')
    parser.add_argument('--max-categories', type=int, default=6, help='Max categories')

    args = parser.parse_args()

    scraper = ThesisScraper()

    print("="*70)
    print("PhD THESIS SCRAPER - ADVANCED RESEARCH")
    print("="*70)
    print(f"Categories: {len(THESIS_CATEGORIES)}")
    print(f"Max categories: {args.max_categories}")
    print(f"Papers per category: {args.max_papers}")
    print("="*70)

    total = 0

    for category in THESIS_CATEGORIES[:args.max_categories]:
        count = scraper.scrape_category(category, args.max_papers)
        total += count
        time.sleep(3)  # Be nice to arXiv

    print(f"\n{'='*70}")
    print(f"✅ COMPLETE! Scraped {min(len(THESIS_CATEGORIES), args.max_categories)} categories")
    print(f"Generated {total} thesis-level research examples")
    print(f"{'='*70}")

if __name__ == '__main__':
    main()
