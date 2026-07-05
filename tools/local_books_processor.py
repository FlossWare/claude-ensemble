#!/usr/bin/env python3
"""
LOCAL BOOKS PROCESSOR
Process PDF books from /mnt/nas/media/books/
NO API CALLS - just extract and chunk text!
"""

import json
from pathlib import Path
from datetime import datetime
import PyPDF2

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

BOOKS_DIR = Path('/mnt/nas/media/books')

def extract_text_from_pdf(pdf_path, max_pages=50):
    """Extract text from PDF (first N pages)"""
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            num_pages = min(len(reader.pages), max_pages)

            text = ""
            for i in range(num_pages):
                page = reader.pages[i]
                text += page.extract_text()

            return text
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None

def chunk_text(text, chunk_size=1500):
    """Split text into chunks"""
    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size):
        chunk = ' '.join(words[i:i+chunk_size])
        if len(chunk) > 500:  # Only keep substantial chunks
            chunks.append(chunk)

    return chunks

def process_book(pdf_path):
    """Process a single PDF book"""
    book_name = pdf_path.stem

    print(f"\n[{book_name}]")
    print(f"  📖 Extracting text...")

    text = extract_text_from_pdf(pdf_path, max_pages=50)
    if not text:
        return 0

    print(f"  ✅ Extracted {len(text)} chars from {pdf_path.name}")
    print(f"  🔪 Chunking...")

    chunks = chunk_text(text)
    print(f"  ✅ Created {len(chunks)} chunks")

    # Create training examples (NO API CALLS!)
    examples = []
    for i, chunk in enumerate(chunks[:10], 1):  # Limit to 10 chunks per book
        example = {
            'input': f"Continue reading from {book_name}:",
            'output': chunk,
            'source': 'local_pdf',
            'category': 'technical_books',
            'book_name': book_name,
            'chunk_num': i
        }
        examples.append(example)

    # Save
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_name = book_name.replace(' ', '_').replace('/', '_')[:50]
    data_file = DATA_DIR / f'book_{safe_name}_{timestamp}.jsonl'

    with open(data_file, 'w') as f:
        for ex in examples:
            f.write(json.dumps(ex) + '\n')

    print(f"  💾 Saved {len(examples)} examples")

    return len(examples)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--max-books', type=int, default=100, help='Max books to process')

    args = parser.parse_args()

    print("="*70)
    print("LOCAL BOOKS PROCESSOR - NO API CALLS")
    print("="*70)
    print(f"Source: {BOOKS_DIR}")
    print(f"Output: {DATA_DIR}")
    print("NO API calls - just extract and chunk!")
    print("="*70)

    # Find all PDFs
    pdf_files = list(BOOKS_DIR.glob('**/*.pdf'))
    print(f"\nFound {len(pdf_files)} PDF files")
    print(f"Processing first {args.max_books}...")

    total = 0

    for i, pdf_path in enumerate(pdf_files[:args.max_books], 1):
        print(f"\n[{i}/{min(len(pdf_files), args.max_books)}] {pdf_path.name[:50]}...")
        count = process_book(pdf_path)
        total += count

    print(f"\n{'='*70}")
    print(f"✅ COMPLETE! Processed {min(len(pdf_files), args.max_books)} books")
    print(f"Generated {total} training examples")
    print(f"{'='*70}")

if __name__ == '__main__':
    main()
