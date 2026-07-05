#!/usr/bin/env python3
"""
PROJECT GUTENBERG SCRAPER
Free books - literature, philosophy, history
Already in text format, minimal processing needed!
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Popular books on Project Gutenberg
BOOKS = [
    # Classic literature
    {'id': 1342, 'title': 'Pride and Prejudice', 'author': 'Jane Austen'},
    {'id': 84, 'title': 'Frankenstein', 'author': 'Mary Shelley'},
    {'id': 1661, 'title': 'Sherlock Holmes Adventures', 'author': 'Arthur Conan Doyle'},
    {'id': 98, 'title': 'A Tale of Two Cities', 'author': 'Charles Dickens'},
    {'id': 2701, 'title': 'Moby Dick', 'author': 'Herman Melville'},
    {'id': 1952, 'title': 'The Yellow Wallpaper', 'author': 'Charlotte Perkins Gilman'},

    # Philosophy
    {'id': 5200, 'title': 'Metamorphosis', 'author': 'Franz Kafka'},
    {'id': 1232, 'title': 'The Prince', 'author': 'Niccolò Machiavelli'},
    {'id': 3600, 'title': 'Essays of Michel de Montaigne'},

    # Science
    {'id': 2009, 'title': 'On the Origin of Species', 'author': 'Charles Darwin'},
    {'id': 5740, 'title': 'The Interpretation of Dreams', 'author': 'Sigmund Freud'},

    # History
    {'id': 10, 'title': 'The King James Bible'},
    {'id': 3600, 'title': 'Essays', 'author': 'Michel de Montaigne'},
]

class GutenbergScraper:
    def __init__(self):
        self.session = requests.Session()

    def get_book_text(self, book_id):
        """Fetch book from Project Gutenberg"""
        url = f"https://www.gutenberg.org/files/{book_id}/{book_id}-0.txt"

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except:
            # Try alternate URL
            url = f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt"
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response.text
            except Exception as e:
                print(f"  ❌ Failed to fetch: {e}")
                return None

    def chunk_book(self, text, chunk_size=2000):
        """Split book into chunks for training"""
        # Remove Project Gutenberg header/footer
        lines = text.split('\n')

        # Find start of actual content
        start_idx = 0
        for i, line in enumerate(lines):
            if '***' in line and 'START' in line.upper():
                start_idx = i + 1
                break

        # Find end of actual content
        end_idx = len(lines)
        for i in range(len(lines)-1, 0, -1):
            if '***' in lines[i] and 'END' in lines[i].upper():
                end_idx = i
                break

        # Get clean text
        clean_text = '\n'.join(lines[start_idx:end_idx])

        # Split into chunks
        words = clean_text.split()
        chunks = []

        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i+chunk_size])
            if len(chunk) > 500:  # Only keep substantial chunks
                chunks.append(chunk)

        return chunks

    def scrape_book(self, book_info):
        """Scrape a book and create training examples"""
        book_id = book_info['id']
        title = book_info['title']

        print(f"\n[{title}] Fetching...")

        text = self.get_book_text(book_id)
        if not text:
            return 0

        print(f"  ✅ Fetched ({len(text)} chars)")
        print(f"  🔪 Chunking...")

        chunks = self.chunk_book(text)
        print(f"  ✅ Created {len(chunks)} chunks")

        # Create training examples (NO API CALLS!)
        examples = []
        for i, chunk in enumerate(chunks[:20], 1):  # Limit to 20 chunks per book
            example = {
                'input': f"Continue this passage from {title}:",
                'output': chunk,
                'source': 'gutenberg',
                'category': 'literature',
                'book_id': book_id,
                'book_title': title,
                'chunk_num': i
            }
            examples.append(example)

        # Save
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        data_file = DATA_DIR / f'gutenberg_{book_id}_{timestamp}.jsonl'

        with open(data_file, 'w') as f:
            for ex in examples:
                f.write(json.dumps(ex) + '\n')

        print(f"  💾 Saved {len(examples)} examples")

        return len(examples)

def main():
    scraper = GutenbergScraper()

    print("="*70)
    print("PROJECT GUTENBERG SCRAPER - FREE BOOKS")
    print("="*70)
    print(f"Books to scrape: {len(BOOKS)}")
    print(f"NO API CALLS NEEDED - just download and chunk!")
    print("="*70)

    total = 0

    for book in BOOKS:
        count = scraper.scrape_book(book)
        total += count
        time.sleep(2)  # Be nice to server

    print(f"\n{'='*70}")
    print(f"✅ COMPLETE! Collected {total} literature examples")
    print(f"{'='*70}")

if __name__ == '__main__':
    main()
