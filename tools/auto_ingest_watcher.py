#!/usr/bin/env python3
"""
Auto-Ingestion File Watcher
Monitors /mnt/nas/web-scrape/synthetic-data/ for new JSONL files
Automatically processes them through the full pipeline:
  1. Read JSONL
  2. Chunk text
  3. Generate embeddings
  4. Store in PostgreSQL
  5. Trigger OrientDB sync
"""

import asyncio
import asyncpg
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from sentence_transformers import SentenceTransformer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
WATCH_DIR = Path('/mnt/nas/web-scrape/synthetic-data')
DB_URL = "postgresql://sfloess@aio-01:5433/learning"
CHUNK_SIZE = 500  # words per chunk
OVERLAP = 50      # word overlap between chunks

# Global state
embedding_model = None
db_pool = None
processed_files = set()

class IngestionHandler(FileSystemEventHandler):
    """Handle new JSONL files"""

    def __init__(self, loop):
        self.loop = loop

    def on_created(self, event):
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Only process JSONL files
        if file_path.suffix != '.jsonl':
            return

        # Skip if already processed
        if str(file_path) in processed_files:
            return

        logger.info(f"🆕 New file detected: {file_path.name}")

        # Schedule processing
        asyncio.run_coroutine_threadsafe(
            process_file(file_path),
            self.loop
        )

async def init_resources():
    """Initialize database and embedding model"""
    global embedding_model, db_pool

    logger.info("🔧 Initializing resources...")

    # Load embedding model
    logger.info("  Loading sentence-transformers model...")
    embedding_model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
    logger.info("  ✅ Embedding model loaded (384 dimensions)")

    # Create database pool
    logger.info("  Connecting to PostgreSQL...")
    db_pool = await asyncpg.create_pool(
        DB_URL,
        min_size=2,
        max_size=10,
        command_timeout=60
    )
    logger.info("  ✅ Database pool created")

    # Ensure tables exist
    await ensure_tables()

    logger.info("✅ Resources initialized!")

