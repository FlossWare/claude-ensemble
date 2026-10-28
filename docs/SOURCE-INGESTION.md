# Source ingestion adapters

Issue #19 adds source acquisition/parsing before the existing Memory-to-Index pipeline. Adapters produce normalized SourceDocument records; they do not chunk, tokenize, embed, rerank, or write Index directly.

## Supported inputs

- **RFC text:** import a local RFC text file. The adapter preserves the complete text and extracts the RFC number, title, and numbered section headings into provenance metadata.
- **Patents:** import saved patent XML or HTML. XML parsing extracts common title, publication identifier, abstract, description, and claim fields. HTML is reduced to visible text; metadata extraction is intentionally best-effort.
- **Source repositories:** scan a local Git working tree. Eligible text/source files retain repository name, relative path, extension, and detected symbol names. .git content, symlinks, binary/unsupported suffixes, and oversized files are excluded.
- **Documents:** Markdown, reStructuredText, and plain text work without extra dependencies. PDF text extraction uses the optional pypdf package; install and pin it in the environment used for PDF imports. A scanned/image-only PDF needs OCR before this adapter can extract useful text.

Each normalized item has a stable source key, source URI, title/type, media type, content hash, source revision, import timestamp, and format metadata. The normalized content is limited to 262,144 UTF-8 bytes to match the current Memory owner contract. Large RFCs or source files must be split at the source-adapter layer in a future change rather than silently truncated.

## Import lifecycle

SourceManifest stores the source key, content hash, Memory identity, revision sequence, scope, and state in SQLite. SourcePipeline sends records to the existing Memory REST endpoints:

1. A new source is submitted with POST /api/v1/memories.
2. An unchanged active source is skipped by content hash.
3. A changed source is read from Memory and submitted as a revision with its expected base sequence.
4. A completed source scan can call remove_missing(current_source_keys) to tombstone removed sources through Memory. Do this only after the source scan completes successfully; a partial/failed scan must never be interpreted as mass deletion.
5. ingest_many isolates per-item errors and returns a result for every input.

Memory remains the canonical owner. Indexing stays asynchronous and follows the existing Chunking -> Tokenization -> Embedding -> Index REST path. Import success means the Memory request was accepted, not that indexing is complete; inspect the returned operation ID/status before declaring the content searchable.

## Configuration example

The API caller supplies deployment-owned scope and Index profile; the adapter does not invent an access-control scope or profile digest.

~~~python
from pathlib import Path
from runtime.source_ingestion import (
    DocumentAdapter, GitRepositoryAdapter, MemoryRestClient,
    RfcAdapter, SourceManifest, SourcePipeline,
)

scope = {"type": "project", "id": "technical-library", "visibility": "private"}
index_profile = {
    "name": "default",
    "version": "0.1",
    "digest": "<the exact 64-character digest from the active Index profile>",
}
client = MemoryRestClient("http://127.0.0.1:8080")
manifest = SourceManifest(Path.home() / ".FlossWare/claude-ensemble/source-manifest.sqlite3")
pipeline = SourcePipeline(client, manifest)

documents = RfcAdapter().read("/data/rfc/rfc9110.txt")
documents += GitRepositoryAdapter().read("/data/working-tree")
documents += DocumentAdapter().read("/data/design.md")
results = pipeline.ingest_many(documents, scope=scope, index_profile=index_profile)
for result in results:
    print(result)
~~~

Patent input uses PatentAdapter().read(path). For PDFs, install pypdf in the importer environment before use. Source acquisition/download scheduling is intentionally separate from parsing; the first slice accepts local files and local working trees and does not download source material or model weights automatically.

## Extending adapters

Implement SourceAdapter.read(source) -> list[SourceDocument]. For every emitted document:

- use a stable source_key for the same logical source across runs;
- retain canonical source URI/path and source-specific provenance;
- let _document normalize line endings and calculate the content hash;
- reject malformed/oversized items with SourceIngestionError rather than truncating content;
- add fixtures for parsing, provenance, unchanged reruns, changed revisions, malformed input, and removal behavior.

Do not add a source-specific indexing path. All normalized content goes through Memory and the existing REST pipeline.
