#!/usr/bin/env python3
"""
QUORA-STYLE Q&A SCRAPER
Since Quora blocks scraping, we'll generate similar Q&A using free APIs
Based on common question patterns from multiple sources
"""

import json
import time
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / 'shared'))
from multi_provider_generator import ProxyGenerator

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Question topics (Quora-style)
QUESTION_TOPICS = [
    # Career/Education
    "How do I become a software engineer?",
    "What skills should I learn for data science?",
    "How can I improve my programming skills?",
    "What's the best way to learn machine learning?",
    "How do I prepare for technical interviews?",

    # Technology
    "What is the difference between AI and machine learning?",
    "How does blockchain technology work?",
    "What is cloud computing in simple terms?",
    "How do neural networks learn?",
    "What is the future of quantum computing?",

    # Science
    "How does CRISPR gene editing work?",
    "What causes climate change?",
    "How do vaccines work?",
    "What is dark matter?",
    "How does the brain store memories?",

    # General Knowledge
    "What are the benefits of meditation?",
    "How can I be more productive?",
    "What is the best way to learn a new language?",
    "How does compound interest work?",
    "What makes a good leader?",

    # Health
    "What is a healthy diet?",
    "How can I improve my sleep quality?",
    "What are the benefits of exercise?",
    "How does stress affect the body?",
    "What is mindfulness?",
]

class QuoraStyleScraper:
    def __init__(self):
        self.generator = ProxyGenerator()

    def generate_answer(self, question):
        """Generate a comprehensive answer using free proxy"""
        prompt = f"""Answer this question comprehensively and helpfully:

Question: {question}

Provide a detailed, informative answer (2-3 paragraphs) as if you're an expert on Quora."""

        try:
            answer = self.generator.generate(prompt, max_tokens=400)
            return answer
        except Exception as e:
            print(f"  ⚠️  Generation error: {e}")
            return None

    def scrape_questions(self, max_questions=25):
        """Generate Q&A pairs"""
        print("="*70)
        print("QUORA-STYLE Q&A GENERATION")
        print("="*70)
        print(f"Questions to answer: {min(len(QUESTION_TOPICS), max_questions)}")
        print("Using free proxy API")
        print("="*70)

        examples = []

        for i, question in enumerate(QUESTION_TOPICS[:max_questions], 1):
            print(f"\n[{i}/{min(len(QUESTION_TOPICS), max_questions)}] {question}")

            answer = self.generate_answer(question)
            if not answer:
                continue

            example = {
                'input': question,
                'output': answer,
                'source': 'quora_style_qa',
                'category': 'question_answer',
                'generated': True
            }
            examples.append(example)

            print(f"  ✅ Generated answer ({len(answer)} chars)")

            # Rate limiting
            time.sleep(1)

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'quora_qa_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n{'='*70}")
            print(f"✅ COMPLETE! Generated {len(examples)} Q&A pairs")
            print(f"💾 Saved to {data_file.name}")
            print(f"{'='*70}")

        return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-questions', type=int, default=25, help='Max questions to answer')

    args = parser.parse_args()

    scraper = QuoraStyleScraper()
    scraper.scrape_questions(args.max_questions)

if __name__ == '__main__':
    main()
