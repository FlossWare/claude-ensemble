#!/bin/bash
# Ingest PDFs into ChromaDB
# Usage: ./ingest-pdfs.sh /path/to/pdfs/

PDF_DIR="$1"
CHROMA_PATH="$HOME/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/knowledge/chromadb"

if [ -z "$PDF_DIR" ]; then
    echo "Usage: $0 /path/to/pdfs/"
    exit 1
fi

if [ ! -d "$PDF_DIR" ]; then
    echo "Error: PDF directory does not exist: $PDF_DIR"
    exit 1
fi

echo "📄 Ingesting PDFs from: $PDF_DIR"
echo "   Target: $CHROMA_PATH"
echo

# Check if pypdf is installed
if ! python3 -c "import pypdf" 2>/dev/null; then
    echo "📦 Installing pypdf..."
    pip install pypdf --quiet
fi

# Python script to do the actual ingestion
python3 << EOF
import os
import chromadb
from pathlib import Path
import hashlib
import pypdf

PDF_DIR = "$PDF_DIR"
CHROMA_PATH = "$CHROMA_PATH"

def chunk_text(text, max_chars=2000):
    """Chunk text into smaller pieces"""
    if len(text) <= max_chars:
        return [text]

    # Split into sentences (rough approximation)
    sentences = text.replace('. ', '.|').replace('? ', '?|').replace('! ', '!|').split('|')

    chunks = []
    current_chunk = []
    current_size = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        sentence_size = len(sentence) + 2  # +2 for '. '

        if current_size + sentence_size > max_chars and current_chunk:
            chunks.append('. '.join(current_chunk) + '.')
            current_chunk = [sentence]
            current_size = sentence_size
        else:
            current_chunk.append(sentence)
            current_size += sentence_size

    if current_chunk:
        chunks.append('. '.join(current_chunk) + '.')

    return chunks

# Connect to ChromaDB
client = chromadb.PersistentClient(path=CHROMA_PATH)

# Get or create collection
try:
    collection = client.get_collection("pdfs")
    print(f"📚 Using existing collection: pdfs")
except:
    collection = client.create_collection(
        name="pdfs",
        metadata={"type": "pdf_documents"}
    )
    print(f"📚 Created new collection: pdfs")

# Find all PDFs
pdf_files = list(Path(PDF_DIR).rglob("*.pdf"))
print(f"   Found {len(pdf_files)} PDF files")
print()

pdfs_processed = 0
pages_processed = 0
chunks_added = 0
errors = 0

for pdf_path in pdf_files:
    rel_path = pdf_path.relative_to(PDF_DIR)

    try:
        # Read PDF
        with open(pdf_path, 'rb') as f:
            pdf_reader = pypdf.PdfReader(f)
            num_pages = len(pdf_reader.pages)

            # Process each page
            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()

                if not text.strip():
                    continue  # Skip empty pages

                # Chunk the page
                chunks = chunk_text(text)

                # Add each chunk to ChromaDB
                for chunk_idx, chunk in enumerate(chunks):
                    chunk_id = hashlib.md5(
                        f"{rel_path}-page{page_num}-chunk{chunk_idx}".encode()
                    ).hexdigest()

                    collection.add(
                        ids=[chunk_id],
                        documents=[chunk],
                        metadatas=[{
                            'file': str(rel_path),
                            'page': page_num + 1,
                            'total_pages': num_pages,
                            'chunk': chunk_idx,
                            'source': 'pdf'
                        }]
                    )
                    chunks_added += 1

                pages_processed += 1

            pdfs_processed += 1
            if pdfs_processed % 10 == 0:
                print(f"   Processed {pdfs_processed}/{len(pdf_files)} PDFs, {pages_processed} pages, {chunks_added} chunks...")

    except Exception as e:
        errors += 1
        if errors < 10:  # Only show first 10 errors
            print(f"   ⚠️  Error processing {rel_path}: {e}")

print()
print(f"✅ PDF ingestion complete!")
print(f"   PDFs processed: {pdfs_processed:,}")
print(f"   Pages processed: {pages_processed:,}")
print(f"   Chunks added: {chunks_added:,}")
print(f"   Errors: {errors}")
print(f"   Total vectors in collection: {collection.count():,}")

EOF

echo
echo "🎉 Done!"
