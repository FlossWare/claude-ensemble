#!/usr/bin/env python3
"""
CREATIVE WRITING SCRAPER
Generates creative writing examples for diverse model capabilities
"""

import json
import time
import random
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / 'shared'))
from multi_provider_generator import MultiProviderGenerator

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Creative writing prompts
CREATIVE_PROMPTS = {
    'stories': [
        "Write a short story about a dragon who's afraid of heights",
        "Write a mystery story set in a chocolate factory",
        "Write a sci-fi story about first contact with aliens",
        "Write a fantasy story about a wizard's cooking school",
        "Write a horror story about an AI that became too helpful",
        "Write an adventure story about exploring a sunken city",
        "Write a romance story between a time traveler and a historian",
        "Write a comedy story about a superhero with useless powers",
        "Write a thriller about a hacker who discovers too much",
        "Write a folk tale about why the moon changes shape",
    ],
    'dialogue': [
        "Write a conversation between a pessimist and an optimist about the weather",
        "Write a dialogue between a chef and a food critic",
        "Write a conversation between two AIs meeting for the first time",
        "Write a dialogue between a student and a professor about procrastination",
        "Write a conversation between a parent and child about bedtime",
        "Write a dialogue between a detective and a witness",
        "Write a conversation between best friends planning a surprise party",
        "Write a dialogue between a doctor and a patient about healthy eating",
        "Write a conversation between coworkers about a mysterious office smell",
        "Write a dialogue between a tour guide and confused tourists",
    ],
    'descriptions': [
        "Describe a bustling marketplace in ancient Rome",
        "Describe a futuristic city underwater",
        "Describe a cozy cabin during a snowstorm",
        "Describe a tropical beach at sunset",
        "Describe a haunted mansion on a hill",
        "Describe a space station orbiting Jupiter",
        "Describe a medieval castle during a feast",
        "Describe a secret garden hidden in a city",
        "Describe a desert oasis at night",
        "Describe a mountain monastery at dawn",
    ],
    'poetry': [
        "Write a haiku about coding late at night",
        "Write a limerick about a clumsy robot",
        "Write a sonnet about the internet",
        "Write free verse about morning coffee",
        "Write a poem about the seasons changing",
        "Write a humorous poem about household chores",
        "Write a poem about artificial intelligence",
        "Write a nature poem about autumn leaves",
        "Write a poem about childhood memories",
        "Write a poem about the ocean",
    ],
    'explanations': [
        "Explain quantum physics using a cooking metaphor",
        "Explain how democracy works to a 5-year-old",
        "Explain the internet using only medieval terminology",
        "Explain climate change through a story",
        "Explain machine learning using a garden analogy",
        "Explain economics using a lemonade stand example",
        "Explain evolution using cartoon characters",
        "Explain photosynthesis as an adventure story",
        "Explain gravity using everyday objects",
        "Explain DNA using a recipe book metaphor",
    ],
    'how_to': [
        "Write a guide on how to make friends as an adult",
        "Write instructions for being a good listener",
        "Write a guide on organizing your home",
        "Write instructions for staying motivated",
        "Write a guide on managing stress",
        "Write instructions for effective communication",
        "Write a guide on developing good habits",
        "Write instructions for conflict resolution",
        "Write a guide on time management",
        "Write instructions for building confidence",
    ]
}

class CreativeScraper:
    def __init__(self):
        self.generator = MultiProviderGenerator()

    def generate_creative_example(self, category, prompt):
        """Generate creative writing example"""
        response = self.generator.generate(prompt, max_tokens=500)

        if not response:
            return None

        return {
            'input': prompt,
            'output': response,
            'source': 'creative_generation',
            'category': category,
            'type': 'creative_writing'
        }

    def scrape_category(self, category, prompts):
        """Generate examples for a category"""
        print(f"\n{'='*70}")
        print(f"CATEGORY: {category.upper()}")
        print(f"Prompts: {len(prompts)}")
        print(f"{'='*70}\n")

        examples = []

        for i, prompt in enumerate(prompts, 1):
            print(f"[{i}/{len(prompts)}] Generating: {prompt[:50]}...")

            example = self.generate_creative_example(category, prompt)
            if example:
                examples.append(example)
                print(f"  ✅ Generated")
            else:
                print(f"  ❌ Failed")

            time.sleep(random.uniform(0.5, 1.0))

        # Save examples
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'creative_{category}_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n✅ Saved {len(examples)} examples to {data_file.name}")

        return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--category', type=str, help='Specific category')

    args = parser.parse_args()

    scraper = CreativeScraper()

    print("="*70)
    print("CREATIVE WRITING SCRAPER")
    print("="*70)
    print(f"Categories: {len(CREATIVE_PROMPTS)}")
    print(f"Total prompts: {sum(len(v) for v in CREATIVE_PROMPTS.values())}")
    print("="*70)

    total = 0

    if args.category:
        if args.category in CREATIVE_PROMPTS:
            count = scraper.scrape_category(args.category, CREATIVE_PROMPTS[args.category])
            total += count
        else:
            print(f"❌ Unknown category: {args.category}")
            return
    else:
        for category, prompts in CREATIVE_PROMPTS.items():
            count = scraper.scrape_category(category, prompts)
            total += count

    print(f"\n{'='*70}")
    print(f"✅ COMPLETE! Generated {total} creative examples")
    print(f"{'='*70}")

if __name__ == '__main__':
    main()
