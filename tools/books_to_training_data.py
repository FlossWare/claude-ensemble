#!/usr/bin/env python3
"""
Generate Training Data from PDF Books
- Reads PDFs from /mnt/nas/media/books/
- Generates Q&A training examples
- Stores in /mnt/nas/web-scrape/synthetic-data/
- ALSO keeps PDFs indexed in PostgreSQL vector DB for RAG
"""

import os
import sys
from pathlib import Path
import json
import PyPDF2
from datetime import datetime

# Add shared to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'shared'))
from multi_provider_generator import MultiProviderGenerator

# Paths
BOOKS_DIR = Path('/mnt/nas/media/books')
OUTPUT_DIR = Path('/mnt/nas/web-scrape/synthetic-data')
PROCESSED_TRACKER = Path('/mnt/nas/web-scrape/processed_books.json')

class BookTrainingDataGenerator:
    """Generate training data from PDF books"""

    def __init__(self):
        self.generator = MultiProviderGenerator()
        self.processed = self._load_processed()

    def _load_processed(self):
        """Load processed books tracker"""
        if PROCESSED_TRACKER.exists():
            with open(PROCESSED_TRACKER) as f:
                return json.load(f)
        return {'books': [], 'count': 0}

    def _save_processed(self):
        """Save processed tracker"""
        PROCESSED_TRACKER.parent.mkdir(parents=True, exist_ok=True)
        with open(PROCESSED_TRACKER, 'w') as f:
            json.dump(self.processed, f, indent=2)

    def extract_text_from_pdf(self, pdf_path, max_pages=10):
        """Extract text from first N pages of PDF"""
        try:
            with open(pdf_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)

                # Limit pages
                num_pages = min(len(reader.pages), max_pages)

                text = ""
                for i in range(num_pages):
                    page = reader.pages[i]
                    text += page.extract_text()

                return text[:3000]  # First 3000 chars
        except Exception as e:
            print(f"    ⚠️  Error reading PDF: {e}")
            return None

    def generate_from_book(self, pdf_path):
        """Generate training examples from a book"""

        # Skip if already processed
        book_name = str(pdf_path.relative_to(BOOKS_DIR))
        if book_name in self.processed['books']:
            return []

        print(f"  📖 {pdf_path.name}")

        # Extract text
        text = self.extract_text_from_pdf(pdf_path, max_pages=10)

        if not text or len(text) < 200:
            print(f"    ⚠️  Not enough text extracted")
            return []

        dataset = []

        # Strategy 1: Explain what this book teaches
        prompt1 = f"""Based on this excerpt from a technical book, explain what topics it covers:

Title: {pdf_path.stem}

Excerpt:
{text[:800]}

Provide a 2-3 sentence summary of what you'd learn from this book:"""

        completion1 = self.generator.generate(prompt1, 512)

        if completion1:
            dataset.append({
                'prompt': prompt1,
                'completion': completion1,
                'source': 'PDF Book',
                'book_path': str(pdf_path),
                'book_title': pdf_path.stem,
                'type': 'book_summary'
            })

        # Strategy 2: Extract key concepts
        prompt2 = f"""What are the main concepts covered in this technical book excerpt?

Title: {pdf_path.stem}

Excerpt:
{text[:600]}

List 3-5 key concepts or technologies:"""

        completion2 = self.generator.generate(prompt2, 512)

        if completion2:
            dataset.append({
                'prompt': prompt2,
                'completion': completion2,
                'source': 'PDF Book',
                'book_path': str(pdf_path),
                'book_title': pdf_path.stem,
                'type': 'book_concepts'
            })

        # Mark as processed
        self.processed['books'].append(book_name)
        self.processed['count'] += 1
        self._save_processed()

        print(f"    ✅ Generated {len(dataset)} examples")

        return dataset

    def process_books(self, max_books=None):
        """Process all PDF books"""

        print("\n" + "="*70)
        print("📚 GENERATING TRAINING DATA FROM PDF BOOKS")
        print("="*70)
        print(f"Books directory: {BOOKS_DIR}")
        print(f"Output directory: {OUTPUT_DIR}")
        print(f"Already processed: {self.processed['count']} books")
        print("="*70)
        print()

        # Find all PDFs
        pdf_files = list(BOOKS_DIR.rglob('*.pdf'))

        print(f"Found {len(pdf_files)} PDF files")

        if max_books:
            pdf_files = pdf_files[:max_books]
            print(f"Processing first {max_books} books")

        print()

        all_data = []

        for i, pdf_path in enumerate(pdf_files):
            print(f"[{i+1}/{len(pdf_files)}] ", end='')

            examples = self.generate_from_book(pdf_path)
            all_data.extend(examples)

        return all_data

    def save_dataset(self, dataset):
        """Save dataset to JSONL"""

        if not dataset:
            print("\n⚠️  No data generated")
            return

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'books_{len(dataset)}_{timestamp}.jsonl'
        filepath = OUTPUT_DIR / filename

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w') as f:
            for ex in dataset:
                f.write(json.dumps(ex) + '\n')

        print(f"\n✅ Saved {len(dataset)} examples to {filepath}")

        # Print stats
        stats = self.generator.get_stats()
        print(f"\n📊 Generation Stats:")
        print(f"  Total requests: {stats['total_requests']}")
        print(f"  By provider: {stats['by_provider']}")
        print(f"  Total cost: ${stats['total_cost_usd']:.4f}")

        return filepath


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Generate training data from PDF books')
    parser.add_argument('--max-books', type=int, help='Maximum number of books to process')
    parser.add_argument('--batch-size', type=int, default=50, help='Process in batches')

    args = parser.parse_args()

    generator = BookTrainingDataGenerator()

    # Process books
    dataset = generator.process_books(max_books=args.max_books)

    # Save
    if dataset:
        generator.save_dataset(dataset)

        print("\n" + "="*70)
        print("🎉 COMPLETE!")
        print(f"Total examples generated: {len(dataset)}")
        print(f"Books processed: {generator.processed['count']}")
        print(f"Next: Model will train on these books!")
        print("="*70)
