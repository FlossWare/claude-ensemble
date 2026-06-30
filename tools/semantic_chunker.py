#!/usr/bin/env python3
"""
Semantic Chunker - Intelligent text chunking that preserves semantic boundaries
Handles code blocks, paragraphs, and maintains context overlap
IMPROVED: Memory-efficient with generators and streaming support
"""

import re
from typing import List, Dict, Any, Iterator, Optional

class SemanticChunker:
    def __init__(
        self,
        min_chunk_size: int = 500,
        max_chunk_size: int = 1500,
        overlap_size: int = 100,
        max_text_size: Optional[int] = 10_000_000  # 10MB default limit
    ):
        """
        Initialize semantic chunker

        Args:
            min_chunk_size: Minimum characters per chunk
            max_chunk_size: Maximum characters per chunk
            overlap_size: Characters to overlap between chunks
            max_text_size: Maximum text size to process (None = unlimited)
        """
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size
        self.max_text_size = max_text_size

    def detect_language(self, text: str) -> str:
        """Detect programming language from code block"""
        # Common language indicators
        patterns = {
            'python': [r'\bdef\b', r'\bclass\b', r'\bimport\b', r'\bfrom\b'],
            'javascript': [r'\bfunction\b', r'\bconst\b', r'\blet\b', r'=>'],
            'java': [r'\bpublic\b', r'\bprivate\b', r'\bclass\b', r'\bvoid\b'],
            'sql': [r'\bSELECT\b', r'\bFROM\b', r'\bWHERE\b', r'\bINSERT\b'],
            'bash': [r'^#!/bin/bash', r'\becho\b', r'\bif\b.*\bthen\b'],
        }

        for lang, indicators in patterns.items():
            if sum(1 for pattern in indicators if re.search(pattern, text, re.IGNORECASE)) >= 2:
                return lang

        return 'unknown'

    def is_code_block(self, text: str) -> bool:
        """Check if text appears to be a code block"""
        # Look for code indicators
        code_indicators = [
            r'^\s{4,}',  # Indented 4+ spaces
            r'^```',  # Markdown code fence
            r'^def\b|^class\b|^function\b',  # Function/class definitions
            r'^\w+\s*\(',  # Function calls
            r'[{};]\s*$',  # Code-like punctuation
        ]

        lines = text.split('\n')
        code_line_count = sum(
            1 for line in lines
            if any(re.match(pattern, line) for pattern in code_indicators)
        )

        return code_line_count / max(len(lines), 1) > 0.3  # 30% threshold

    def split_by_paragraphs(self, text: str) -> List[str]:
        """Split text by paragraph boundaries"""
        # Split on double newlines or markdown headers
        paragraphs = re.split(r'\n\s*\n|\n#{1,6}\s', text)
        return [p.strip() for p in paragraphs if p.strip()]

    def split_code_block(self, text: str) -> List[str]:
        """Split code block by logical boundaries (functions, classes)"""
        chunks = []
        current_chunk = []
        indent_stack = []

        lines = text.split('\n')
        for line in lines:
            # Detect function/class starts
            if re.match(r'^(def\b|class\b|function\b|public\b|private\b)', line.strip()):
                if current_chunk:
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = []

            current_chunk.append(line)

            # If chunk is getting too large, force split
            if len('\n'.join(current_chunk)) > self.max_chunk_size:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []

        if current_chunk:
            chunks.append('\n'.join(current_chunk))

        return chunks

    def chunk_text_stream(self, text: str) -> Iterator[Dict[str, Any]]:
        """
        MEMORY-EFFICIENT: Stream chunks using generator (yields instead of building list)

        Args:
            text: Input text to chunk

        Yields:
            Chunk dicts with content, metadata, and overlap
        """
        # Check size limit
        if self.max_text_size and len(text) > self.max_text_size:
            raise ValueError(f"Text size {len(text)} exceeds max {self.max_text_size}")

        is_code = self.is_code_block(text)
        language = self.detect_language(text) if is_code else None

        raw_chunks = self.split_code_block(text) if is_code else self.split_by_paragraphs(text)

        # Stream chunks with overlap
        current = ""
        previous_chunk = None
        chunk_index = 0

        for i, chunk in enumerate(raw_chunks):
            if len(current) + len(chunk) < self.max_chunk_size:
                current += "\n\n" + chunk if current else chunk
            else:
                if current:
                    # Yield current chunk
                    overlap_prefix = previous_chunk[-self.overlap_size:] if previous_chunk and len(previous_chunk) >= self.overlap_size else ""
                    overlap_suffix = current[-self.overlap_size:] if len(current) >= self.overlap_size else current

                    yield {
                        'index': chunk_index,
                        'content': current,
                        'overlap_prefix': overlap_prefix,
                        'overlap_suffix': overlap_suffix,
                        'char_count': len(current),
                        'has_code': is_code,
                        'language': language,
                        'chunk_type': 'code' if is_code else 'text'
                    }

                    previous_chunk = current
                    chunk_index += 1

                current = chunk

        # Yield final chunk
        if current:
            overlap_prefix = previous_chunk[-self.overlap_size:] if previous_chunk and len(previous_chunk) >= self.overlap_size else ""
            yield {
                'index': chunk_index,
                'content': current,
                'overlap_prefix': overlap_prefix,
                'overlap_suffix': "",
                'char_count': len(current),
                'has_code': is_code,
                'language': language,
                'chunk_type': 'code' if is_code else 'text'
            }

    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Chunk text intelligently preserving semantic boundaries (backward compatible)

        Args:
            text: Input text to chunk

        Returns:
            List of chunk dicts with content, metadata, and overlap
        """
        # Use streaming version and collect results
        return list(self.chunk_text_stream(text))

        # Detect if text is primarily code
        is_code = self.is_code_block(text)
        language = self.detect_language(text) if is_code else None

        if is_code:
            # Split code by logical boundaries
            raw_chunks = self.split_code_block(text)
        else:
            # Split by paragraphs
            raw_chunks = self.split_by_paragraphs(text)

        # Merge small chunks and add overlap
        processed_chunks = []
        current = ""

        for i, chunk in enumerate(raw_chunks):
            if len(current) + len(chunk) < self.max_chunk_size:
                current += "\n\n" + chunk if current else chunk
            else:
                if current:
                    processed_chunks.append(current)
                current = chunk

        if current:
            processed_chunks.append(current)

        # Add overlap and metadata
        for i, chunk_text in enumerate(processed_chunks):
            # Get overlap from previous chunk
            overlap_prefix = ""
            if i > 0 and len(processed_chunks[i-1]) >= self.overlap_size:
                overlap_prefix = processed_chunks[i-1][-self.overlap_size:]

            # Get overlap for next chunk
            overlap_suffix = ""
            if i < len(processed_chunks) - 1:
                overlap_suffix = chunk_text[-self.overlap_size:] if len(chunk_text) >= self.overlap_size else chunk_text

            chunks.append({
                'index': i,
                'content': chunk_text,
                'overlap_prefix': overlap_prefix,
                'overlap_suffix': overlap_suffix,
                'char_count': len(chunk_text),
                'has_code': is_code,
                'language': language,
                'chunk_type': 'code' if is_code else 'text'
            })

        return chunks


def main():
    """Test the semantic chunker"""
    print("="*60)
    print("SEMANTIC CHUNKER TEST")
    print("="*60)

    chunker = SemanticChunker(min_chunk_size=200, max_chunk_size=500, overlap_size=50)

    # Test with code
    code_sample = """
