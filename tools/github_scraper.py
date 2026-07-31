#!/usr/bin/env python3
"""
GITHUB SCRAPER
Scrapes popular GitHub repos (READMEs, docs, code examples)
Uses GitHub API (5,000 requests/hour authenticated, 60 unauth)
"""

import json
import time
import requests
import base64
from pathlib import Path
from datetime import datetime
import os

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-github'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Popular repos to scrape
POPULAR_REPOS = [
    # AI/ML
    'tensorflow/tensorflow',
    'pytorch/pytorch',
    'openai/gpt-3',
    'huggingface/transformers',

    # Web
    'facebook/react',
    'vuejs/vue',
    'angular/angular',
    'nodejs/node',

    # Backend
    'django/django',
    'flask/flask',
    'rails/rails',
    'laravel/laravel',

    # DevOps
    'kubernetes/kubernetes',
    'docker/docker-ce',
    'ansible/ansible',
    'terraform/terraform',

    # Languages
    'rust-lang/rust',
    'golang/go',
    'python/cpython',
    'microsoft/TypeScript',
]

class GitHubScraper:
    def __init__(self):
        self.session = requests.Session()

        # Try to use auth token if available
        token = os.getenv('PERSONAL_GITHUB_TOKEN')
        if token:
            self.session.headers.update({
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github.v3+json'
            })
            print("  ✅ Using authenticated requests (5,000/hour)")
        else:
            print("  ⚠️  No PERSONAL_GITHUB_TOKEN - limited to 60/hour")

    def get_readme(self, repo):
        """Get README content"""
        url = f"https://api.github.com/repos/{repo}/readme"

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Decode base64 content
            content = base64.b64decode(data['content']).decode('utf-8')
            return content
        except Exception as e:
            print(f"  ❌ README error: {e}")
            return None

    def get_docs(self, repo):
        """Get documentation files"""
        url = f"https://api.github.com/repos/{repo}/contents/docs"

        docs = []
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                files = response.json()

                for file in files[:5]:  # Max 5 doc files
                    if file['type'] == 'file' and file['name'].endswith('.md'):
                        # Get file content
                        content_response = self.session.get(file['download_url'], timeout=10)
                        if content_response.status_code == 200:
                            docs.append({
                                'name': file['name'],
                                'content': content_response.text
                            })
        except:
            pass

        return docs

    def scrape_repo(self, repo):
        """Scrape a single repo"""
        owner, name = repo.split('/')
        print(f"\n[{repo}]")

        examples = []

        # Get README
        readme = self.get_readme(repo)
        if readme:
            print(f"  ✅ README ({len(readme)} chars)")

            # Create example from README
            examples.append({
                'input': f"What is {name}? (from GitHub README)",
                'output': readme[:2000],  # First 2000 chars
                'source': 'github',
                'category': 'documentation',
                'repo': repo,
                'file_type': 'README'
            })

        # Get docs
        docs = self.get_docs(repo)
        if docs:
            print(f"  ✅ {len(docs)} doc files")

            for doc in docs:
                examples.append({
                    'input': f"{name} documentation: {doc['name']}",
                    'output': doc['content'][:2000],
                    'source': 'github',
                    'category': 'documentation',
                    'repo': repo,
                    'file_type': doc['name']
                })

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_name = repo.replace('/', '_')
            data_file = DATA_DIR / f'github_{safe_name}_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"  💾 Saved {len(examples)} examples")

        return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-repos', type=int, default=20, help='Max repos to scrape')

    args = parser.parse_args()

    scraper = GitHubScraper()

    print("="*70)
    print("GITHUB SCRAPER - POPULAR REPOSITORIES")
    print("="*70)
    print(f"Repos to scrape: {len(POPULAR_REPOS)}")
    print(f"Max: {args.max_repos}")
    print("="*70)

    total = 0

    for repo in POPULAR_REPOS[:args.max_repos]:
        count = scraper.scrape_repo(repo)
        total += count
        time.sleep(2)  # Rate limiting

    print(f"\n{'='*70}")
    print(f"✅ COMPLETE! Scraped {min(len(POPULAR_REPOS), args.max_repos)} repos")
    print(f"Generated {total} documentation examples")
    print(f"{'='*70}")

if __name__ == '__main__':
    main()
