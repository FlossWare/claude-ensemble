# Link to code examples mentioned in PDFs

**Status:** Open  
**Priority:** Low  
**Created:** 2026-07-04  

## Goal

Extract and link code examples from PDFs to create a searchable code snippet library.

## Context

Technical PDFs contain code examples, configurations, and snippets. These are currently buried in text_preview. Extracting them creates a reusable code knowledge base.

## Implementation

- Parse PDF text for code blocks (indented sections, language keywords)
- Extract code snippets with context
- Store in new table: `learning.code_snippets`
- Link in Neo4j: `(PDFDocument)-[:CONTAINS_CODE]->(CodeSnippet)`
- Add metadata: language, topic, line numbers

## Benefits

- "Show me Python examples from my library"
- "Find Kubernetes deployment configs in PDFs"
- Reusable code patterns from books
- Learning by example from curated sources

## Technical Approach

```python
# Extract code blocks from PDF text
import re

def extract_code_blocks(text):
    # Detect indented blocks (4+ spaces)
    # Detect language keywords (def, class, function, etc.)
    # Extract with surrounding context
    # Classify language (python, java, yaml, etc.)
```

## Database Schema

```sql
CREATE TABLE learning.code_snippets (
    id SERIAL PRIMARY KEY,
    pdf_path TEXT REFERENCES learning.pdf_metadata(pdf_path),
    code TEXT NOT NULL,
    language VARCHAR(50),
    context TEXT,
    page_number INT,
    embedding vector(384)
);
```

## Related

- PDF extraction: `tools/process_single_pdf_simple.sh`
- Text storage: `learning.pdf_metadata`

## Acceptance Criteria

- [ ] Code extraction function created
- [ ] Snippets stored with language detection
- [ ] Neo4j relationship: `CONTAINS_CODE`
- [ ] Query: "Find Python examples about async" returns results
- [ ] Language stats: count of snippets per language
