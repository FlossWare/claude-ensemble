#!/usr/bin/env python3
"""
WIKIPEDIA SCRAPER - General Knowledge
Scrapes diverse Wikipedia articles for general knowledge training
"""

import json
import time
import random
import requests
from pathlib import Path
from datetime import datetime
import sys

# Add shared directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'shared'))
from multi_provider_generator import MultiProviderGenerator

# NAS storage
NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-wikipedia'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Diverse Wikipedia topics for general knowledge
TOPIC_CATEGORIES = {
    'history': [
        'World War II', 'Ancient Rome', 'Renaissance', 'Industrial Revolution',
        'Cold War', 'Ancient Egypt', 'Medieval Europe', 'Age of Exploration',
        'American Revolution', 'French Revolution', 'Victorian era', 'Bronze Age',
        'Mongol Empire', 'Byzantine Empire', 'Ottoman Empire', 'Han Dynasty',
        'Aztec civilization', 'Inca Empire', 'Ancient Greece', 'Mesopotamia'
    ],
    'geography': [
        'Amazon rainforest', 'Sahara Desert', 'Mount Everest', 'Great Barrier Reef',
        'Antarctica', 'Pacific Ocean', 'Himalayas', 'Grand Canyon',
        'Niagara Falls', 'Great Lakes', 'Mediterranean Sea', 'Rocky Mountains',
        'Andes', 'Alps', 'Yellowstone National Park', 'Death Valley',
        'Victoria Falls', 'Lake Baikal', 'Gobi Desert', 'Mariana Trench'
    ],
    'culture': [
        'Jazz', 'Hip hop', 'Classical music', 'Rock music', 'Opera',
        'Ballet', 'Cinema', 'Photography', 'Sculpture', 'Painting',
        'Literature', 'Poetry', 'Theater', 'Dance', 'Architecture',
        'Fashion', 'Cuisine', 'Philosophy', 'Religion', 'Mythology'
    ],
    'science': [
        'Evolution', 'Climate change', 'Photosynthesis', 'DNA', 'Plate tectonics',
        'Big Bang', 'Black hole', 'Quantum mechanics', 'Relativity', 'Atoms',
        'Periodic table', 'Gravity', 'Electricity', 'Magnetism', 'Thermodynamics',
        'Optics', 'Nuclear energy', 'Renewable energy', 'Ecology', 'Biodiversity'
    ],
    'people': [
        'Albert Einstein', 'Marie Curie', 'Leonardo da Vinci', 'Isaac Newton',
        'Charles Darwin', 'Nikola Tesla', 'Stephen Hawking', 'Galileo Galilei',
        'William Shakespeare', 'Ludwig van Beethoven', 'Pablo Picasso', 'Vincent van Gogh',
        'Nelson Mandela', 'Mahatma Gandhi', 'Martin Luther King Jr.', 'Abraham Lincoln',
        'Winston Churchill', 'Napoleon Bonaparte', 'Julius Caesar', 'Cleopatra'
    ],
    'current': [
        'Internet', 'Artificial intelligence', 'Social media', 'Smartphone',
        'Electric vehicle', 'Space exploration', 'Cryptocurrency', 'Global warming',
        'Pandemic', 'Renewable energy', '5G', 'Biotechnology', 'Nanotechnology',
        'Virtual reality', 'Robotics', 'Drones', 'Self-driving car', 'Gene therapy',
        'Quantum computing', 'Internet of Things'
    ],
    'everyday': [
        'Coffee', 'Cooking', 'Gardening', 'Fitness', 'Nutrition',
        'Sleep', 'Stress management', 'Time management', 'Personal finance', 'Investing',
        'Real estate', 'Education', 'Parenting', 'Marriage', 'Friendship',
        'Communication', 'Leadership', 'Teamwork', 'Creativity', 'Productivity'
    ]
}

class WikipediaScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Educational Research Bot 1.0 (sfloess@redhat.com)'
        })
        self.generator = MultiProviderGenerator()

    def get_article(self, title):
        """Fetch Wikipedia article content"""
        url = 'https://en.wikipedia.org/w/api.php'
        params = {
            'action': 'query',
            'format': 'json',
            'titles': title,
            'prop': 'extracts',
            'explaintext': True,
            'exsectionformat': 'plain'
        }

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            pages = data.get('query', {}).get('pages', {})
            if not pages:
                return None

            page = list(pages.values())[0]
            if 'extract' not in page:
                return None

            return {
                'title': page.get('title'),
                'extract': page.get('extract'),
                'url': f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
            }

        except Exception as e:
            print(f"Error fetching {title}: {e}")
            return None

    def generate_training_examples(self, article):
        """Generate 3 training examples from article"""
        title = article['title']
        extract = article['extract'][:5000]  # First 5000 chars

        examples = []

        # Example 1: Summary
        prompt1 = f"Summarize this Wikipedia article about {title} in 2-3 paragraphs:\n\n{extract}"
        response1 = self.generator.generate(prompt1, max_tokens=300)
        if response1:
            examples.append({
                'input': f"Summarize the Wikipedia article about {title}",
                'output': response1,
                'source': 'wikipedia',
                'category': 'summary',
                'topic': title
            })

        # Example 2: Key facts
        prompt2 = f"What are the 5 most important facts from this article about {title}?\n\n{extract}"
        response2 = self.generator.generate(prompt2, max_tokens=300)
        if response2:
            examples.append({
                'input': f"What are key facts about {title}?",
                'output': response2,
                'source': 'wikipedia',
                'category': 'facts',
                'topic': title
            })

        # Example 3: Explanation
        prompt3 = f"Explain {title} to someone who has never heard of it before:\n\n{extract}"
        response3 = self.generator.generate(prompt3, max_tokens=300)
        if response3:
            examples.append({
                'input': f"Explain {title} in simple terms",
                'output': response3,
                'source': 'wikipedia',
                'category': 'explanation',
                'topic': title
            })

        return examples

    def scrape_category(self, category, topics, max_per_category=20):
        """Scrape all topics in a category"""
        print(f"\n{'='*70}")
        print(f"CATEGORY: {category.upper()}")
        print(f"Topics: {len(topics)}")
        print(f"{'='*70}\n")

        total_examples = 0

        for i, topic in enumerate(topics[:max_per_category], 1):
            print(f"[{i}/{min(len(topics), max_per_category)}] Fetching: {topic}")

            # Fetch article
            article = self.get_article(topic)
            if not article:
                print(f"  ❌ Failed to fetch article")
                continue

            # Save raw article
            raw_file = RAW_DIR / f"{category}_{topic.replace(' ', '_')}.json"
            with open(raw_file, 'w') as f:
                json.dump(article, f, indent=2)
            print(f"  ✅ Saved raw: {raw_file.name}")

            # Generate training examples
            print(f"  🤖 Generating training examples...")
            examples = self.generate_training_examples(article)

            if examples:
                # Save training examples
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                data_file = DATA_DIR / f'wikipedia_{category}_{timestamp}_{i}.jsonl'

                with open(data_file, 'w') as f:
                    for ex in examples:
                        f.write(json.dumps(ex) + '\n')

                total_examples += len(examples)
                print(f"  ✅ Generated {len(examples)} examples")
                print(f"  💾 Total examples: {total_examples}")

            # Rate limiting
            time.sleep(random.uniform(1.0, 2.0))

        return total_examples

def main():
    """Main scraping function"""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--category', type=str, help='Specific category to scrape')
    parser.add_argument('--max-per-category', type=int, default=20, help='Max topics per category')

    args = parser.parse_args()

    scraper = WikipediaScraper()

    print("="*70)
    print("WIKIPEDIA SCRAPER - GENERAL KNOWLEDGE")
    print("="*70)
    print(f"Categories: {len(TOPIC_CATEGORIES)}")
    print(f"Total topics: {sum(len(v) for v in TOPIC_CATEGORIES.values())}")
    print(f"Max per category: {args.max_per_category}")
    print(f"Target examples: {len(TOPIC_CATEGORIES) * args.max_per_category * 3}")
    print("="*70)

    total_examples = 0

    if args.category:
        # Scrape specific category
        if args.category in TOPIC_CATEGORIES:
            examples = scraper.scrape_category(
                args.category,
                TOPIC_CATEGORIES[args.category],
                args.max_per_category
            )
            total_examples += examples
        else:
            print(f"❌ Unknown category: {args.category}")
            print(f"Available: {list(TOPIC_CATEGORIES.keys())}")
            return
    else:
        # Scrape all categories
        for category, topics in TOPIC_CATEGORIES.items():
            examples = scraper.scrape_category(category, topics, args.max_per_category)
            total_examples += examples
            print(f"\n✅ {category}: {examples} examples generated\n")

    print("\n" + "="*70)
    print(f"✅ WIKIPEDIA SCRAPING COMPLETE!")
    print(f"Total examples: {total_examples}")
    print(f"Data directory: {DATA_DIR}")
    print("="*70)

if __name__ == '__main__':
    main()
