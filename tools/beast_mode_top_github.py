#!/usr/bin/env python3
"""
BEAST MODE: TOP 200 GITHUB REPOS
Gets READMEs + key files from top starred repos
"""

import json
import requests
import time
from pathlib import Path
from datetime import datetime
import os

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

class TopGitHubScraper:
    def __init__(self):
        self.token = os.getenv('PERSONAL_GITHUB_TOKEN')
        self.session = requests.Session()
        if self.token:
            self.session.headers['Authorization'] = f'token {self.token}'

    def get_trending_repos(self, language=None, limit=200):
        """Get top repos by stars"""
        repos = []

        # Top repos overall
        for page in range(1, 5):  # 4 pages = ~200 repos
            url = 'https://api.github.com/search/repositories'
            params = {
                'q': 'stars:>50000',
                'sort': 'stars',
                'order': 'desc',
                'per_page': 50,
                'page': page
            }

            try:
                resp = self.session.get(url, params=params, timeout=10)
                if resp.status_code == 200:
                    repos.extend(resp.json().get('items', []))
                time.sleep(2)
            except:
                pass

        return repos[:limit]

    def get_readme(self, repo_full_name):
        """Get README"""
        url = f'https://api.github.com/repos/{repo_full_name}/readme'

        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                import base64
                content = base64.b64decode(resp.json()['content']).decode('utf-8')
                return content
        except:
            pass
        return None

    def scrape(self):
        print("="*70)
        print("TOP 200 GITHUB REPOS")
        print("="*70)

        repos = self.get_trending_repos(limit=200)
        print(f"✅ Found {len(repos)} top repos")

        examples = []

        for i, repo in enumerate(repos, 1):
            if i % 20 == 0:
                print(f"  [{i}/{len(repos)}] Progress...")

            readme = self.get_readme(repo['full_name'])
            if readme:
                examples.append({
                    'input': f"GitHub project: {repo['name']}",
                    'output': readme[:5000],
                    'source': 'top_github',
                    'category': 'real_world_code',
                    'repo': repo['full_name'],
                    'stars': repo['stargazers_count']
                })

            time.sleep(0.5)

        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            (DATA_DIR / f'top_github_{timestamp}.jsonl').write_text(
                '\n'.join(json.dumps(ex) for ex in examples)
            )
            print(f"\n✅ SAVED {len(examples)} examples!")

        return len(examples)

if __name__ == '__main__':
    TopGitHubScraper().scrape()