def process_data(input_file):
    data = read_file(input_file)
    cleaned = clean_data(data)
    return cleaned

def clean_data(data):
    # Remove null values
    data = data.dropna()
    # Normalize columns
    data = normalize(data)
    return data

class DataProcessor:
    def __init__(self, config):
        self.config = config

    def run(self):
        print("Processing...")
"""

    print("\n1. Chunking code sample...")
    code_chunks = chunker.chunk_text(code_sample)
    for chunk in code_chunks:
        print(f"  Chunk {chunk['index']}: {chunk['char_count']} chars, lang={chunk['language']}, type={chunk['chunk_type']}")
        print(f"    Preview: {chunk['content'][:80]}...")

    # Test with text
    text_sample = """
This is a paragraph about machine learning. It discusses various concepts
and techniques used in modern AI systems.

Another paragraph follows here. This one talks about neural networks and
their applications in natural language processing.

A third paragraph with more details about transformers and attention
mechanisms in deep learning architectures.
"""

    print("\n2. Chunking text sample...")
    text_chunks = chunker.chunk_text(text_sample)
    for chunk in text_chunks:
        print(f"  Chunk {chunk['index']}: {chunk['char_count']} chars, type={chunk['chunk_type']}")
        print(f"    Overlap prefix: {len(chunk['overlap_prefix'])} chars")

    print("\n✅ Semantic chunker test complete!")


if __name__ == "__main__":
    main()
