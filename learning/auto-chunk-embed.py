#!/usr/bin/env python3
"""
Automatic Chunking and Embedding Service

Monitors and chunks:
- Session conversations (every 50 messages)
- Worker solutions (from consensus tasks)
- Arbiter decisions (from consensus results)
- Deep research reports
- Autonomous SDLC artifacts
- PostgreSQL execution logs

Stores in learning.consciousness_research with 768-dim embeddings
"""

import psycopg2
from sentence_transformers import SentenceTransformer
import json
from pathlib import Path
import time
from datetime import datetime

# Configuration
DB_CONFIG = {
    'host': 'laptop-01',
    'database': 'learning',
    'user': 'sfloess',
    'password': 'sfloess'
}

CHUNK_SIZE = 1000  # chars
MODEL_768 = 'sentence-transformers/all-mpnet-base-v2'

class AutoChunkEmbed:
    def __init__(self):
        self.model = None
        self.conn = None
        
    def load_model(self):
        """Load 768-dim embedding model"""
        if not self.model:
            print("Loading embedding model...")
            self.model = SentenceTransformer(MODEL_768)
        return self.model
    
    def get_db(self):
        """Get PostgreSQL connection"""
        if not self.conn or self.conn.closed:
            self.conn = psycopg2.connect(**DB_CONFIG)
        return self.conn
    
    def chunk_text(self, text, chunk_size=CHUNK_SIZE):
        """Split text into chunks"""
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i:i+chunk_size])
        return chunks
    
    def embed_and_store(self, doc_id, chunks, metadata):
        """Embed chunks and store in vectordb"""
        model = self.load_model()
        db = self.get_db()
        cur = db.cursor()
        
        stored = 0
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
                
            # Generate embedding
            embedding = model.encode(chunk).tolist()
            
            # Store
            chunk_id = f"{doc_id}-chunk-{i}"
            chunk_meta = {**metadata, 'chunk_index': i, 'total_chunks': len(chunks)}
            
            try:
                cur.execute("""
                    INSERT INTO learning.consciousness_research 
                    (original_id, embedding, metadata, document)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (original_id) DO UPDATE SET
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata,
                        document = EXCLUDED.document
                """, (chunk_id, embedding, json.dumps(chunk_meta), chunk))
                stored += 1
            except Exception as e:
                print(f"Error storing chunk {i}: {e}")
        
        db.commit()
        return stored
    
    def process_worker_solutions(self):
        """Chunk worker solutions from consensus tasks"""
        # Check for worker output files
        worker_dir = Path('/tmp')
        worker_files = list(worker_dir.glob('w*.txt'))
        
        for wf in worker_files:
            content = wf.read_text()
            if len(content) > 100:  # Skip empty/failed
                chunks = self.chunk_text(content)
                metadata = {
                    'type': 'worker_solution',
                    'file': str(wf),
                    'timestamp': datetime.now().isoformat()
                }
                stored = self.embed_and_store(f"worker-{wf.stem}", chunks, metadata)
                print(f"  Worker {wf.name}: {stored} chunks")
    
    def process_execution_logs(self):
        """Chunk recent execution logs from PostgreSQL"""
        db = self.get_db()
        cur = db.cursor()
        
        # Get recent executions
        cur.execute("""
            SELECT model, workflow, task_type, quality_score, outcome, timestamp
            FROM monitoring.execution_summary
            WHERE timestamp > NOW() - INTERVAL '1 hour'
            ORDER BY timestamp DESC
            LIMIT 100
        """)
        
        logs = cur.fetchall()
        if logs:
            # Create summary document
            doc = "Recent Execution Logs:\n\n"
            for model, workflow, task, quality, outcome, ts in logs:
                doc += f"{ts}: {model} on {workflow} ({task}) -> {outcome} (quality: {quality})\n"
            
            chunks = self.chunk_text(doc)
            metadata = {
                'type': 'execution_logs',
                'count': len(logs),
                'timestamp': datetime.now().isoformat()
            }
            stored = self.embed_and_store(f"exec-logs-{int(time.time())}", chunks, metadata)
            print(f"  Execution logs: {stored} chunks ({len(logs)} entries)")
    
    def process_deep_research(self):
        """Chunk deep research outputs"""
        research_dir = Path('/tmp/claude-1000')
        if research_dir.exists():
            # Find deep-research outputs
            outputs = list(research_dir.glob('**/tasks/*.output'))
            for out in outputs[-5:]:  # Last 5 outputs
                content = out.read_text()
                if 'deep-research' in content or 'Deep research' in content:
                    chunks = self.chunk_text(content)
                    metadata = {
                        'type': 'deep_research',
                        'file': str(out),
                        'timestamp': datetime.now().isoformat()
                    }
                    stored = self.embed_and_store(f"research-{out.stem}", chunks, metadata)
                    print(f"  Research {out.stem}: {stored} chunks")
    
    def run_once(self):
        """Single pass of chunking/embedding"""
        print(f"\n=== Auto-Chunk-Embed: {datetime.now()} ===\n")
        
        try:
            self.process_worker_solutions()
            self.process_execution_logs()
            self.process_deep_research()
            print("\n✅ Chunking complete\n")
        except Exception as e:
            print(f"❌ Error: {e}\n")
    
    def run_daemon(self, interval=300):
        """Run as daemon (every 5 minutes)"""
        print(f"Auto-Chunk-Embed daemon starting (interval: {interval}s)")
        while True:
            self.run_once()
            time.sleep(interval)

if __name__ == '__main__':
    import sys
    
    service = AutoChunkEmbed()
    
    if '--daemon' in sys.argv:
        service.run_daemon()
    else:
        service.run_once()
