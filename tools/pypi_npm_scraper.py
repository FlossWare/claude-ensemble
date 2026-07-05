#!/usr/bin/env python3
"""
PYPI/NPM SCRAPER
Scrapes package documentation from PyPI and NPM registries
Uses FREE public APIs
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-packages'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Popular packages
PYPI_PACKAGES = [
    'numpy', 'pandas', 'scikit-learn', 'tensorflow', 'pytorch',
    'django', 'flask', 'fastapi', 'requests', 'sqlalchemy',
    'pytest', 'black', 'mypy', 'matplotlib', 'scipy',
]

NPM_PACKAGES = [
    'react', 'vue', 'express', 'axios', 'lodash',
    'webpack', 'babel', 'typescript', 'prettier', 'eslint',
    'jest', 'mocha', 'next', 'nuxt', 'vite',
]

class PackageScraper:
    def __init__(self):
        pass

    def get_pypi_package(self, package_name):
        """Get PyPI package info"""
        url = f'https://pypi.org/pypi/{package_name}/json'

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            info = data.get('info', {})
            return {
                'name': package_name,
                'description': info.get('summary', ''),
                'long_description': info.get('description', '')[:3000],
                'version': info.get('version', ''),
            }
        except:
            return None

    def get_npm_package(self, package_name):
        """Get NPM package info"""
        url = f'https://registry.npmjs.org/{package_name}'

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            latest = data.get('dist-tags', {}).get('latest', '')
            readme = data.get('readme', '')

            return {
                'name': package_name,
                'description': data.get('description', ''),
                'readme': readme[:3000],
                'version': latest,
            }
        except:
            return None

    def scrape(self, max_pypi=15, max_npm=15):
        """Scrape package documentation"""
        print("="*70)
        print("PYPI/NPM SCRAPER - PACKAGE DOCUMENTATION")
        print("="*70)
        print(f"PyPI packages: {max_pypi}")
        print(f"NPM packages: {max_npm}")
        print("="*70)

        examples = []

        # PyPI
        print("\n📦 PyPI Packages:")
        for i, pkg in enumerate(PYPI_PACKAGES[:max_pypi], 1):
            print(f"  [{i}/{max_pypi}] {pkg}")

            info = self.get_pypi_package(pkg)
            if not info or not info.get('long_description'):
                continue

            example = {
                'input': f"What is the Python {pkg} package?",
                'output': info['long_description'],
                'source': 'pypi',
                'category': 'package_docs',
                'package': pkg,
                'version': info['version']
            }
            examples.append(example)

            time.sleep(0.5)

        # NPM
        print("\n📦 NPM Packages:")
        for i, pkg in enumerate(NPM_PACKAGES[:max_npm], 1):
            print(f"  [{i}/{max_npm}] {pkg}")

            info = self.get_npm_package(pkg)
            if not info or not info.get('readme'):
                continue

            example = {
                'input': f"What is the npm {pkg} package?",
                'output': info['readme'],
                'source': 'npm',
                'category': 'package_docs',
                'package': pkg,
                'version': info['version']
            }
            examples.append(example)

            time.sleep(0.5)

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'packages_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n{'='*70}")
            print(f"✅ COMPLETE! Scraped {len(examples)} packages")
            print(f"💾 Saved to {data_file.name}")
            print(f"{'='*70}")

        return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-pypi', type=int, default=15, help='Max PyPI packages')
    parser.add_argument('--max-npm', type=int, default=15, help='Max NPM packages')

    args = parser.parse_args()

    scraper = PackageScraper()
    scraper.scrape(args.max_pypi, args.max_npm)

if __name__ == '__main__':
    main()
