#!/usr/bin/env python3
"""
FlossWare Module: Document Parser (#214)
Parse multiple document formats for RAG pipelines
"""

import re
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

class DocumentParser:
    """
    Parse documents from various formats

    Supported formats:
    - Markdown (.md)
    - JSON (.json)
    - JSONL (.jsonl)
    - Text (.txt)
    - Python (.py) - extracts docstrings
    - JavaScript (.js, .mjs) - extracts JSDoc
    """

    def __init__(self):
        self.parsers = {
            '.md': self._parse_markdown,
            '.json': self._parse_json,
            '.jsonl': self._parse_jsonl,
            '.txt': self._parse_text,
            '.py': self._parse_python,
            '.js': self._parse_javascript,
            '.mjs': self._parse_javascript,
        }

    def parse_file(self, filepath: str) -> Dict[str, Any]:
        """
        Parse file and extract structured content

        Returns:
            {
                'content': str,           # Main text content
                'metadata': dict,         # Extracted metadata
                'sections': List[dict],   # Document sections (for chunking)
                'format': str             # File format
            }
        """
        path = Path(filepath)
        suffix = path.suffix.lower()

        if suffix not in self.parsers:
            # Fallback to plain text
            return self._parse_text(filepath)

        return self.parsers[suffix](filepath)

    def _parse_markdown(self, filepath: str) -> Dict[str, Any]:
        """Parse Markdown with section extraction"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        sections = []
        current_section = {'title': 'Introduction', 'content': '', 'level': 0}

        for line in content.split('\n'):
            # Detect headers
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if header_match:
                # Save previous section
                if current_section['content']:
                    sections.append(current_section.copy())

                # Start new section
                level = len(header_match.group(1))
                title = header_match.group(2)
                current_section = {'title': title, 'content': '', 'level': level}
            else:
                current_section['content'] += line + '\n'

        # Save final section
        if current_section['content']:
            sections.append(current_section)

        # Extract frontmatter metadata if present
        metadata = {}
        if content.startswith('---'):
            frontmatter_end = content.find('---', 3)
            if frontmatter_end > 0:
                frontmatter = content[3:frontmatter_end].strip()
                for line in frontmatter.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        metadata[key.strip()] = value.strip()

        return {
            'content': content,
            'metadata': metadata,
            'sections': sections,
            'format': 'markdown'
        }

    def _parse_json(self, filepath: str) -> Dict[str, Any]:
        """Parse JSON documents"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Convert JSON to searchable text
        content = json.dumps(data, indent=2)

        return {
            'content': content,
            'metadata': {'source': 'json', 'keys': list(data.keys()) if isinstance(data, dict) else []},
            'sections': [{'title': 'JSON Data', 'content': content, 'level': 1}],
            'format': 'json',
            'data': data  # Include parsed data
        }

    def _parse_jsonl(self, filepath: str) -> Dict[str, Any]:
        """Parse JSONL (newline-delimited JSON)"""
        sections = []

        with open(filepath, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                if line.strip():
                    try:
                        record = json.loads(line)
                        sections.append({
                            'title': f'Record {i}',
                            'content': json.dumps(record, indent=2),
                            'level': 1,
                            'data': record
                        })
                    except json.JSONDecodeError:
                        continue

        content = '\n'.join(s['content'] for s in sections)

        return {
            'content': content,
            'metadata': {'source': 'jsonl', 'record_count': len(sections)},
            'sections': sections,
            'format': 'jsonl'
        }

    def _parse_text(self, filepath: str) -> Dict[str, Any]:
        """Parse plain text"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Split by paragraphs
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        sections = [
            {'title': f'Paragraph {i+1}', 'content': p, 'level': 1}
            for i, p in enumerate(paragraphs)
        ]

        return {
            'content': content,
            'metadata': {'source': 'text'},
            'sections': sections,
            'format': 'text'
        }

    def _parse_python(self, filepath: str) -> Dict[str, Any]:
        """Parse Python files - extract docstrings and comments"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        sections = []

        # Extract module docstring
        module_doc_match = re.match(r'^(\"\"\"(.+?)\"\"\"|\'\'\'(.+?)\'\'\')', content, re.DOTALL)
        if module_doc_match:
            docstring = module_doc_match.group(2) or module_doc_match.group(3)
            sections.append({
                'title': 'Module Documentation',
                'content': docstring.strip(),
                'level': 1
            })

        # Extract function/class docstrings
        func_pattern = r'def\s+(\w+)\(.*?\):\s*(?:\"\"\"(.+?)\"\"\"|\'\'\'(.+?)\'\'\')?'
        class_pattern = r'class\s+(\w+).*?:\s*(?:\"\"\"(.+?)\"\"\"|\'\'\'(.+?)\'\'\')?'

        for match in re.finditer(func_pattern, content, re.DOTALL):
            name = match.group(1)
            docstring = match.group(2) or match.group(3) or ''
            if docstring:
                sections.append({
                    'title': f'Function: {name}',
                    'content': docstring.strip(),
                    'level': 2
                })

        for match in re.finditer(class_pattern, content, re.DOTALL):
            name = match.group(1)
            docstring = match.group(2) or match.group(3) or ''
            if docstring:
                sections.append({
                    'title': f'Class: {name}',
                    'content': docstring.strip(),
                    'level': 2
                })

        return {
            'content': content,
            'metadata': {'source': 'python', 'docstring_count': len(sections)},
            'sections': sections,
            'format': 'python'
        }

    def _parse_javascript(self, filepath: str) -> Dict[str, Any]:
        """Parse JavaScript/ESM - extract JSDoc comments"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        sections = []

        # Extract JSDoc comments (/** ... */)
        jsdoc_pattern = r'/\*\*(.+?)\*/'
        for match in re.finditer(jsdoc_pattern, content, re.DOTALL):
            doc = match.group(1).strip()
            # Clean up asterisks
            doc = '\n'.join(line.lstrip(' *') for line in doc.split('\n'))

            sections.append({
                'title': 'JSDoc Comment',
                'content': doc,
                'level': 1
            })

        # Extract function/class names
        func_pattern = r'(?:export\s+)?(?:async\s+)?function\s+(\w+)'
        class_pattern = r'(?:export\s+)?class\s+(\w+)'

        functions = re.findall(func_pattern, content)
        classes = re.findall(class_pattern, content)

        metadata = {
            'source': 'javascript',
            'functions': functions,
            'classes': classes,
            'jsdoc_count': len(sections)
        }

        return {
            'content': content,
            'metadata': metadata,
            'sections': sections,
            'format': 'javascript'
        }

    def parse_batch(self, filepaths: List[str]) -> List[Dict[str, Any]]:
        """Parse multiple files"""
        return [self.parse_file(fp) for fp in filepaths]


# Test module
if __name__ == '__main__':
    print("=== Document Parser Test ===\n")

    parser = DocumentParser()

    # Test 1: Create test markdown
    test_md = '/tmp/test_doc.md'
    with open(test_md, 'w') as f:
        f.write("""---
title: Test Document
author: Fleet
---

# Introduction

This is a test document for the parser.

## Section 1

Content of section 1.

## Section 2

Content of section 2.
""")

    print("Test 1: Parse Markdown")
    result = parser.parse_file(test_md)
    print(f"  Format: {result['format']}")
    print(f"  Sections: {len(result['sections'])}")
    print(f"  Metadata: {result['metadata']}")
    print(f"  First section: {result['sections'][0]['title']}\n")

    # Test 2: Parse JSON
    test_json = '/tmp/test_doc.json'
    with open(test_json, 'w') as f:
        json.dump({'test': 'data', 'version': 1}, f)

    print("Test 2: Parse JSON")
    result = parser.parse_file(test_json)
    print(f"  Format: {result['format']}")
    print(f"  Has data: {'data' in result}")
    print(f"  Metadata keys: {result['metadata']['keys']}\n")

    # Test 3: Parse JSONL
    test_jsonl = '/tmp/test_doc.jsonl'
    with open(test_jsonl, 'w') as f:
        f.write('{"id": 1, "text": "First record"}\n')
        f.write('{"id": 2, "text": "Second record"}\n')

    print("Test 3: Parse JSONL")
    result = parser.parse_file(test_jsonl)
    print(f"  Format: {result['format']}")
    print(f"  Records: {result['metadata']['record_count']}")
    print(f"  Sections: {len(result['sections'])}\n")

    # Test 4: Parse Python file (use self!)
    print("Test 4: Parse Python (this file)")
    result = parser.parse_file(__file__)
    print(f"  Format: {result['format']}")
    print(f"  Docstrings found: {result['metadata']['docstring_count']}")
    if result['sections']:
        print(f"  First section: {result['sections'][0]['title']}\n")

    print("=== Tests Complete ===\n")
