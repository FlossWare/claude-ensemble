#!/usr/bin/env python3
"""
Web Content Scraper for LLM Training
Scrapes high-quality technical content from the web
"""

import json
import requests
import time
from bs4 import BeautifulSoup
from datetime import datetime
import os

OUTPUT_DIR = os.path.expanduser('~/.claude/ml-training/synthetic-data')

class WebContentScraper:
    """Scrape technical content from the web"""

    def __init__(self):
        self.cloudflare_url = f"https://api.cloudflare.com/client/v4/accounts/{os.getenv('PERSONAL_CLOUDFLARE_ACCOUNT_ID', '')}/ai/run/@cf/meta/llama-3.3-70b-instruct-fp8-fast"
        self.cloudflare_key = os.getenv('PERSONAL_CLOUDFLARE_API_KEY', '')

    def scrape_github_readme(self, repo_url: str) -> str:
        """Scrape README from GitHub repo"""
        try:
            # Convert github.com URL to raw content
            if 'github.com' in repo_url:
                parts = repo_url.split('/')
                user = parts[3]
                repo = parts[4]
                raw_url = f'https://raw.githubusercontent.com/{user}/{repo}/main/README.md'

                response = requests.get(raw_url, timeout=10)
                if response.status_code == 200:
                    return response.text

                # Try master branch
                raw_url = f'https://raw.githubusercontent.com/{user}/{repo}/master/README.md'
                response = requests.get(raw_url, timeout=10)
                if response.status_code == 200:
                    return response.text
        except:
            pass
        return None

    def scrape_documentation(self, url: str) -> str:
        """Scrape technical documentation"""
        try:
            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Educational AI Training Bot)'
            })

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Remove scripts, styles
                for script in soup(['script', 'style', 'nav', 'footer']):
                    script.decompose()

                # Get main content
                main = soup.find('main') or soup.find('article') or soup.find('body')
                if main:
                    text = main.get_text(separator='\n', strip=True)
                    # Clean up
                    lines = [l.strip() for l in text.split('\n') if l.strip()]
                    return '\n'.join(lines)
        except:
            pass
        return None

    def generate_with_cloudflare(self, prompt: str) -> str:
        """Generate completion using Cloudflare"""
        headers = {
            'Authorization': f'Bearer {self.cloudflare_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': 512
        }

        try:
            response = requests.post(self.cloudflare_url, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                return response.json()['result']['response']
        except:
            pass
        return None

    def create_training_examples_from_web(self, sources: list, output_file: str):
        """
        Create training examples from web sources

        sources = [
            {'type': 'github', 'url': 'https://github.com/user/repo'},
            {'type': 'docs', 'url': 'https://kubernetes.io/docs/...'},
        ]
        """

        print(f"\n🌐 WEB SCRAPING FOR TRAINING DATA")
        print(f"{'='*70}")
        print(f"Sources: {len(sources)}")
        print(f"Output: {output_file}")
        print(f"{'='*70}\n")

        dataset = []

        for i, source in enumerate(sources):
            print(f"  [{i+1}/{len(sources)}] Scraping {source['url'][:50]}...")

            # Scrape content
            if source['type'] == 'github':
                content = self.scrape_github_readme(source['url'])
            elif source['type'] == 'docs':
                content = self.scrape_documentation(source['url'])
            else:
                content = None

            if not content or len(content) < 200:
                print(f"    ⚠ Skipped (no content)")
                continue

            # Create training examples from content
            # Strategy: Take chunks and ask for explanations
            chunks = self.chunk_content(content, chunk_size=800)

            for chunk in chunks[:3]:  # Max 3 examples per source
                prompt = f"Explain this technical content in simple terms:\n\n{chunk}"

                completion = self.generate_with_cloudflare(prompt)

                if completion:
                    dataset.append({
                        'prompt': prompt,
                        'completion': completion,
                        'source': source['url'],
                        'type': source['type'],
                        'timestamp': datetime.utcnow().isoformat()
                    })

            print(f"    ✓ Generated {len([d for d in dataset if d['source'] == source['url']])} examples")
            time.sleep(1)  # Rate limit

        # Save
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(output_file, 'w') as f:
            for ex in dataset:
                f.write(json.dumps(ex) + '\n')

        print(f"\n✅ Generated {len(dataset)} examples from {len(sources)} web sources")
        print(f"📁 Saved to: {output_file}")

        return output_file

    def chunk_content(self, text: str, chunk_size: int = 800):
        """Split content into chunks"""
        words = text.split()
        chunks = []

        for i in range(0, len(words), chunk_size//5):  # Overlap
            chunk = ' '.join(words[i:i+chunk_size//5])
            if len(chunk) > 200:
                chunks.append(chunk)

        return chunks[:10]  # Max 10 chunks


# Popular technical sources (all public/open)
TRAINING_SOURCES = [
    # Kubernetes docs
    {'type': 'docs', 'url': 'https://kubernetes.io/docs/concepts/overview/'},
    {'type': 'docs', 'url': 'https://kubernetes.io/docs/concepts/workloads/pods/'},

    # Python docs
    {'type': 'docs', 'url': 'https://docs.python.org/3/tutorial/'},

    # Popular GitHub repos (README only - public)
    {'type': 'github', 'url': 'https://github.com/kubernetes/kubernetes'},
    {'type': 'github', 'url': 'https://github.com/apache/kafka'},
    {'type': 'github', 'url': 'https://github.com/postgres/postgres'},

    # Add more as needed...
]


if __name__ == '__main__':
    import sys

    scraper = WebContentScraper()

    # Use default sources or custom
    sources = TRAINING_SOURCES
    output = os.path.join(OUTPUT_DIR, f'web_training_{len(sources)}.jsonl')

    scraper.create_training_examples_from_web(sources, output)

    print("\n📚 Next: Combine with PDF dataset for training!")
    print(f"  cat {output} ~/.claude/ml-training/synthetic-data/quick_test_50.jsonl > combined_dataset.jsonl")
