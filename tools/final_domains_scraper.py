#!/usr/bin/env python3
"""
FINAL 4 DOMAINS SCRAPER
Makes the model WORLD-CLASS across ALL human knowledge
- Mathematics
- Economics & Finance
- Art & Literature
- Languages & Linguistics
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Mathematics topics
MATH_TOPICS = [
    # Foundational
    'Calculus', 'Linear algebra', 'Differential equations',
    'Abstract algebra', 'Real analysis', 'Complex analysis',
    'Topology', 'Number theory', 'Set theory', 'Logic',

    # Applied
    'Statistics', 'Probability theory', 'Optimization',
    'Game theory', 'Graph theory', 'Combinatorics',
    'Cryptography', 'Numerical analysis',

    # Geometry
    'Euclidean geometry', 'Differential geometry', 'Algebraic geometry',
]

# Economics & Finance topics
ECON_FINANCE_TOPICS = [
    # Economics
    'Microeconomics', 'Macroeconomics', 'Econometrics',
    'Game theory', 'Behavioral economics', 'Public economics',
    'International trade', 'Economic growth', 'Labor economics',
    'Industrial organization', 'Development economics',

    # Finance
    'Corporate finance', 'Investment banking', 'Portfolio theory',
    'Options pricing', 'Risk management', 'Asset pricing',
    'Financial markets', 'Derivatives', 'Fixed income',
    'Monetary policy', 'Central banking',
]

# Art & Literature topics
ART_LIT_TOPICS = [
    # Literature
    'William Shakespeare', 'Charles Dickens', 'Jane Austen',
    'Leo Tolstoy', 'Fyodor Dostoevsky', 'James Joyce',
    'Virginia Woolf', 'Franz Kafka', 'Gabriel García Márquez',
    'Romanticism', 'Modernism', 'Postmodernism',

    # Art
    'Renaissance art', 'Baroque', 'Impressionism',
    'Cubism', 'Surrealism', 'Abstract expressionism',
    'Leonardo da Vinci', 'Michelangelo', 'Vincent van Gogh',
    'Pablo Picasso', 'Claude Monet', 'Salvador Dalí',
]

# Languages & Linguistics topics
LING_TOPICS = [
    # Linguistics
    'Linguistics', 'Phonetics', 'Phonology', 'Morphology',
    'Syntax', 'Semantics', 'Pragmatics', 'Sociolinguistics',
    'Psycholinguistics', 'Historical linguistics',
    'Language acquisition', 'Computational linguistics',

    # Languages
    'Spanish language', 'French language', 'German language',
    'Italian language', 'Russian language', 'Chinese language',
    'Japanese language', 'Arabic language', 'Hindi',
    'Latin', 'Ancient Greek', 'Sanskrit',
]

# arXiv categories for these domains
ARXIV_CATEGORIES = {
    'math': ['math.CO', 'math.NT', 'math.AG'],  # Combinatorics, Number Theory, Algebraic Geometry
    'econ': ['econ.EM', 'econ.TH', 'q-fin.EC'],  # Econometrics, Theory, Economics
}

class FinalDomainsScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Educational Research Bot 1.0'
        })

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

    def scrape_arxiv(self, category, max_results=50):
        """Search arXiv"""
        base_url = 'http://export.arxiv.org/api/query'

        params = {
            'search_query': f'cat:{category}',
            'start': 0,
            'max_results': max_results,
            'sortBy': 'relevance',
            'sortOrder': 'descending'
        }

        try:
            response = self.session.get(base_url, params=params, timeout=30)
            response.raise_for_status()

            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)

            papers = []
            for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
                title_elem = entry.find('{http://www.w3.org/2005/Atom}title')
                summary_elem = entry.find('{http://www.w3.org/2005/Atom}summary')

                if title_elem is not None and summary_elem is not None:
                    papers.append({
                        'title': title_elem.text.strip(),
                        'abstract': summary_elem.text.strip()
                    })

            return papers
        except Exception as e:
            print(f"  ❌ arXiv Error: {e}")
            return []

    def scrape(self):
        """Scrape all 4 final domains"""
        print("="*70)
        print("FINAL 4 DOMAINS FOR WORLD-CLASS COVERAGE")
        print("="*70)
        print("Mathematics, Economics & Finance, Art & Literature, Linguistics")
        print("="*70)

        examples = []

        # Mathematics
        print("\n🔢 Mathematics Topics:")
        for i, topic in enumerate(MATH_TOPICS, 1):
            if i % 10 == 0:
                print(f"  [{i}/{len(MATH_TOPICS)}] Progress...")

            content = self.scrape_wikipedia_topic(topic)
            if content:
                examples.append({
                    'input': f"Explain {topic} in mathematics",
                    'output': content,
                    'source': 'wikipedia_math',
                    'category': 'mathematics',
                    'topic': topic
                })

            time.sleep(1)

        math_count = len(examples)
        print(f"  ✅ {math_count} math topics")

        # Economics & Finance
        print("\n💰 Economics & Finance Topics:")
        for i, topic in enumerate(ECON_FINANCE_TOPICS, 1):
            if i % 10 == 0:
                print(f"  [{i}/{len(ECON_FINANCE_TOPICS)}] Progress...")

            content = self.scrape_wikipedia_topic(topic)
            if content:
                examples.append({
                    'input': f"Explain {topic}",
                    'output': content,
                    'source': 'wikipedia_econ',
                    'category': 'economics_finance',
                    'topic': topic
                })

            time.sleep(1)

        econ_count = len(examples) - math_count
        print(f"  ✅ {econ_count} econ/finance topics")

        # Art & Literature
        print("\n🎨 Art & Literature Topics:")
        for i, topic in enumerate(ART_LIT_TOPICS, 1):
            if i % 10 == 0:
                print(f"  [{i}/{len(ART_LIT_TOPICS)}] Progress...")

            content = self.scrape_wikipedia_topic(topic)
            if content:
                examples.append({
                    'input': f"Tell me about {topic}",
                    'output': content,
                    'source': 'wikipedia_art',
                    'category': 'art_literature',
                    'topic': topic
                })

            time.sleep(1)

        art_count = len(examples) - math_count - econ_count
        print(f"  ✅ {art_count} art/literature topics")

        # Languages & Linguistics
        print("\n🗣️ Languages & Linguistics Topics:")
        for i, topic in enumerate(LING_TOPICS, 1):
            if i % 10 == 0:
                print(f"  [{i}/{len(LING_TOPICS)}] Progress...")

            content = self.scrape_wikipedia_topic(topic)
            if content:
                examples.append({
                    'input': f"Explain {topic}",
                    'output': content,
                    'source': 'wikipedia_linguistics',
                    'category': 'linguistics',
                    'topic': topic
                })

            time.sleep(1)

        ling_count = len(examples) - math_count - econ_count - art_count
        print(f"  ✅ {ling_count} linguistics topics")

        # arXiv papers
        print("\n📄 arXiv Math & Economics Papers:")

        # Math papers
        for category in ARXIV_CATEGORIES['math']:
            print(f"  Category: {category}")
            papers = self.scrape_arxiv(category, 50)

            for paper in papers:
                examples.append({
                    'input': f"Math research: {paper['title']}",
                    'output': paper['abstract'][:2000],
                    'source': 'arxiv_math',
                    'category': 'mathematics_research',
                    'arxiv_category': category
                })

            print(f"    ✅ {len(papers)} papers")
            time.sleep(3)

        # Econ papers
        for category in ARXIV_CATEGORIES['econ']:
            print(f"  Category: {category}")
            papers = self.scrape_arxiv(category, 50)

            for paper in papers:
                examples.append({
                    'input': f"Economics research: {paper['title']}",
                    'output': paper['abstract'][:2000],
                    'source': 'arxiv_econ',
                    'category': 'economics_research',
                    'arxiv_category': category
                })

            print(f"    ✅ {len(papers)} papers")
            time.sleep(3)

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'final_4_domains_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n{'='*70}")
            print(f"✅ COMPLETE! Scraped {len(examples)} examples")
            print(f"   Math: {math_count}, Econ: {econ_count}")
            print(f"   Art/Lit: {art_count}, Linguistics: {ling_count}")
            print(f"   Papers: {len(examples) - math_count - econ_count - art_count - ling_count}")
            print(f"💾 Saved to {data_file.name}")
            print(f"{'='*70}")

        return len(examples)

def main():
    scraper = FinalDomainsScraper()
    scraper.scrape()

if __name__ == '__main__':
    main()
