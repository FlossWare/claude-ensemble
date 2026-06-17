#!/usr/bin/env python3
"""
Universal Auto-Chunker for Fleet Orchestration

Automatically chunks and embeds EVERYTHING:
- Session conversations (live monitoring)
- Worker solutions (all /tmp/*.txt files)
- Arbiter decisions (consensus results)
- Deep research outputs
- Autonomous SDLC workflows
- PostgreSQL execution logs
- GitLab issues/commits
- Tool outputs
- Error logs

Runs as daemon: python3 universal-chunker.py --daemon
Run once:      python3 universal-chunker.py
"""

import psycopg2
from sentence_transformers import SentenceTransformer
import json
from pathlib import Path
import time
from datetime import datetime
import hashlib
import os

DB_CONFIG = {
    'host': 'aio-01',
    'database': 'learning',
    'user': 'sfloess',
    'password': 'sfloess'
}

CHUNK_SIZE = 800
MODEL = 'sentence-transformers/all-mpnet-base-v2'  # 768-dim

class UniversalChunker:
    def __init__(self):
        self.model = None
        self.conn = None
        self.processed = set()  # Track processed files
        self.load_processed()
        
    def load_processed(self):
        """Load set of already-processed files"""
        cache_file = Path.home() / '.claude/learning/chunked-files.json'
        if cache_file.exists():
            try:
                self.processed = set(json.loads(cache_file.read_text()))
            except:
                pass
    
    def save_processed(self):
        """Save processed files cache"""
        cache_file = Path.home() / '.claude/learning/chunked-files.json'
        cache_file.write_text(json.dumps(list(self.processed)))
    
    def get_model(self):
        if not self.model:
            print("Loading embedding model (768-dim)...")
            self.model = SentenceTransformer(MODEL)
        return self.model
    
    def get_db(self):
        if not self.conn or self.conn.closed:
            self.conn = psycopg2.connect(**DB_CONFIG)
        return self.conn
    
    def chunk_and_embed(self, doc_id, content, metadata):
        """Chunk content, embed, and store"""
        if len(content) < 50:  # Skip tiny content
            return 0
            
        model = self.get_model()
        db = self.get_db()
        cur = db.cursor()
        
        # Create chunks
        chunks = []
        for i in range(0, len(content), CHUNK_SIZE):
            chunk = content[i:i+CHUNK_SIZE].strip()
            if chunk:
                chunks.append(chunk)
        
        stored = 0
        for i, chunk in enumerate(chunks):
            embedding = model.encode(chunk).tolist()
            
            chunk_id = f"{doc_id}-{i}"
            chunk_meta = {
                **metadata,
                'chunk_index': i,
                'total_chunks': len(chunks),
                'timestamp': datetime.now().isoformat()
            }
            
            try:
                cur.execute("""
                    INSERT INTO learning.consciousness_research 
                    (original_id, embedding, metadata, document)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (original_id) DO UPDATE SET
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata,
                        document = EXCLUDED.document,
                        timestamp = CURRENT_TIMESTAMP
                """, (chunk_id, embedding, json.dumps(chunk_meta), chunk))
                stored += 1
            except Exception as e:
                print(f"  Error storing {chunk_id}: {e}")
        
        db.commit()
        return stored
    
    def process_worker_outputs(self):
        """Process all worker output files in /tmp"""
        count = 0
        for pattern in ['w*.txt', 'fleet-w*.txt', 'worker*.txt']:
            for f in Path('/tmp').glob(pattern):
                file_key = str(f)
                if file_key in self.processed:
                    continue
                    
                try:
                    content = f.read_text()
                    if len(content) > 100:
                        stored = self.chunk_and_embed(
                            f"worker-{f.stem}",
                            content,
                            {'type': 'worker_solution', 'file': str(f)}
                        )
                        if stored > 0:
                            print(f"  Worker {f.name}: {stored} chunks")
                            self.processed.add(file_key)
                            count += stored
                except Exception as e:
                    print(f"  Error processing {f}: {e}")
        return count
    
    def process_task_outputs(self):
        """Process all task output files"""
        count = 0
        task_dir = Path('/tmp/claude-1000')
        
        if task_dir.exists():
            for out in task_dir.glob('**/tasks/*.output'):
                file_key = str(out)
                if file_key in self.processed:
                    continue
                
                try:
                    content = out.read_text()
                    if len(content) > 200:
                        # Determine type
                        doc_type = 'task_output'
                        if 'deep-research' in content.lower():
                            doc_type = 'deep_research'
                        elif 'consensus' in content.lower():
                            doc_type = 'consensus_result'
                        elif 'autonomous' in content.lower():
                            doc_type = 'autonomous_sdlc'
                        
                        stored = self.chunk_and_embed(
                            f"task-{out.stem}",
                            content,
                            {'type': doc_type, 'file': str(out)}
                        )
                        if stored > 0:
                            print(f"  Task {out.stem}: {stored} chunks ({doc_type})")
                            self.processed.add(file_key)
                            count += stored
                except Exception as e:
                    print(f"  Error processing {out}: {e}")
        return count
    
    def process_execution_logs(self):
        """Process PostgreSQL execution logs"""
        try:
            db = self.get_db()
            cur = db.cursor()
            
            # Get recent logs not yet embedded
            cur.execute("""
                SELECT model, workflow, task_type, quality_score, outcome, 
                       duration_ms, input_tokens, output_tokens, timestamp
                FROM monitoring.execution_summary
                WHERE timestamp > NOW() - INTERVAL '6 hours'
                ORDER BY timestamp DESC
                LIMIT 200
            """)
            
            logs = cur.fetchall()
            if not logs:
                return 0
            
            # Create document
            doc = "Recent Fleet Execution Logs:\n\n"
            for row in logs:
                model, workflow, task, quality, outcome, dur, inp, outp, ts = row
                doc += f"{ts}: {model} | {workflow} | {task} -> {outcome} "
                doc += f"(quality: {quality}, {dur}ms, {inp}→{outp} tokens)\n"
            
            stored = self.chunk_and_embed(
                f"exec-logs-{int(time.time())}",
                doc,
                {'type': 'execution_logs', 'count': len(logs)}
            )
            
            if stored > 0:
                print(f"  Execution logs: {stored} chunks ({len(logs)} entries)")
            return stored
            
        except Exception as e:
            print(f"  Error processing execution logs: {e}")
            return 0
    
    def process_sessions(self):
        """Process recent session JSONL files"""
        count = 0
        session_dir = Path.home() / '.claude/projects/-home-sfloess-Development-redhat-scm-gitlab-cee-sfloess-claude-global-skills'
        
        if session_dir.exists():
            # Get most recent 3 sessions
            sessions = sorted(session_dir.glob('*.jsonl'), key=lambda f: f.stat().st_mtime, reverse=True)[:3]
            
            for sess in sessions:
                file_key = str(sess)
                if file_key in self.processed:
                    continue
                
                try:
                    # Read and parse session
                    lines = sess.read_text().split('\n')
                    content = '\n'.join(lines[:50])  # First 50 lines as sample
                    
                    if len(content) > 500:
                        stored = self.chunk_and_embed(
                            f"session-{sess.stem[:8]}",
                            content,
                            {'type': 'session', 'file': str(sess)}
                        )
                        if stored > 0:
                            print(f"  Session {sess.stem[:16]}...: {stored} chunks")
                            self.processed.add(file_key)
                            count += stored
                except Exception as e:
                    print(f"  Error processing {sess}: {e}")
        return count
    
    def run_once(self):
        """Single processing pass"""
        print(f"\n{'='*60}")
        print(f"Universal Chunker: {datetime.now()}")
        print(f"{'='*60}\n")
        
        total = 0
        
        print("Processing worker outputs...")
        total += self.process_worker_outputs()
        
        print("Processing task outputs...")
        total += self.process_task_outputs()
        
        print("Processing execution logs...")
        total += self.process_execution_logs()
        
        print("Processing sessions...")
        total += self.process_sessions()
        
        self.save_processed()
        
        print(f"\n{'='*60}")
        print(f"✅ Total chunks stored: {total}")
        print(f"{'='*60}\n")
        
        return total
    
    def run_daemon(self, interval=300):
        """Run as background daemon"""
        print(f"Universal Chunker daemon starting (interval: {interval}s)")
        print(f"Vectordb: {DB_CONFIG['host']}/{DB_CONFIG['database']}")
        print(f"Model: {MODEL} (768-dim)\n")
        
        while True:
            try:
                self.run_once()
            except Exception as e:
                print(f"❌ Error in chunker: {e}\n")
            
            time.sleep(interval)

if __name__ == '__main__':
    import sys
    
    chunker = UniversalChunker()
    
    if '--daemon' in sys.argv:
        chunker.run_daemon()
    else:
        chunker.run_once()
