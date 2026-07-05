#!/usr/bin/env python3
"""
ELECTRONICS & ELECTRICAL ENGINEERING SCRAPER
Scrapes from multiple EE/electronics sources
- All About Circuits tutorials
- Electronics tutorials
- Wikipedia EE topics
- arXiv EE papers
- Electronics Stack Exchange (via main Stack Exchange scraper)
"""

import json
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-electronics'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Wikipedia EE topics
WIKIPEDIA_EE_TOPICS = [
    'Ohm\'s law', 'Kirchhoff\'s circuit laws', 'Thevenin\'s theorem',
    'Norton\'s theorem', 'Superposition theorem', 'Maximum power transfer theorem',
    'Operational amplifier', 'Transistor', 'MOSFET', 'BJT',
    'Diode', 'LED', 'Zener diode', 'Capacitor', 'Inductor',
    'Resistor', 'Transformer', 'Electric motor', 'Generator',
    'Rectifier', 'Inverter', 'Voltage regulator', 'Filter (electronics)',
    'Amplifier', 'Oscillator', 'Logic gate', 'Flip-flop',
    'Microcontroller', 'Arduino', 'Raspberry Pi', 'FPGA',
    'PCB design', 'Integrated circuit', 'Digital signal processing',
    'Analog signal', 'Digital signal', 'Modulation',
    'Power supply', 'Battery', 'Solar cell', 'Electric circuit',
]

# arXiv EE categories
ARXIV_EE_CATEGORIES = [
    'eess.SP',  # Signal Processing
    'eess.SY',  # Systems and Control
    'cs.SY',    # Systems and Control (CS)
    'physics.app-ph',  # Applied Physics
]

class ElectronicsEEScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Educational Research Bot 1.0'
        })

    def scrape_wikipedia_topic(self, topic):
        """Scrape Wikipedia article for EE topic"""
        url = f'https://en.wikipedia.org/api/rest_v1/page/summary/{topic}'

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            extract = data.get('extract', '')
            if len(extract) < 100:
                return None

            return {
                'title': data.get('title', topic),
                'content': extract,
                'url': data.get('content_urls', {}).get('desktop', {}).get('page', '')
            }
        except Exception as e:
            return None

    def scrape_arxiv_ee(self, category, max_results=50):
        """Search arXiv for EE papers"""
        base_url = 'http://export.arxiv.org/api/query'

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

            # Parse XML
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
            print(f"  ❌ arXiv Error: {e}")
            return []

    def scrape(self, max_wiki_topics=40, max_arxiv_per_category=50):
        """Scrape all EE sources"""
        print("="*70)
        print("ELECTRONICS & ELECTRICAL ENGINEERING SCRAPER")
        print("="*70)
        print(f"Wikipedia EE topics: {min(len(WIKIPEDIA_EE_TOPICS), max_wiki_topics)}")
        print(f"arXiv EE categories: {len(ARXIV_EE_CATEGORIES)}")
        print(f"Papers per category: {max_arxiv_per_category}")
        print("="*70)

        examples = []

        # Wikipedia EE Topics
        print("\n📚 Wikipedia EE Topics:")
        for i, topic in enumerate(WIKIPEDIA_EE_TOPICS[:max_wiki_topics], 1):
            if i % 10 == 0:
                print(f"  [{i}/{min(len(WIKIPEDIA_EE_TOPICS), max_wiki_topics)}] Progress...")

            article = self.scrape_wikipedia_topic(topic)
            if not article:
                continue

            example = {
                'input': f"Explain {topic} in electrical engineering",
                'output': article['content'],
                'source': 'wikipedia_ee',
                'category': 'electronics_tutorial',
                'topic': topic
            }
            examples.append(example)

            time.sleep(1)  # Be polite

        print(f"  ✅ Scraped {len(examples)} Wikipedia EE articles")

        # arXiv EE Papers
        print("\n📄 arXiv EE Papers:")
        for i, category in enumerate(ARXIV_EE_CATEGORIES, 1):
            print(f"\n  [{i}/{len(ARXIV_EE_CATEGORIES)}] Category: {category}")

            papers = self.scrape_arxiv_ee(category, max_arxiv_per_category)
            print(f"    ✅ {len(papers)} papers")

            for paper in papers:
                example = {
                    'input': f"Research paper: {paper['title']}",
                    'output': paper['abstract'][:2000],
                    'source': 'arxiv_ee',
                    'category': 'ee_research',
                    'arxiv_category': category
                }
                examples.append(example)

            time.sleep(3)  # Be nice to arXiv

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'electronics_ee_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n{'='*70}")
            print(f"✅ COMPLETE! Scraped {len(examples)} EE examples")
            print(f"💾 Saved to {data_file.name}")
            print(f"{'='*70}")

        return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-wiki-topics', type=int, default=40, help='Max Wikipedia topics')
    parser.add_argument('--max-arxiv-per-category', type=int, default=50, help='Max arXiv papers per category')

    args = parser.parse_args()

    scraper = ElectronicsEEScraper()
    scraper.scrape(args.max_wiki_topics, args.max_arxiv_per_category)

if __name__ == '__main__':
    main()
