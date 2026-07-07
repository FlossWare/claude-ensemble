#!/usr/bin/env python3
"""
GitHub Code Scraper for LLM Training
Scrapes actual source code, docs, issues, and PRs from top projects
"""

import os
import json
import requests
import time
from datetime import datetime
import base64

OUTPUT_DIR = os.path.expanduser('~/.claude/ml-training/synthetic-data')
CLOUDFLARE_URL = f"https://api.cloudflare.com/client/v4/accounts/{os.getenv('CLOUDFLARE_ACCOUNT_ID', '')}/ai/run/@cf/meta/llama-3.3-70b-instruct-fp8-fast"
CLOUDFLARE_KEY = os.getenv('CLOUDFLARE_API_KEY', '')

# GitHub Personal Access Token (optional - for higher rate limits)
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', None)

class GitHubCodeScraper:
    """Scrape GitHub repositories for training data"""

    def __init__(self):
        self.headers = {
            'Accept': 'application/vnd.github.v3+json'
        }
        if GITHUB_TOKEN:
            self.headers['Authorization'] = f'token {GITHUB_TOKEN}'

    def generate_completion(self, prompt):
        """Generate with Cloudflare"""
        try:
            r = requests.post(
                CLOUDFLARE_URL,
                headers={'Authorization': f'Bearer {CLOUDFLARE_KEY}', 'Content-Type': 'application/json'},
                json={'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 512},
                timeout=30
            )
            if r.status_code == 200:
                return r.json()['result']['response']
        except Exception as e:
            print(f"    Error generating: {e}")
        return None

    def get_repo_tree(self, owner, repo):
        """Get repository file tree"""
        url = f'https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1'

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.json().get('tree', [])
            elif response.status_code == 404:
                # Try 'master' branch
                url = f'https://api.github.com/repos/{owner}/{repo}/git/trees/master?recursive=1'
                response = requests.get(url, headers=self.headers, timeout=10)
                if response.status_code == 200:
                    return response.json().get('tree', [])
        except Exception as e:
            print(f"    Error getting tree: {e}")

        return []

    def get_file_content(self, owner, repo, path):
        """Get file content"""
        url = f'https://api.github.com/repos/{owner}/{repo}/contents/{path}'

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('encoding') == 'base64':
                    content = base64.b64decode(data['content']).decode('utf-8')
                    return content
        except Exception as e:
            pass

        return None

    def scrape_source_files(self, owner, repo, extensions=['.py', '.js', '.go', '.rs', '.java'], max_files=10):
        """
        Scrape source code files from repository

        Creates training examples like:
        - "Explain this Python function..."
        - "What does this code do?"
        - "Refactor this code..."
        """
        print(f"\n📂 Scraping source code: {owner}/{repo}")

        tree = self.get_repo_tree(owner, repo)
        dataset = []

        # Filter for source files
        source_files = [
            f for f in tree
            if f['type'] == 'blob' and any(f['path'].endswith(ext) for ext in extensions)
        ]

        print(f"  Found {len(source_files)} source files, selecting {min(max_files, len(source_files))}")

        for i, file in enumerate(source_files[:max_files]):
            path = file['path']
            print(f"  [{i+1}/{min(max_files, len(source_files))}] {path}")

            content = self.get_file_content(owner, repo, path)

            if content and len(content) < 2000:  # Skip huge files
                # Strategy 1: Explain the code
                prompt1 = f"""Explain what this code does:

Repository: {owner}/{repo}
File: {path}

```
{content[:1000]}
```

Provide a concise explanation:"""

                completion1 = self.generate_completion(prompt1)
                if completion1:
                    dataset.append({
                        'prompt': prompt1,
                        'completion': completion1,
                        'source': 'GitHub Code',
                        'repo': f'{owner}/{repo}',
                        'file': path,
                        'type': 'code_explanation'
                    })

                time.sleep(1)  # Rate limit

        return dataset

    def scrape_readme(self, owner, repo):
        """Scrape README file"""
        print(f"\n📖 Scraping README: {owner}/{repo}")

        url = f'https://api.github.com/repos/{owner}/{repo}/readme'

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                content = base64.b64decode(data['content']).decode('utf-8')[:1500]

                prompt = f"""Explain this open-source project:

Repository: {owner}/{repo}

{content}

Provide a summary of what this project does and its key features:"""

                completion = self.generate_completion(prompt)
                if completion:
                    return [{
                        'prompt': prompt,
                        'completion': completion,
                        'source': 'GitHub README',
                        'repo': f'{owner}/{repo}',
                        'type': 'readme_explanation'
                    }]
        except Exception as e:
            print(f"  Error: {e}")

        return []

    def scrape_issues(self, owner, repo, max_issues=5):
        """
        Scrape top issues and their solutions

        Great for:
        - Problem-solving
        - Debugging
        - Common errors
        """
        print(f"\n🐛 Scraping issues: {owner}/{repo}")

        url = f'https://api.github.com/repos/{owner}/{repo}/issues'
        params = {
            'state': 'closed',  # Closed issues have solutions!
            'sort': 'comments',
            'direction': 'desc',
            'per_page': max_issues
        }

        dataset = []

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            if response.status_code == 200:
                issues = response.json()

                for i, issue in enumerate(issues[:max_issues]):
                    title = issue.get('title', '')
                    body = issue.get('body', '')[:500] if issue.get('body') else ''

                    print(f"  [{i+1}/{max_issues}] Issue #{issue['number']}: {title[:50]}...")

                    prompt = f"""This GitHub issue was reported and resolved:

Repository: {owner}/{repo}
Issue: {title}

Description:
{body}

What was the likely problem and how would you approach solving it?"""

                    completion = self.generate_completion(prompt)
                    if completion:
                        dataset.append({
                            'prompt': prompt,
                            'completion': completion,
                            'source': 'GitHub Issues',
                            'repo': f'{owner}/{repo}',
                            'issue_number': issue['number'],
                            'type': 'issue_solution'
                        })

                    time.sleep(1)
        except Exception as e:
            print(f"  Error: {e}")

        return dataset

    def scrape_repo_complete(self, owner, repo):
        """Scrape everything from a repository"""
        print(f"\n{'='*70}")
        print(f"🐙 SCRAPING REPOSITORY: {owner}/{repo}")
        print(f"{'='*70}")

        all_data = []

        # 1. README
        readme_data = self.scrape_readme(owner, repo)
        all_data.extend(readme_data)

        # 2. Source code
        code_data = self.scrape_source_files(owner, repo, max_files=5)
        all_data.extend(code_data)

        # 3. Issues
        issues_data = self.scrape_issues(owner, repo, max_issues=3)
        all_data.extend(issues_data)

        print(f"\n✅ Total examples from {owner}/{repo}: {len(all_data)}")

        return all_data

    def save_dataset(self, dataset, filename):
        """Save dataset to JSONL"""
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        filepath = os.path.join(OUTPUT_DIR, filename)

        with open(filepath, 'w') as f:
            for item in dataset:
                f.write(json.dumps(item) + '\n')

        print(f"\n✅ Saved {len(dataset)} examples to {filepath}")
        return filepath


# TOP REPOSITORIES TO SCRAPE
TOP_REPOS = [
    # Systems & Infrastructure
    ('kubernetes', 'kubernetes'),          # Container orchestration
    ('docker', 'moby'),                    # Containerization
    ('hashicorp', 'terraform'),            # Infrastructure as code

    # Machine Learning
    ('pytorch', 'pytorch'),                # Deep learning
    ('tensorflow', 'tensorflow'),          # ML framework
    ('huggingface', 'transformers'),       # NLP models

    # Web Frameworks
    ('facebook', 'react'),                 # UI framework
    ('vuejs', 'vue'),                      # Progressive framework
    ('django', 'django'),                  # Python web framework

    # Languages
    ('golang', 'go'),                      # Go language
    ('rust-lang', 'rust'),                 # Rust language
    ('python', 'cpython'),                 # Python interpreter

    # Databases
    ('postgres', 'postgres'),              # PostgreSQL
    ('redis', 'redis'),                    # In-memory DB

    # Tools
    ('git', 'git'),                        # Version control
    ('microsoft', 'vscode'),               # Code editor
]


if __name__ == '__main__':
    import sys

    scraper = GitHubCodeScraper()

    if len(sys.argv) > 1:
        # Scrape specific repo
        owner_repo = sys.argv[1]
        if '/' in owner_repo:
            owner, repo = owner_repo.split('/')
            all_data = scraper.scrape_repo_complete(owner, repo)
        else:
            print("Usage: python3 github_code_scraper.py owner/repo")
            sys.exit(1)
    else:
        # Scrape all top repos
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("🐙 ULTIMATE GITHUB CODE SCRAPER")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"\nScraping {len(TOP_REPOS)} top repositories...")
        print()

        all_data = []

        for owner, repo in TOP_REPOS:
            try:
                data = scraper.scrape_repo_complete(owner, repo)
                all_data.extend(data)

                # Save incremental progress
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                scraper.save_dataset(all_data, f'github_code_{len(all_data)}_{timestamp}.jsonl')

                time.sleep(2)  # Be nice to GitHub API

            except Exception as e:
                print(f"\n❌ Error on {owner}/{repo}: {e}")
                continue

        print("\n" + "="*70)
        print(f"🎉 COMPLETE! Total examples: {len(all_data)}")
        print("="*70)
