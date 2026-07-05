#!/usr/bin/env python3
"""
W3C SCRAPER
Scrapes W3C specifications (HTML, CSS, XML, Web APIs)
Uses publicly available spec documents
"""

import json
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-w3c'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Important W3C specifications
W3C_SPECS = [
    ('https://www.w3.org/TR/html52/', 'HTML 5.2 Specification'),
    ('https://www.w3.org/TR/CSS/', 'CSS Specifications Overview'),
    ('https://www.w3.org/TR/SVG2/', 'SVG 2 Specification'),
    ('https://www.w3.org/TR/xml/', 'XML Specification'),
    ('https://www.w3.org/TR/dom/', 'DOM Standard'),
    ('https://www.w3.org/TR/webrtc/', 'WebRTC Specification'),
    ('https://www.w3.org/TR/websockets/', 'WebSockets API'),
    ('https://www.w3.org/TR/service-workers/', 'Service Workers'),
    ('https://www.w3.org/TR/wasm-core-1/', 'WebAssembly'),
    ('https://www.w3.org/TR/web-animations-1/', 'Web Animations'),
]

class W3CScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Educational Research Bot 1.0'
        })

    def scrape_spec(self, url, title):
        """Scrape a W3C specification"""
        try:
            response = self.session.get(url, timeout=20)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Find main content (W3C specs use <main> or <body>)
            main = soup.find('main') or soup.find('body')
            if not main:
                return None

            # Remove scripts, styles, navigation
            for tag in main(['script', 'style', 'nav', 'header', 'footer']):
                tag.decompose()

            # Get abstract/intro section
            abstract = main.find(id='abstract') or main.find(class_='abstract')
            intro = main.find(id='introduction') or main.find(class_='introduction')

            text = ""
            if abstract:
                text += abstract.get_text(separator='\n', strip=True) + "\n\n"
            if intro:
                text += intro.get_text(separator='\n', strip=True)

            if not text:
                # Fallback: get first 3000 chars of main content
                text = main.get_text(separator='\n', strip=True)[:3000]

            return text[:3000]

        except Exception as e:
            print(f"  ❌ Error: {e}")
            return None

    def scrape(self, max_specs=10):
        """Scrape W3C specifications"""
        print("="*70)
        print("W3C SCRAPER - WEB STANDARDS")
        print("="*70)
        print(f"Specs: {min(len(W3C_SPECS), max_specs)}")
        print("="*70)

        examples = []

        for i, (url, title) in enumerate(W3C_SPECS[:max_specs], 1):
            print(f"\n[{i}/{min(len(W3C_SPECS), max_specs)}] {title}")

            content = self.scrape_spec(url, title)
            if not content:
                continue

            example = {
                'input': f"What is the {title}?",
                'output': content,
                'source': 'w3c',
                'category': 'web_standards',
                'spec': title
            }
            examples.append(example)

            print(f"  ✅ Scraped {len(content)} chars")

            time.sleep(2)  # Be polite

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'w3c_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n{'='*70}")
            print(f"✅ COMPLETE! Scraped {len(examples)} W3C specs")
            print(f"💾 Saved to {data_file.name}")
            print(f"{'='*70}")

        return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-specs', type=int, default=10, help='Max specs to scrape')

    args = parser.parse_args()

    scraper = W3CScraper()
    scraper.scrape(args.max_specs)

if __name__ == '__main__':
    main()
