#!/usr/bin/env python3
"""
DATABASE & LANGUAGES CODE SCRAPER
Scrapes source code and documentation from:
- PostgreSQL (database source code)
- MariaDB (database source code)
- Object Pascal / Free Pascal / Lazarus
- C++ projects and documentation
"""

import json
import os
import subprocess
from pathlib import Path
from datetime import datetime
import time
import requests

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-db-languages'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Source code repositories
CODE_REPOS = [
    {
        'name': 'PostgreSQL',
        'url': 'https://github.com/postgres/postgres.git',
        'depth': 1,
        'key_dirs': ['src/backend', 'src/include', 'src/bin', 'doc/src/sgml'],
        'description': 'PostgreSQL database source code',
        'max_files': 300
    },
    {
        'name': 'MariaDB',
        'url': 'https://github.com/MariaDB/server.git',
        'depth': 1,
        'key_dirs': ['sql', 'storage', 'include', 'client'],
        'description': 'MariaDB database source code',
        'max_files': 300
    },
    {
        'name': 'Free-Pascal-Compiler',
        'url': 'https://gitlab.com/freepascal.org/fpc/source.git',
        'depth': 1,
        'key_dirs': ['rtl', 'packages', 'compiler'],
        'description': 'Free Pascal Compiler source',
        'max_files': 200
    },
    {
        'name': 'Lazarus-IDE',
        'url': 'https://gitlab.com/freepascal.org/lazarus/lazarus.git',
        'depth': 1,
        'key_dirs': ['lcl', 'components', 'ide'],
        'description': 'Lazarus IDE for Object Pascal',
        'max_files': 200
    },
    {
        'name': 'LLVM',
        'url': 'https://github.com/llvm/llvm-project.git',
        'depth': 1,
        'key_dirs': ['clang/lib', 'clang/include', 'llvm/lib'],
        'description': 'LLVM Compiler Infrastructure (C++ heavy)',
        'max_files': 300
    },
    {
        'name': 'Boost',
        'url': 'https://github.com/boostorg/boost.git',
        'depth': 1,
        'key_dirs': ['libs/algorithm', 'libs/asio', 'libs/filesystem', 'libs/thread'],
        'description': 'Boost C++ Libraries',
        'max_files': 200
    },
]

# File extensions to extract
SOURCE_EXTENSIONS = {
    '.c', '.h', '.cpp', '.hpp', '.cc', '.hh', '.cxx',  # C/C++
    '.pas', '.pp', '.inc',  # Pascal
    '.sql',                  # SQL
    '.sgml', '.xml',         # Documentation
    '.md', '.txt', '.rst',   # Markdown/text docs
    '.py', '.pl', '.sh',     # Scripts
}

