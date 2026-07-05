#!/usr/bin/env python3
"""
FIRMWARE SOURCE CODE SCRAPER
Scrapes actual source code from router firmware projects
- OpenWrt (GitHub)
- DD-WRT (source if available)
- Tomato (GitHub - various forks)
- FreshTomato (active fork)
- Advanced Tomato
- Asuswrt-Merlin (popular for ASUS routers)

Extracts C code, shell scripts, makefiles, config files
"""

import json
import os
import subprocess
from pathlib import Path
from datetime import datetime
import time

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-firmware-code'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Firmware repositories
FIRMWARE_REPOS = [
    {
        'name': 'OpenWrt',
        'url': 'https://github.com/openwrt/openwrt.git',
        'depth': 1,  # Shallow clone
        'key_dirs': ['package/network', 'package/kernel', 'target/linux', 'package/base-files'],
        'description': 'OpenWrt Linux distribution for embedded devices'
    },
    {
        'name': 'FreshTomato',
        'url': 'https://github.com/Freshtomato/freshtomato-mips.git',
        'depth': 1,
        'key_dirs': ['release/src/router', 'release/src/linux'],
        'description': 'FreshTomato firmware for routers'
    },
    {
        'name': 'Asuswrt-Merlin',
        'url': 'https://github.com/RMerl/asuswrt-merlin.ng.git',
        'depth': 1,
        'key_dirs': ['release/src/router', 'release/src-rt'],
        'description': 'Enhanced firmware for ASUS routers'
    },
    {
        'name': 'Tomato-ARM',
        'url': 'https://github.com/Jackysi/advancedtomato-arm.git',
        'depth': 1,
        'key_dirs': ['release/src/router', 'release/src-rt'],
        'description': 'AdvancedTomato ARM firmware'
    },
]

# File extensions to extract
SOURCE_EXTENSIONS = {
    '.c', '.h',      # C source/headers
    '.sh',           # Shell scripts
    '.mk',           # Makefiles
    '.conf',         # Config files
    '.py',           # Python scripts
    '.lua',          # Lua scripts
    '.pl',           # Perl scripts
}

class FirmwareCodeScraper:
    def __init__(self):
        self.clone_dir = RAW_DIR / 'repos'
        self.clone_dir.mkdir(exist_ok=True)

    def clone_repo(self, repo_info):
        """Clone a firmware repository (shallow)"""
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

    def create_training_examples(self, repo_info, files):
        """Create training examples from source files"""
        examples = []

        for file_path in files:
            try:
                # Read file
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                # Skip if too small or too large
                if len(content) < 100 or len(content) > 50000:
                    continue

                # Get relative path
                rel_path = file_path.relative_to(self.clone_dir)

                # Create example
                example = {
                    'input': f"{repo_info['name']} source code: {rel_path}",
                    'output': content[:5000],  # First 5000 chars
                    'source': 'firmware_code',
                    'category': 'router_firmware',
                    'firmware': repo_info['name'],
                    'file_type': file_path.suffix,
                    'file_path': str(rel_path)
                }
                examples.append(example)

            except Exception as e:
                continue

        return examples

    def scrape(self, max_repos=4, max_files_per_repo=200):
        """Scrape firmware source code"""
        print("="*70)
        print("FIRMWARE SOURCE CODE SCRAPER")
        print("="*70)
        print(f"Repositories: {min(len(FIRMWARE_REPOS), max_repos)}")
        print(f"Max files per repo: {max_files_per_repo}")
        print("="*70)

        all_examples = []

        for i, repo_info in enumerate(FIRMWARE_REPOS[:max_repos], 1):
            print(f"\n[{i}/{min(len(FIRMWARE_REPOS), max_repos)}] {repo_info['name']}")

            # Clone repo
            repo_path = self.clone_repo(repo_info)
            if not repo_path:
                continue

            # Extract source files
            print(f"\n  📁 Extracting source files from key directories...")
            files = self.extract_source_files(repo_path, repo_info['key_dirs'], max_files_per_repo)
            print(f"  ✅ Found {len(files)} source files")

            # Create training examples
            print(f"  📝 Creating training examples...")
            examples = self.create_training_examples(repo_info, files)
            print(f"  ✅ Created {len(examples)} examples")

            all_examples.extend(examples)

            # Clean up clone to save space (optional - comment out to keep)
            # print(f"  🗑️  Cleaning up clone...")
            # subprocess.run(['rm', '-rf', str(repo_path)], check=True)

            time.sleep(2)

        # Save
        if all_examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'firmware_code_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in all_examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n{'='*70}")
            print(f"✅ COMPLETE! Scraped {len(all_examples)} code examples")
            print(f"💾 Saved to {data_file.name}")
            print(f"{'='*70}")

        return len(all_examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-repos', type=int, default=4, help='Max repositories')
    parser.add_argument('--max-files-per-repo', type=int, default=200, help='Max files per repo')

    args = parser.parse_args()

    scraper = FirmwareCodeScraper()
    scraper.scrape(args.max_repos, args.max_files_per_repo)

if __name__ == '__main__':
    main()
