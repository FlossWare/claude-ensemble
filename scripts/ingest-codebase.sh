#!/bin/bash
# Ingest Codebase into ChromaDB
# Usage: ./ingest-codebase.sh /path/to/repo

REPO_PATH="$1"
CHROMA_PATH="$HOME/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/knowledge/chromadb"

if [ -z "$REPO_PATH" ]; then
    echo "Usage: $0 /path/to/repo"
    exit 1
fi

if [ ! -d "$REPO_PATH" ]; then
    echo "Error: Repository path does not exist: $REPO_PATH"
    exit 1
fi

echo "🚀 Ingesting codebase: $REPO_PATH"
echo "   Target: $CHROMA_PATH"
echo

# Python script to do the actual ingestion
python3 << EOF
import os
import chromadb
from pathlib import Path
import hashlib

REPO_PATH = "$REPO_PATH"
CHROMA_PATH = "$CHROMA_PATH"

# File extensions to ingest
CODE_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.c', '.cpp',
    '.h', '.hpp', '.cs', '.rb', '.php', '.swift', '.kt', '.scala', '.sh',
    '.bash', '.yaml', '.yml', '.json', '.xml', '.sql', '.md', '.txt'
}

def should_skip(path):
    """Skip common non-code directories"""
    skip_dirs = {
        'node_modules', '.git', 'venv', 'env', '__pycache__',
        '.venv', 'build', 'dist', 'target', '.cache', 'vendor'
    }
    parts = Path(path).parts
    return any(skip_dir in parts for skip_dir in skip_dirs)

def chunk_file(content, max_chars=2000):
    """Chunk large files into smaller pieces"""
    if len(content) <= max_chars:
        return [content]

    # Split by lines and group into chunks
    lines = content.split('\n')
    chunks = []
    current_chunk = []
    current_size = 0

    for line in lines:
        line_size = len(line) + 1  # +1 for newline
        if current_size + line_size > max_chars and current_chunk:
            chunks.append('\n'.join(current_chunk))
            current_chunk = [line]
            current_size = line_size
        else:
            current_chunk.append(line)
            current_size += line_size

    if current_chunk:
        chunks.append('\n'.join(current_chunk))

    return chunks

# Connect to ChromaDB
client = chromadb.PersistentClient(path=CHROMA_PATH)

# Get or create collection
repo_name = os.path.basename(REPO_PATH.rstrip('/'))
collection_name = f"code-{repo_name}".replace('.', '-').replace('_', '-')[:63]

try:
    collection = client.get_collection(collection_name)
    print(f"📚 Using existing collection: {collection_name}")
except:
    collection = client.create_collection(
        name=collection_name,
        metadata={"repo_path": REPO_PATH}
    )
    print(f"📚 Created new collection: {collection_name}")

# Walk through repo and ingest files
files_processed = 0
chunks_added = 0
errors = 0

for root, dirs, files in os.walk(REPO_PATH):
    # Skip unwanted directories
    if should_skip(root):
        continue

    for file in files:
        ext = Path(file).suffix.lower()
        if ext not in CODE_EXTENSIONS:
            continue

        file_path = os.path.join(root, file)
        rel_path = os.path.relpath(file_path, REPO_PATH)

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Chunk the file
            chunks = chunk_file(content)

            # Add each chunk to ChromaDB
            for i, chunk in enumerate(chunks):
                chunk_id = hashlib.md5(f"{rel_path}-chunk-{i}".encode()).hexdigest()

                collection.add(
                    ids=[chunk_id],
                    documents=[chunk],
                    metadatas=[{
                        'file': rel_path,
                        'extension': ext,
                        'chunk': i,
                        'total_chunks': len(chunks),
                        'repo': repo_name
                    }]
                )
                chunks_added += 1

            files_processed += 1
            if files_processed % 100 == 0:
                print(f"   Processed {files_processed} files, {chunks_added} chunks...")

        except Exception as e:
            errors += 1
            if errors < 10:  # Only show first 10 errors
                print(f"   ⚠️  Error processing {rel_path}: {e}")

print()
print(f"✅ Ingestion complete!")
print(f"   Files processed: {files_processed:,}")
print(f"   Chunks added: {chunks_added:,}")
print(f"   Errors: {errors}")
print(f"   Collection: {collection_name}")
print(f"   Total vectors in collection: {collection.count():,}")

EOF

echo
echo "🎉 Done!"