class DatabaseLanguagesScraper:
    def __init__(self):
        self.clone_dir = RAW_DIR / 'repos'
        self.clone_dir.mkdir(exist_ok=True)
        self.session = requests.Session()

    def clone_repo(self, repo_info):
        """Clone a repository (shallow)"""
        repo_name = repo_info['name']
        repo_url = repo_info['url']
        depth = repo_info.get('depth', 1)

        repo_path = self.clone_dir / repo_name

        print(f"\n{'='*70}")
        print(f"CLONING: {repo_name}")
        print(f"URL: {repo_url}")
        print(f"{'='*70}")

        # Remove if exists
        if repo_path.exists():
            print(f"  Removing existing clone...")
            subprocess.run(['rm', '-rf', str(repo_path)], check=True)

        # Clone (shallow)
        print(f"  Cloning (depth={depth})...")
        try:
            subprocess.run([
                'git', 'clone',
                '--depth', str(depth),
                '--single-branch',
                repo_url,
                str(repo_path)
            ], check=True, capture_output=True, timeout=900)  # 15 min timeout
            print(f"  ✅ Clone complete!")
            return repo_path
        except subprocess.TimeoutExpired:
            print(f"  ⚠️  Clone timeout (15min)")
            return None
        except subprocess.CalledProcessError as e:
            print(f"  ❌ Clone failed: {e}")
            return None

    def extract_source_files(self, repo_path, key_dirs, max_files=200):
        """Extract source code from key directories"""
        files = []

        for key_dir in key_dirs:
            dir_path = repo_path / key_dir
            if not dir_path.exists():
                continue

            # Find source files
            for ext in SOURCE_EXTENSIONS:
                pattern = f"**/*{ext}"
                found = list(dir_path.glob(pattern))[:max_files // len(key_dirs)]
                files.extend(found)

        return files[:max_files]

    def create_training_examples(self, repo_info, files):
        """Create training examples from source files"""
        examples = []

        for file_path in files:
            try:
                # Read file
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                # Skip if too small or too large
                if len(content) < 50 or len(content) > 50000:
                    continue

                # Get relative path
                if file_path.is_relative_to(self.clone_dir):
                    rel_path = file_path.relative_to(self.clone_dir)
                else:
                    rel_path = file_path.name

                # Determine category
                if repo_info['name'] in ['PostgreSQL', 'MariaDB']:
                    category = 'database_source'
                elif 'Pascal' in repo_info['name'] or 'Lazarus' in repo_info['name']:
                    category = 'object_pascal'
                else:
                    category = 'cpp_source'

                # Create example
                example = {
                    'input': f"{repo_info['name']} source: {rel_path}",
                    'output': content[:5000],  # First 5000 chars
                    'source': 'db_lang_code',
                    'category': category,
                    'project': repo_info['name'],
                    'file_type': file_path.suffix,
                    'file_path': str(rel_path)
                }
                examples.append(example)

            except Exception as e:
                continue

        return examples

    def scrape_cpp_reference(self):
        """Scrape C++ reference documentation"""
        print(f"\n{'='*70}")
        print("C++ REFERENCE DOCUMENTATION")
        print(f"{'='*70}")

        cpp_topics = [
            'Standard Template Library',
            'C++ algorithm header',
            'C++ vector',
            'C++ map',
            'C++ smart pointer',
            'C++ lambda',
            'C++ thread',
            'C++ mutex',
            'RAII',
            'Move semantics',
        ]

        examples = []

        for topic in cpp_topics:
            url = f'https://en.wikipedia.org/api/rest_v1/page/summary/{topic}'

            try:
                response = self.session.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    extract = data.get('extract', '')

                    if len(extract) > 100:
                        example = {
                            'input': f"Explain {topic} in C++",
                            'output': extract,
                            'source': 'wikipedia_cpp',
                            'category': 'cpp_concepts',
                            'topic': topic
                        }
                        examples.append(example)
                        print(f"  ✅ {topic}")
            except:
                print(f"  ⚠️  Failed: {topic}")

            time.sleep(1)

        return examples

    def scrape(self, max_repos=6):
        """Scrape database and language source code"""
        print("="*70)
        print("DATABASE & LANGUAGES CODE SCRAPER")
        print("="*70)
        print(f"Repositories: {min(len(CODE_REPOS), max_repos)}")
        print("PostgreSQL, MariaDB, Free Pascal, Lazarus, LLVM, Boost")
        print("="*70)

        all_examples = []

        # Clone repos
        for i, repo_info in enumerate(CODE_REPOS[:max_repos], 1):
            print(f"\n[{i}/{min(len(CODE_REPOS), max_repos)}] {repo_info['name']}")

            # Clone repo
            repo_path = self.clone_repo(repo_info)
            if not repo_path:
                continue

            # Extract source files
            print(f"\n  📁 Extracting source files...")
            max_files = repo_info.get('max_files', 200)
            files = self.extract_source_files(repo_path, repo_info['key_dirs'], max_files)
            print(f"  ✅ Found {len(files)} source files")

            # Create training examples
            print(f"  📝 Creating training examples...")
            examples = self.create_training_examples(repo_info, files)
            print(f"  ✅ Created {len(examples)} examples")

            all_examples.extend(examples)
            time.sleep(2)

        # C++ reference docs
        cpp_docs = self.scrape_cpp_reference()
        print(f"\n  ✅ Created {len(cpp_docs)} C++ concept examples")
        all_examples.extend(cpp_docs)

        # Save
        if all_examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'db_languages_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in all_examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n{'='*70}")
            print(f"✅ COMPLETE! Scraped {len(all_examples)} code/docs examples")
            print(f"💾 Saved to {data_file.name}")
            print(f"{'='*70}")

        return len(all_examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-repos', type=int, default=6, help='Max repositories')

    args = parser.parse_args()

    scraper = DatabaseLanguagesScraper()
    scraper.scrape(args.max_repos)

if __name__ == '__main__':
    main()
