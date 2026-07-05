#!/usr/bin/env python3
"""
MDN WEB DOCS SCRAPER
Scrapes web development documentation from MDN
Uses web scraping (no API, but allowed for educational purposes)
"""

import json
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
RAW_DIR = NAS_BASE / 'raw-mdn'
RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Key MDN topics
MDN_TOPICS = [
    # JavaScript
    ('JavaScript/Reference/Global_Objects/Array', 'JavaScript Array methods'),
    ('JavaScript/Reference/Global_Objects/Promise', 'JavaScript Promises'),
    ('JavaScript/Reference/Statements/async_function', 'Async/Await'),
    ('JavaScript/Guide/Modules', 'JavaScript Modules'),
    ('JavaScript/Reference/Operators/Destructuring_assignment', 'Destructuring'),

    # Web APIs
    ('Web/API/Fetch_API', 'Fetch API'),
    ('Web/API/Web_Storage_API', 'Web Storage'),
    ('Web/API/WebSockets_API', 'WebSockets'),
    ('Web/API/Service_Worker_API', 'Service Workers'),

    # CSS
    ('Web/CSS/CSS_Flexbox', 'CSS Flexbox'),
    ('Web/CSS/CSS_Grid_Layout', 'CSS Grid'),
    ('Web/CSS/CSS_Animations', 'CSS Animations'),

    # HTML
    ('Web/HTML/Element/form', 'HTML Forms'),
    ('Web/HTML/Element/canvas', 'HTML Canvas'),
    ('Web/Accessibility', 'Web Accessibility'),
]

class MDNScraper:
    def __init__(self):
        self.base_url = 'https://developer.mozilla.org/en-US/docs'
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Educational Research Bot 1.0'
        })

    def scrape_page(self, path, title):
        """Scrape a single MDN page"""
        url = f'{self.base_url}/{path}'

        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Find main content
            article = soup.find('article')
            if not article:
                return None

            # Extract text (remove script/style)
            for script in article(['script', 'style']):
                script.decompose()

            text = article.get_text(separator='\n', strip=True)

            return text[:3000]  # First 3000 chars

        except Exception as e:
            print(f"  ❌ Error: {e}")
            return None

    def scrape(self, max_topics=15):
        """Scrape MDN topics"""
        print("="*70)
        print("MDN WEB DOCS SCRAPER - WEB DEVELOPMENT")
        print("="*70)
        print(f"Topics: {min(len(MDN_TOPICS), max_topics)}")
        print("="*70)

        examples = []

        for i, (path, title) in enumerate(MDN_TOPICS[:max_topics], 1):
            print(f"\n[{i}/{min(len(MDN_TOPICS), max_topics)}] {title}")

            content = self.scrape_page(path, title)
            if not content:
                continue

            example = {
                'input': f"Explain {title} in web development",
                'output': content,
                'source': 'mdn',
                'category': 'web_development',
                'topic': title
            }
            examples.append(example)

            print(f"  ✅ Scraped {len(content)} chars")

            time.sleep(2)  # Be polite

        # Save
        if examples:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = DATA_DIR / f'mdn_{timestamp}.jsonl'

            with open(data_file, 'w') as f:
                for ex in examples:
                    f.write(json.dumps(ex) + '\n')

            print(f"\n{'='*70}")
            print(f"✅ COMPLETE! Scraped {len(examples)} topics")
            print(f"💾 Saved to {data_file.name}")
            print(f"{'='*70}")

        return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-topics', type=int, default=15, help='Max topics to scrape')

    args = parser.parse_args()

    scraper = MDNScraper()
    scraper.scrape(args.max_topics)

if __name__ == '__main__':
    main()