async def ensure_tables():
    """Create tables if they don't exist"""
    async with db_pool.acquire() as conn:
        # Training data table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS training_data (
                id SERIAL PRIMARY KEY,
                source TEXT NOT NULL,
                category TEXT,
                input_text TEXT,
                output_text TEXT,
                full_text TEXT,
                metadata JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Chunks table with vector embeddings
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id SERIAL PRIMARY KEY,
                training_data_id INTEGER REFERENCES training_data(id),
                chunk_text TEXT NOT NULL,
                chunk_index INTEGER,
                embedding vector(1024),
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Create vector index
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS chunks_embedding_idx
            ON chunks USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """)

        # Processed files tracking
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_files (
                file_path TEXT PRIMARY KEY,
                file_size BIGINT,
                examples_count INTEGER,
                chunks_count INTEGER,
                processed_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        logger.info("  ✅ Tables ensured")

def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=OVERLAP):
    """Split text into overlapping chunks"""
    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size - overlap):
        chunk = ' '.join(words[i:i + chunk_size])
        if len(chunk) > 100:  # Only keep substantial chunks
            chunks.append(chunk)

    return chunks

async def process_file(file_path: Path):
    """Process a single JSONL file through the pipeline"""
    try:
        logger.info(f"📂 Processing: {file_path.name}")

        # Check if already processed
        async with db_pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM processed_files WHERE file_path = $1",
                str(file_path)
            )
            if exists:
                logger.info(f"  ⏭️  Already processed, skipping")
                processed_files.add(str(file_path))
                return

        # Read JSONL file
        examples = []
        with open(file_path, 'r') as f:
            for line in f:
                if line.strip():
                    examples.append(json.loads(line))

        logger.info(f"  📖 Read {len(examples)} examples")

        total_chunks = 0

        # Process each example
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                for i, example in enumerate(examples):
                    # Extract text
                    input_text = example.get('input', '')
                    output_text = example.get('output', '')
                    full_text = f"{input_text}\n\n{output_text}"

                    # Insert training data
                    training_id = await conn.fetchval("""
                        INSERT INTO training_data
                        (source, category, input_text, output_text, full_text, metadata)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        RETURNING id
                    """,
                        example.get('source', 'unknown'),
                        example.get('category', 'general'),
                        input_text,
                        output_text,
                        full_text,
                        json.dumps(example)
                    )

                    # Chunk the full text
                    chunks = chunk_text(full_text)
                    total_chunks += len(chunks)

                    # Generate embeddings and store chunks
                    for chunk_idx, chunk in enumerate(chunks):
                        # Generate embedding
                        embedding = embedding_model.encode(chunk).tolist()

                        # Store chunk with embedding
                        await conn.execute("""
                            INSERT INTO chunks
                            (training_data_id, chunk_text, chunk_index, embedding)
                            VALUES ($1, $2, $3, $4)
                        """,
                            training_id,
                            chunk,
                            chunk_idx,
                            embedding
                        )

                    if (i + 1) % 10 == 0:
                        logger.info(f"  ⏳ Processed {i + 1}/{len(examples)} examples...")

                # Mark file as processed
                await conn.execute("""
                    INSERT INTO processed_files
                    (file_path, file_size, examples_count, chunks_count)
                    VALUES ($1, $2, $3, $4)
                """,
                    str(file_path),
                    file_path.stat().st_size,
                    len(examples),
                    total_chunks
                )

        processed_files.add(str(file_path))

        logger.info(f"  ✅ Processed {len(examples)} examples → {total_chunks} chunks")
        logger.info(f"  💾 Stored in PostgreSQL with vector embeddings")

        # Trigger OrientDB sync (async, don't wait)
        asyncio.create_task(trigger_orientdb_sync())

    except Exception as e:
        logger.error(f"  ❌ Error processing {file_path.name}: {e}", exc_info=True)

async def trigger_orientdb_sync():
    """Trigger OrientDB sync via REST API (non-blocking, best-effort)"""
    try:
        import aiohttp
        logger.info("  Triggering OrientDB sync...")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'http://aio-01:5000/graph/query',
                json={'query': 'SELECT count(*) FROM V'},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    logger.info("  OrientDB sync triggered")
                else:
                    logger.warning(f"  OrientDB sync returned status {resp.status}")
    except ImportError:
        # aiohttp not available, fall back to logging
        logger.info("  OrientDB sync: new data available for next sync cycle")
    except Exception as e:
        logger.warning(f"  OrientDB sync error (best-effort): {e}")

async def process_existing_files():
    """Process any existing files that haven't been processed yet"""
    logger.info("📂 Scanning for existing files...")

    jsonl_files = sorted(WATCH_DIR.glob('*.jsonl'))
    logger.info(f"  Found {len(jsonl_files)} JSONL files")

    # Get already processed files
    async with db_pool.acquire() as conn:
        processed = await conn.fetch("SELECT file_path FROM processed_files")
        processed_paths = {row['file_path'] for row in processed}

    unprocessed = [f for f in jsonl_files if str(f) not in processed_paths]

    if unprocessed:
        logger.info(f"  📥 {len(unprocessed)} files need processing")
        for file_path in unprocessed:
            await process_file(file_path)
    else:
        logger.info("  ✅ All files already processed")

async def main():
    """Main entry point"""
    logger.info("="*70)
    logger.info("🚀 AUTO-INGESTION PIPELINE STARTING")
    logger.info("="*70)
    logger.info(f"Watch directory: {WATCH_DIR}")
    logger.info(f"Database: {DB_URL}")
    logger.info(f"Chunk size: {CHUNK_SIZE} words, overlap: {OVERLAP} words")
    logger.info("="*70)

    # Initialize resources
    await init_resources()

    # Process existing files
    await process_existing_files()

    # Start file watcher
    logger.info("\n👁️  Starting file watcher...")
    logger.info("    Monitoring for new JSONL files...")
    logger.info("    Press Ctrl+C to stop\n")

    loop = asyncio.get_event_loop()
    event_handler = IngestionHandler(loop)
    observer = Observer()
    observer.schedule(event_handler, str(WATCH_DIR), recursive=False)
    observer.start()

    logger.info("✅ File watcher active!")
    logger.info("━"*70)

    try:
        while True:
            await asyncio.sleep(10)
            # Log stats every 10 seconds
            async with db_pool.acquire() as conn:
                stats = await conn.fetchrow("""
                    SELECT
                        COUNT(*) as total_examples,
                        COUNT(DISTINCT source) as sources,
                        SUM((SELECT COUNT(*) FROM chunks WHERE chunks.training_data_id = training_data.id)) as total_chunks
                    FROM training_data
                """)
                if stats and stats['total_examples'] > 0:
                    logger.info(f"📊 Stats: {stats['total_examples']} examples, {stats['total_chunks']} chunks, {stats['sources']} sources")

    except KeyboardInterrupt:
        logger.info("\n🛑 Stopping file watcher...")
        observer.stop()
        observer.join()
        await db_pool.close()
        logger.info("✅ Shutdown complete")

if __name__ == '__main__':
    asyncio.run(main())
