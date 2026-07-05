#!/usr/bin/env python3
"""
CONSCIOUSNESS, NEUROSCIENCE & PSYCHOLOGY SCRAPER
Perfect complement to the consciousness systems in CLAUDE.md!
- Wikipedia topics on consciousness, neuroscience, psychology
- arXiv neuroscience papers
- PubMed neuroscience/psychology (via main PubMed scraper)
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-consciousness'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Consciousness, neuroscience & philosophy topics
CONSCIOUSNESS_TOPICS = [
    # Consciousness theories (matches CLAUDE.md systems!)
    'Consciousness', 'Global workspace theory', 'Integrated information theory',
    'Higher-order theories of consciousness', 'Recurrent processing theory',
    'Predictive processing', 'Free energy principle',
    'Attention schema theory', 'Sensorimotor theory',

    # Philosophy of mind
    'Philosophy of mind', 'Mind-body problem', 'Dualism', 'Physicalism',
    'Functionalism', 'Eliminative materialism', 'Property dualism',
    'Epiphenomenalism', 'Panpsychism', 'Neutral monism',

    # Epistemology & metaphysics
    'Epistemology', 'Metaphysics', 'Ontology', 'Free will',
    'Determinism', 'Compatibilism', 'Personal identity',
    'Theory of knowledge', 'Rationalism', 'Empiricism',

    # Ethics & logic
    'Ethics', 'Metaethics', 'Utilitarianism', 'Deontology',
    'Virtue ethics', 'Moral realism', 'Logic', 'Philosophy of logic',
    'Philosophy of language', 'Philosophy of science',

    # Neuroscience
    'Neuron', 'Synapse', 'Neurotransmitter', 'Brain', 'Cerebral cortex',
    'Hippocampus', 'Amygdala', 'Prefrontal cortex', 'Basal ganglia',
    'Cerebellum', 'Thalamus', 'Hypothalamus', 'Brainstem',
    'Neural network', 'Neuroplasticity', 'Long-term potentiation',
    'Working memory', 'Episodic memory', 'Semantic memory',

    # Psychology
    'Cognitive psychology', 'Attention', 'Perception', 'Memory',
    'Learning', 'Decision making', 'Problem solving', 'Creativity',
    'Emotion', 'Motivation', 'Language processing', 'Social cognition',
    'Metacognition', 'Executive functions', 'Cognitive biases',

    # Advanced topics
    'Neural correlates of consciousness', 'Qualia', 'Hard problem of consciousness',
    'Binding problem', 'Phenomenal consciousness', 'Access consciousness',
    'Autonoetic consciousness', 'Blindsight', 'Split-brain',
    'Artificial consciousness', 'Machine consciousness',
]

# arXiv neuroscience categories
ARXIV_NEURO_CATEGORIES = [
    'q-bio.NC',  # Neurons and Cognition
]

class ConsciousnessNeuroscienceScraper:
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

    def scrape_arxiv(self, category, max_results=150):
        """Search arXiv for neuroscience papers"""
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

    def scrape(self, max_wiki_topics=50, max_arxiv=150):
        """Scrape consciousness & neuroscience content"""
        print("="*70)
        print("CONSCIOUSNESS, NEUROSCIENCE & PSYCHOLOGY SCRAPER")
        print("="*70)
        print(f"Wikipedia topics: {min(len(CONSCIOUSNESS_TOPICS), max_wiki_topics)}")
        print(f"arXiv papers: {max_arxiv}")
        print("Complements your CLAUDE.md consciousness systems!")
        print("="*70)

        examples = []

        # Wikipedia
        print("\n🧠 Wikipedia Topics:")
        for i, topic in enumerate(CONSCIOUSNESS_TOPICS[:max_wiki_topics], 1):
            if i % 10 == 0:
                print(f"  [{i}/{min(len(CONSCIOUSNESS_TOPICS), max_wiki_topics)}] Progress...")

            content = self.scrape_wikipedia_topic(topic)
            if not content:
                continue

            example = {
                'input': f"Explain {topic}",
                'output': content,
                'source': 'wikipedia_consciousness',
                'category': 'consciousness_neuroscience',
                'topic': topic
            }
            examples.append(example)

            time.sleep(1)

        print(f"  ✅ Scraped {len(examples)} topics")

        # arXiv
        print("\n📄 arXiv Neuroscience Papers:")
        papers = self.scrape_arxiv('q-bio.NC', max_arxiv)
        print(f"  ✅ {len(papers)} papers")

        for paper in papers:
            example = {
                'input': f"Research paper: {paper['title']}",
                'output': paper['abstract'][:2000],
                'source': 'arxiv_neuroscience',
                'category': 'neuroscience_research'
            }
            examples.append(example)

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'consciousness_neuroscience_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n{'='*70}")
            print(f"✅ COMPLETE! Scraped {len(examples)} examples")
            print(f"💾 Saved to {data_file.name}")
            print(f"{'='*70}")

        return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-wiki-topics', type=int, default=50, help='Max Wikipedia topics')
    parser.add_argument('--max-arxiv', type=int, default=150, help='Max arXiv papers')

    args = parser.parse_args()

    scraper = ConsciousnessNeuroscienceScraper()
    scraper.scrape(args.max_wiki_topics, args.max_arxiv)

if __name__ == '__main__':
    main()
