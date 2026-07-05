#!/usr/bin/env python3
"""
STACK OVERFLOW SCRAPER
Scrapes Q&A pairs - PERFECT training format, minimal API calls needed!
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-stackoverflow'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Stack Exchange API (no auth needed for basic queries!)
API_BASE = 'https://api.stackexchange.com/2.3'

# Popular tags to scrape
TAGS = [
    # Programming languages
    'python', 'javascript', 'java', 'c++', 'c#', 'go', 'rust', 'typescript',
    'php', 'ruby', 'swift', 'kotlin', 'scala', 'r', 'matlab',

    # Web development
    'html', 'css', 'react', 'vue.js', 'angular', 'node.js', 'django', 'flask',

    # Data/ML
    'machine-learning', 'deep-learning', 'tensorflow', 'pytorch', 'pandas',
    'numpy', 'scikit-learn', 'data-science',

    # DevOps/Infrastructure
    'docker', 'kubernetes', 'aws', 'linux', 'git', 'bash', 'postgresql',
    'mysql', 'mongodb', 'redis',

    # Other
    'algorithm', 'data-structures', 'security', 'testing', 'api'
]

class StackOverflowScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Educational Research Bot 1.0'
        })

    def get_questions(self, tag, page=1, pagesize=100):
        """Fetch questions for a tag"""
        url = f"{API_BASE}/questions"
        params = {
            'page': page,
            'pagesize': pagesize,
            'order': 'desc',
            'sort': 'votes',  # Get highest quality questions
            'tagged': tag,
            'site': 'stackoverflow',
            'filter': 'withbody'  # Include question body
        }

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Check quota
            if 'quota_remaining' in data:
                print(f"  API quota remaining: {data['quota_remaining']}")

            return data.get('items', [])

        except Exception as e:
            print(f"  ❌ Error fetching questions: {e}")
            return []

    def get_answers(self, question_id):
        """Fetch answers for a question"""
        url = f"{API_BASE}/questions/{question_id}/answers"
        params = {
            'order': 'desc',
            'sort': 'votes',  # Get best answer
            'site': 'stackoverflow',
            'filter': 'withbody',
            'pagesize': 1  # Just get top answer
        }

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get('items', [])
        except Exception as e:
            print(f"  ❌ Error fetching answers: {e}")
            return []

    def scrape_tag(self, tag, max_questions=50):
        """Scrape Q&A pairs for a tag"""
        print(f"\n{'='*70}")
        print(f"TAG: {tag.upper()}")
        print(f"{'='*70}\n")

        questions = self.get_questions(tag, pagesize=max_questions)
        print(f"Fetched {len(questions)} questions")

        examples = []

        for i, q in enumerate(questions[:max_questions], 1):
            print(f"[{i}/{len(questions)}] Processing Q#{q['question_id']}...")

            # Get answers
            answers = self.get_answers(q['question_id'])

            if not answers:
                print(f"  ⚠️  No answers found")
                continue

            # Create training example (NO API CALL NEEDED!)
            example = {
                'input': q['title'],  # Question title
                'output': answers[0].get('body', ''),  # Top answer
                'source': 'stackoverflow',
                'category': tag,
                'question_id': q['question_id'],
                'score': q.get('score', 0),
                'answer_score': answers[0].get('score', 0)
            }

            examples.append(example)
            print(f"  ✅ Added (Q score: {q.get('score', 0)}, A score: {answers[0].get('score', 0)})")

            # Rate limiting - Stack Exchange allows 30 requests/second
            time.sleep(0.1)

        # Save examples
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'stackoverflow_{tag}_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n✅ Saved {len(examples)} Q&A pairs to {data_file.name}")

        return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', type=str, help='Specific tag to scrape')
    parser.add_argument('--max-questions', type=int, default=50, help='Max questions per tag')

    args = parser.parse_args()

    scraper = StackOverflowScraper()

    print("="*70)
    print("STACK OVERFLOW SCRAPER - Q&A PAIRS")
    print("="*70)
    print(f"API: Stack Exchange (30 req/sec limit)")
    print(f"No summarization needed - Q&A already perfect format!")
    print("="*70)

    total = 0

    if args.tag:
        # Scrape specific tag
        count = scraper.scrape_tag(args.tag, args.max_questions)
        total += count
    else:
        # Scrape all tags
        print(f"\nScraping {len(TAGS)} tags...")
        for tag in TAGS:
            count = scraper.scrape_tag(tag, args.max_questions)
            total += count
            time.sleep(1)  # Be nice to API

    print(f"\n{'='*70}")
    print(f"✅ COMPLETE! Collected {total} Q&A pairs")
    print(f"{'='*70}")

if __name__ == '__main__':
    main()
