#!/usr/bin/env python3
"""
BEAST MODE: ML FRAMEWORKS
TensorFlow, PyTorch, scikit-learn, NumPy, Pandas
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime
import time

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-ml-frameworks'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

REPOS = [
    {'name': 'TensorFlow', 'url': 'https://github.com/tensorflow/tensorflow.git', 'key_dirs': ['tensorflow/python', 'tensorflow/core'], 'max': 400},
    {'name': 'PyTorch', 'url': 'https://github.com/pytorch/pytorch.git', 'key_dirs': ['torch', 'aten/src'], 'max': 400},
    {'name': 'scikit-learn', 'url': 'https://github.com/scikit-learn/scikit-learn.git', 'key_dirs': ['sklearn'], 'max': 300},
    {'name': 'NumPy', 'url': 'https://github.com/numpy/numpy.git', 'key_dirs': ['numpy'], 'max': 300},
    {'name': 'Pandas', 'url': 'https://github.com/pandas-dev/pandas.git', 'key_dirs': ['pandas/core'], 'max': 300},
]

SOURCE_EXTS = {'.py', '.cpp', '.c', '.h', '.hpp', '.cu', '.cuh'}

class MLFrameworksScraper:
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
                                'source': 'ml_frameworks',
                                'category': 'machine_learning',
                                'framework': repo['name']
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
            (DATA_DIR / f'ml_frameworks_{timestamp}.jsonl').write_text(
                '\n'.join(json.dumps(ex) for ex in all_examples)
            )
            print(f"\n✅ SAVED {len(all_examples)} examples!")

        return len(all_examples)

if __name__ == '__main__':
    MLFrameworksScraper().scrape()
