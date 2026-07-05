#!/usr/bin/env python3
"""
OPERATING SYSTEM CODE & DOCS SCRAPER
Scrapes source code and documentation from major OS projects
- Fedora (RPM specs, documentation)
- Debian (package sources, docs)
- FreeBSD (system source, docs)
- Tiny Core Linux (extensions, docs)
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
RAW_DIR = NAS_BASE / 'raw-os-code'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# OS Repositories
OS_REPOS = [
    {
        'name': 'FreeBSD-src',
        'url': 'https://github.com/freebsd/freebsd-src.git',
        'depth': 1,
        'key_dirs': ['sys/kern', 'sys/net', 'bin', 'sbin', 'usr.bin', 'usr.sbin'],
        'description': 'FreeBSD operating system source code',
        'max_files': 300
    },
    {
        'name': 'Debian-installer',
        'url': 'https://salsa.debian.org/installer-team/debian-installer.git',
        'depth': 1,
        'key_dirs': ['doc', 'scripts'],
        'description': 'Debian installer',
        'max_files': 100
    },
    {
        'name': 'TinyCore-Extensions',
        'url': 'https://github.com/tinycorelinux/tinycorelinux.git',
        'depth': 1,
        'key_dirs': ['.'],
        'description': 'Tiny Core Linux',
        'max_files': 50
    },
]

# Fedora package specs to download
FEDORA_PACKAGES = [
    'kernel', 'systemd', 'glibc', 'bash', 'coreutils',
    'util-linux', 'openssh', 'vim', 'nginx', 'httpd',
    'postgresql', 'mysql', 'docker', 'podman', 'kubernetes',
]

# File extensions to extract
SOURCE_EXTENSIONS = {
    '.c', '.h',      # C source/headers
    '.sh',           # Shell scripts
    '.py',           # Python
    '.pl',           # Perl
    '.rb',           # Ruby
    '.mk',           # Makefiles
    '.spec',         # RPM specs
    '.conf',         # Config files
    '.md', '.txt',   # Documentation
}

class OSCodeDocsScraper:
    def __init__(self):
        self.clone_dir = RAW_DIR / 'repos'
        self.clone_dir.mkdir(exist_ok=True)
        self.session = requests.Session()

    def clone_repo(self, repo_info):
        """Clone an OS repository (shallow)"""
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
            ], check=True, capture_output=True, timeout=600)
            print(f"  ✅ Clone complete!")
            return repo_path
        except subprocess.TimeoutExpired:
            print(f"  ⚠️  Clone timeout (10min)")
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

    def scrape_fedora_spec(self, package_name):
        """Download Fedora RPM spec file"""
        # Fedora dist-git URL
        url = f'https://src.fedoraproject.org/rpms/{package_name}/raw/rawhide/f/{package_name}.spec'

        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return response.text
            else:
                return None
        except Exception as e:
            return None

    def create_training_examples(self, source_name, files):
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

                # Create example
                example = {
                    'input': f"{source_name} source: {rel_path}",
                    'output': content[:5000],  # First 5000 chars
                    'source': 'os_code',
                    'category': 'operating_system',
                    'os': source_name,
                    'file_type': file_path.suffix,
                    'file_path': str(rel_path)
                }
                examples.append(example)

            except Exception as e:
                continue

        return examples

    def scrape(self, max_repos=3, scrape_fedora=True):
        """Scrape OS source code and docs"""
        print("="*70)
        print("OPERATING SYSTEM CODE & DOCS SCRAPER")
        print("="*70)
        print(f"Repositories: {min(len(OS_REPOS), max_repos)}")
        print(f"Fedora packages: {len(FEDORA_PACKAGES) if scrape_fedora else 0}")
        print("="*70)

        all_examples = []

        # Clone OS repos
        for i, repo_info in enumerate(OS_REPOS[:max_repos], 1):
            print(f"\n[{i}/{min(len(OS_REPOS), max_repos)}] {repo_info['name']}")

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
            examples = self.create_training_examples(repo_info['name'], files)
            print(f"  ✅ Created {len(examples)} examples")

            all_examples.extend(examples)
            time.sleep(2)

        # Scrape Fedora RPM specs
        if scrape_fedora:
            print(f"\n{'='*70}")
            print("FEDORA RPM SPECS")
            print(f"{'='*70}")

            fedora_examples = []

            for i, package in enumerate(FEDORA_PACKAGES, 1):
                print(f"  [{i}/{len(FEDORA_PACKAGES)}] {package}")

                spec_content = self.scrape_fedora_spec(package)
                if spec_content:
                    example = {
                        'input': f"Fedora RPM spec for {package}",
                        'output': spec_content[:5000],
                        'source': 'fedora_spec',
                        'category': 'operating_system',
                        'os': 'Fedora',
                        'package': package
                    }
                    fedora_examples.append(example)
                    print(f"    ✅ Downloaded spec ({len(spec_content)} chars)")
                else:
                    print(f"    ⚠️  Spec not found")

                time.sleep(1)

            print(f"\n  ✅ Created {len(fedora_examples)} Fedora spec examples")
            all_examples.extend(fedora_examples)

        # Save
        if all_examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'os_code_docs_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in all_examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n{'='*70}")
            print(f"✅ COMPLETE! Scraped {len(all_examples)} OS code/docs examples")
            print(f"💾 Saved to {data_file.name}")
            print(f"{'='*70}")

        return len(all_examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-repos', type=int, default=3, help='Max repositories')
    parser.add_argument('--skip-fedora', action='store_true', help='Skip Fedora specs')

    args = parser.parse_args()

    scraper = OSCodeDocsScraper()
    scraper.scrape(args.max_repos, not args.skip_fedora)

if __name__ == '__main__':
    main()
