#!/usr/bin/env python3
"""
LAW & HISTORY SCRAPER
Scrapes legal and historical content
- Wikipedia law topics
- Wikipedia history topics
- CourtListener (US legal cases) - FREE API!
- Historical periods and events
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime
import os

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-law-history'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Law topics
LAW_TOPICS = [
    # Constitutional law
    'Constitutional law', 'Bill of Rights', 'Separation of powers',
    'Judicial review', 'Due process', 'Equal protection',

    # Criminal law
    'Criminal law', 'Mens rea', 'Actus reus', 'Criminal procedure',
    'Fourth Amendment', 'Fifth Amendment', 'Sixth Amendment',

    # Civil law
    'Contract law', 'Tort law', 'Property law', 'Negligence',
    'Strict liability', 'Intentional tort', 'Breach of contract',

    # Business law
    'Corporate law', 'Securities law', 'Intellectual property',
    'Patent law', 'Trademark', 'Copyright', 'Trade secret',

    # Other
    'Administrative law', 'Tax law', 'Labor law', 'Environmental law',
    'International law', 'Antitrust law', 'Bankruptcy law',
]

# History topics
HISTORY_TOPICS = [
    # Ancient history
    'Ancient Egypt', 'Ancient Greece', 'Ancient Rome',
    'Roman Empire', 'Byzantine Empire', 'Persian Empire',

    # Medieval
    'Middle Ages', 'Feudalism', 'Crusades', 'Black Death',
    'Renaissance', 'Protestant Reformation',

    # Modern Europe
    'Age of Enlightenment', 'French Revolution', 'Napoleonic Wars',
    'Industrial Revolution', 'World War I', 'World War II',
    'Cold War', 'Fall of the Berlin Wall',

    # American history
    'American Revolution', 'American Civil War', 'Great Depression',
    'New Deal', 'Civil Rights Movement', 'Vietnam War',

    # World history
    'Colonialism', 'Decolonization', 'Scientific Revolution',
    'Space Age', 'Information Age', 'Globalization',

    # Historical figures
    'Julius Caesar', 'Napoleon Bonaparte', 'Abraham Lincoln',
    'Winston Churchill', 'Mahatma Gandhi', 'Martin Luther King Jr.',
]

class LawHistoryScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Educational Research Bot 1.0'
        })
        # CourtListener API token (optional, works without for basic access)
        self.cl_token = os.getenv('COURTLISTENER_TOKEN')

    def scrape_wikipedia_topic(self, topic):
        """Scrape Wikipedia article"""
        url = f'https://en.wikipedia.org/api/rest_v1/page/summary/{topic}'

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            extract = data.get('extract', '')
            if len(extract) < 100:
                return None

            return extract
        except:
            return None

    def scrape_courtlistener(self, query='supreme court', max_results=100):
        """Search CourtListener for legal cases"""
        url = 'https://www.courtlistener.com/api/rest/v3/search/'

        params = {
            'q': query,
            'type': 'o',  # opinions
            'order_by': 'score desc',
        }

        headers = {}
        if self.cl_token:
            headers['Authorization'] = f'Token {self.cl_token}'

        try:
            response = self.session.get(url, params=params, headers=headers, timeout=15)

            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                return results[:max_results]
            else:
                print(f"  ⚠️  CourtListener: Status {response.status_code}")
                return []
        except Exception as e:
            print(f"  ⚠️  CourtListener Error: {e}")
            return []

    def scrape(self, max_law_topics=30, max_history_topics=40, max_cases=50):
        """Scrape law & history content"""
        print("="*70)
        print("LAW & HISTORY SCRAPER")
        print("="*70)
        print(f"Law topics: {min(len(LAW_TOPICS), max_law_topics)}")
        print(f"History topics: {min(len(HISTORY_TOPICS), max_history_topics)}")
        print(f"Legal cases: {max_cases}")
        print("="*70)

        examples = []

        # Law topics
        print("\n⚖️  Wikipedia Law Topics:")
        for i, topic in enumerate(LAW_TOPICS[:max_law_topics], 1):
            if i % 10 == 0:
                print(f"  [{i}/{min(len(LAW_TOPICS), max_law_topics)}] Progress...")

            content = self.scrape_wikipedia_topic(topic)
            if not content:
                continue

            example = {
                'input': f"Explain {topic}",
                'output': content,
                'source': 'wikipedia_law',
                'category': 'law',
                'topic': topic
            }
            examples.append(example)

            time.sleep(1)

        law_count = len(examples)
        print(f"  ✅ Scraped {law_count} law topics")

        # History topics
        print("\n📜 Wikipedia History Topics:")
        for i, topic in enumerate(HISTORY_TOPICS[:max_history_topics], 1):
            if i % 10 == 0:
                print(f"  [{i}/{min(len(HISTORY_TOPICS), max_history_topics)}] Progress...")

            content = self.scrape_wikipedia_topic(topic)
            if not content:
                continue

            example = {
                'input': f"What was {topic}?",
                'output': content,
                'source': 'wikipedia_history',
                'category': 'history',
                'topic': topic
            }
            examples.append(example)

            time.sleep(1)

        history_count = len(examples) - law_count
        print(f"  ✅ Scraped {history_count} history topics")

        # CourtListener cases
        print("\n⚖️  CourtListener Legal Cases:")
        cases = self.scrape_courtlistener('supreme court', max_cases)

        if cases:
            print(f"  ✅ {len(cases)} legal cases")

            for case in cases:
                snippet = case.get('snippet', '') or case.get('text', '')
                if not snippet or len(snippet) < 50:
                    continue

                example = {
                    'input': f"Legal case: {case.get('caseName', '')}",
                    'output': snippet[:2000],
                    'source': 'courtlistener',
                    'category': 'legal_case',
                    'court': case.get('court', '')
                }
                examples.append(example)
        else:
            print(f"  ⚠️  CourtListener unavailable (needs token or rate limited)")

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'law_history_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n{'='*70}")
            print(f"✅ COMPLETE! Scraped {len(examples)} examples")
            print(f"   Law: {law_count}, History: {history_count}, Cases: {len(examples) - law_count - history_count}")
            print(f"💾 Saved to {data_file.name}")
            print(f"{'='*70}")

        return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-law-topics', type=int, default=30, help='Max law topics')
    parser.add_argument('--max-history-topics', type=int, default=40, help='Max history topics')
    parser.add_argument('--max-cases', type=int, default=50, help='Max legal cases')

    args = parser.parse_args()

    scraper = LawHistoryScraper()
    scraper.scrape(args.max_law_topics, args.max_history_topics, args.max_cases)

if __name__ == '__main__':
    main()
