#!/usr/bin/env python3
"""
BEAST MODE: BLOCKCHAIN + CLOUD
Bitcoin, Ethereum, Docker, Kubernetes, Redis, MongoDB, SQLite, GCC
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime
import time

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-blockchain-cloud'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

REPOS = [
    # Blockchain
    {'name': 'Bitcoin', 'url': 'https://github.com/bitcoin/bitcoin.git', 'key_dirs': ['src'], 'max': 300},
    {'name': 'Ethereum-go', 'url': 'https://github.com/ethereum/go-ethereum.git', 'key_dirs': ['core', 'eth'], 'max': 300},

    # Cloud/Container
    {'name': 'Docker', 'url': 'https://github.com/moby/moby.git', 'key_dirs': ['daemon', 'container'], 'max': 300},
    {'name': 'Kubernetes', 'url': 'https://github.com/kubernetes/kubernetes.git', 'key_dirs': ['pkg'], 'max': 400},

    # Databases
    {'name': 'Redis', 'url': 'https://github.com/redis/redis.git', 'key_dirs': ['src'], 'max': 300},
    {'name': 'MongoDB', 'url': 'https://github.com/mongodb/mongo.git', 'key_dirs': ['src/mongo'], 'max': 300},
    {'name': 'SQLite', 'url': 'https://github.com/sqlite/sqlite.git', 'key_dirs': ['src'], 'max': 200},

    # Compiler
    {'name': 'GCC', 'url': 'https://github.com/gcc-mirror/gcc.git', 'key_dirs': ['gcc'], 'max': 400},
]

SOURCE_EXTS = {'.c', '.h', '.cpp', '.hpp', '.go', '.rs', '.cc', '.hh'}

class BlockchainCloudScraper:
    def __init__(self):
        self.clone_dir = RAW_DIR / 'repos'
        self.clone_dir.mkdir(exist_ok=True)

    def clone_and_extract(self, repo):
        repo_path = self.clone_dir / repo['name']

        print(f"\n{'='*70}")
        print(f"CLONING: {repo['name']}")
        print(f"{'='*70}")

        if repo_path.exists():
            subprocess.run(['rm', '-rf', str(repo_path)], check=True)

        try:
            subprocess.run(['git', 'clone', '--depth', '1', repo['url'], str(repo_path)],
                         check=True, capture_output=True, timeout=900)
            print(f"  ✅ Cloned!")
        except:
            print(f"  ❌ Failed")
            return []

        examples = []
        for key_dir in repo['key_dirs']:
            dir_path = repo_path / key_dir
            if not dir_path.exists():
                continue

            for ext in SOURCE_EXTS:
                files = list(dir_path.glob(f"**/*{ext}"))[:repo['max'] // len(repo['key_dirs'])]

                for f in files:
                    try:
                        content = f.read_text(encoding='utf-8', errors='ignore')
                        if 100 < len(content) < 50000:
                            examples.append({
                                'input': f"{repo['name']} source: {f.name}",
                                'output': content[:5000],
                                'source': 'blockchain_cloud',
                                'category': 'infrastructure',
                                'project': repo['name']
                            })
                    except:
                        pass

        print(f"  ✅ Extracted {len(examples)} examples")
        return examples

    def scrape(self):
        from concurrent.futures import ThreadPoolExecutor, as_completed

        all_examples = []

        print(f"\n🚀 Using 6 parallel workers for maximum speed!")

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {executor.submit(self.clone_and_extract, repo): repo for repo in REPOS}

            for future in as_completed(futures):
                repo = futures[future]
                try:
                    examples = future.result()
                    all_examples.extend(examples)
                    print(f"  ✅ {repo['name']}: {len(examples)} examples")
                except Exception as e:
                    print(f"  ❌ {repo['name']}: {e}")

        if all_examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            (DATA_DIR / f'blockchain_cloud_{timestamp}.jsonl').write_text(
                '\n'.join(json.dumps(ex) for ex in all_examples)
            )
            print(f"\n✅ SAVED {len(all_examples)} examples!")

        return len(all_examples)

if __name__ == '__main__':
    BlockchainCloudScraper().scrape()
