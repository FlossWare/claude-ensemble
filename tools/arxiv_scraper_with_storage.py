#!/usr/bin/env python3
"""
arXiv Scraper with LOCAL STORAGE + Multi-Provider Generation
- Stores raw papers locally (can rescrape later!)
- Uses multi-provider fallback
- Tracks which papers have been processed
"""

import os
import json
import requests
import time
import sys
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

# Import multi-provider generator
sys.path.insert(0, str(Path(__file__).parent.parent / 'shared'))
from multi_provider_generator import MultiProviderGenerator

# NAS Storage Directories
NAS_BASE = Path('/mnt/nas/web-scrape')
RAW_PAPERS_DIR = NAS_BASE / 'raw-papers'
SYNTHETIC_DATA_DIR = NAS_BASE / 'synthetic-data'
PROCESSED_TRACKER = NAS_BASE / 'processed_papers.json'

class ArxivScraperWithStorage:
    """Scrape arXiv + store papers + generate training data"""

    def __init__(self):
        self.arxiv_api = 'https://export.arxiv.org/api/query'
        self.generator = MultiProviderGenerator()

        # Create directories
        RAW_PAPERS_DIR.mkdir(parents=True, exist_ok=True)
        SYNTHETIC_DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Load processed tracker
        self.processed = self._load_processed()

    def _load_processed(self):
        """Load list of processed paper IDs"""
        if PROCESSED_TRACKER.exists():
            with open(PROCESSED_TRACKER) as f:
                return json.load(f)
        return {'papers': [], 'count': 0}

    def _save_processed(self):
        """Save processed papers tracker"""
        with open(PROCESSED_TRACKER, 'w') as f:
            json.dump(self.processed, f, indent=2)

    def search_and_store(self, query, max_results=100):
        """Search arXiv and store papers locally"""

        print(f"\n🔬 Searching arXiv: {query}")
        print(f"Target: {max_results} papers")

        params = {
            'search_query': query,
            'start': 0,
            'max_results': max_results,
            'sortBy': 'relevance',
            'sortOrder': 'descending'
        }

        try:
            response = requests.get(self.arxiv_api, params=params, timeout=30)

            if response.status_code == 200:
                papers = self._parse_arxiv_response(response.text)
                print(f"✓ Found {len(papers)} papers")

                # Store each paper
                stored = 0
                for paper in papers:
                    paper_id = paper['link'].split('/')[-1]

                    # Skip if already processed
                    if paper_id in self.processed['papers']:
                        continue

                    # Store paper
                    self._store_paper(paper)
                    stored += 1

                print(f"✓ Stored {stored} new papers locally")
                return papers

        except Exception as e:
            print(f"❌ Error: {e}")

        return []

    def _store_paper(self, paper):
        """Store paper locally as JSON"""

        paper_id = paper['link'].split('/')[-1]
        filename = f"{paper_id}.json"
        filepath = RAW_PAPERS_DIR / filename

        # Add metadata
        paper['stored_at'] = datetime.now().isoformat()
        paper['processed'] = False

        # Save
        with open(filepath, 'w') as f:
            json.dump(paper, f, indent=2)

    def _parse_arxiv_response(self, xml_text):
        """Parse arXiv XML"""
        papers = []
        root = ET.fromstring(xml_text)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}

        for entry in root.findall('atom:entry', ns):
            try:
                paper = {
                    'title': entry.find('atom:title', ns).text.strip(),
                    'summary': entry.find('atom:summary', ns).text.strip(),
                    'authors': [author.find('atom:name', ns).text
                               for author in entry.findall('atom:author', ns)],
                    'link': entry.find('atom:id', ns).text,
                    'published': entry.find('atom:published', ns).text[:10]
                }
                papers.append(paper)
            except:
                continue

        return papers

    def generate_from_stored(self, max_papers=None):
        """Generate training data from stored papers"""

        print(f"\n📚 GENERATING TRAINING DATA FROM STORED PAPERS")
        print(f"{'='*70}")

        # Get all stored papers
        paper_files = list(RAW_PAPERS_DIR.glob('*.json'))

        if max_papers:
            paper_files = paper_files[:max_papers]

        print(f"Processing {len(paper_files)} papers...")
        print()

        dataset = []

        for i, filepath in enumerate(paper_files):
            # Load paper
            with open(filepath) as f:
                paper = json.load(f)

            paper_id = paper['link'].split('/')[-1]

            # Skip if already processed
            if paper_id in self.processed['papers']:
                continue

            print(f"  [{i+1}/{len(paper_files)}] {paper['title'][:60]}...")

            # Generate examples
            examples = self._generate_examples(paper)

            if examples:
                dataset.extend(examples)

                # Mark as processed
                paper['processed'] = True
                with open(filepath, 'w') as f:
                    json.dump(paper, f, indent=2)

                self.processed['papers'].append(paper_id)
                self.processed['count'] += 1
                self._save_processed()

                print(f"    ✓ Generated {len(examples)} examples")

            time.sleep(0.5)  # Small delay

        return dataset

    def _generate_examples(self, paper):
        """Generate training examples from paper"""

        examples = []

        # Example 1: Explain the paper
        prompt1 = f"""Explain this research paper in simple terms:

Title: {paper['title']}
Authors: {', '.join(paper['authors'][:3])}

Abstract: {paper['summary'][:500]}

Provide a 2-3 sentence explanation:"""

        completion1 = self.generator.generate(prompt1, 512)

        if completion1:
            examples.append({
                'prompt': prompt1,
                'completion': completion1,
                'source': 'arXiv',
                'paper_id': paper['link'].split('/')[-1],
                'paper_title': paper['title'],
                'type': 'paper_explanation'
            })

        # Example 2: Key concepts
        prompt2 = f"""What are the key concepts in this paper?

Title: {paper['title']}
Abstract: {paper['summary'][:400]}

List the main technical concepts:"""

        completion2 = self.generator.generate(prompt2, 512)

        if completion2:
            examples.append({
                'prompt': prompt2,
                'completion': completion2,
                'source': 'arXiv',
                'paper_id': paper['link'].split('/')[-1],
                'paper_title': paper['title'],
                'type': 'key_concepts'
            })

        return examples

    def save_dataset(self, dataset, topic):
        """Save dataset to JSONL"""

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'arxiv_{topic}_{len(dataset)}_{timestamp}.jsonl'
        filepath = SYNTHETIC_DATA_DIR / filename

        with open(filepath, 'w') as f:
            for ex in dataset:
                f.write(json.dumps(ex) + '\n')

        print(f"\n✅ Saved {len(dataset)} examples to {filepath}")

        # Print stats
        stats = self.generator.get_stats()
        print(f"\n📊 Generation Stats:")
        print(f"  Total requests: {stats['total_requests']}")
        print(f"  By provider: {stats['by_provider']}")
        print(f"  Total cost: ${stats['total_cost_usd']:.4f}")

        return filepath


if __name__ == '__main__':
    import sys

    scraper = ArxivScraperWithStorage()

    topic = sys.argv[1] if len(sys.argv) > 1 else 'machine learning'
    num_papers = int(sys.argv[2]) if len(sys.argv) > 2 else 50

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🌟 arXiv SCRAPER WITH LOCAL STORAGE")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"Topic: {topic}")
    print(f"Target: {num_papers} papers")
    print(f"Storage: {RAW_PAPERS_DIR}")
    print(f"Already processed: {len(scraper.processed['papers'])} papers")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Step 1: Search and store papers
    papers = scraper.search_and_store(topic, num_papers)

    if papers:
        # Step 2: Generate training data
        dataset = scraper.generate_from_stored(max_papers=num_papers)

        if dataset:
            # Step 3: Save
            scraper.save_dataset(dataset, topic.replace(' ', '_'))

            print("\n🎉 COMPLETE!")
            print(f"   Raw papers stored: {len(list(RAW_PAPERS_DIR.glob('*.json')))}")
            print(f"   Can rescrape anytime with: python3 {__file__} --rescrape")
