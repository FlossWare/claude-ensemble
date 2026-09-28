#!/usr/bin/env python3
"""
RH Memory Service Daemon

Central memory authority for all Claude Code sessions.
Runs as systemd user service, listens on Unix socket.
Handles concurrent access, file locking, memory operations.
"""

import json
import logging
import socket
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import threading
import re
import math
from collections import Counter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path.home() / '.claude' / 'rh-memory-service.log')
    ]
)
logger = logging.getLogger(__name__)

MEMORY_DIR = Path.home() / '.claude' / 'projects' / '-home-sfloess' / 'memory'
SOCKET_PATH = Path('/tmp/rh-memory.sock')


class MemoryStore:
    """Thread-safe memory file operations"""

    def __init__(self, memory_dir: Path, chunk_size: int = 500):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.chunk_size = chunk_size  # Lines per chunk

    def read_file(self, name: str) -> Optional[str]:
        """Read a memory file"""
        path = self.memory_dir / f"{name}.md"

        if not path.exists():
            return None

        try:
            with open(path, 'r') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading {name}: {e}")
            return None

    def write_file(self, name: str, content: str) -> bool:
        """Write a memory file"""
        path = self.memory_dir / f"{name}.md"

        try:
            with self.lock:
                with open(path, 'w') as f:
                    f.write(content)
            logger.info(f"Wrote memory: {name}")
            return True
        except Exception as e:
            logger.error(f"Error writing {name}: {e}")
            return False

    def append_entry(self, name: str, entry: Dict[str, Any]) -> bool:
        """Append entry to a memory file (JSONL style)"""
        path = self.memory_dir / f"{name}.jsonl"

        try:
            with self.lock:
                with open(path, 'a') as f:
                    entry['timestamp'] = datetime.utcnow().isoformat()
                    f.write(json.dumps(entry) + '\n')
            logger.info(f"Appended to {name}")
            return True
        except Exception as e:
            logger.error(f"Error appending to {name}: {e}")
            return False

    def list_files(self) -> List[str]:
        """List all memory files"""
        return [f.stem for f in self.memory_dir.glob('*.md')]

    def vectorize_text(self, text: str) -> Dict[str, float]:
        """Convert text to TF-IDF vector (local, no API calls)"""
        # Tokenize
        terms = [word.strip('.,!?;:').lower() for word in text.split() if len(word) > 2]
        term_freq = Counter(terms)
        doc_length = len(terms)

        # Normalize TF
        vector = {}
        for term, freq in term_freq.items():
            tf = freq / max(doc_length, 1)
            vector[term] = tf

        return vector

    def cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """Calculate cosine similarity between two vectors"""
        # Get all unique terms
        all_terms = set(vec1.keys()) | set(vec2.keys())

        if not all_terms:
            return 0.0

        # Dot product
        dot_product = sum(vec1.get(term, 0) * vec2.get(term, 0) for term in all_terms)

        # Magnitudes
        mag1 = math.sqrt(sum(v**2 for v in vec1.values()))
        mag2 = math.sqrt(sum(v**2 for v in vec2.values()))

        if mag1 == 0 or mag2 == 0:
            return 0.0

        return dot_product / (mag1 * mag2)

    def search_semantic(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Semantic search using cosine similarity on vectors"""
        query_vector = self.vectorize_text(query)

        results = []
        for md_file in self.memory_dir.glob('*.md'):
            try:
                file_name = md_file.stem

                # Get chunks
                chunks = self.chunk_document(file_name)
                if not chunks:
                    with open(md_file, 'r') as f:
                        content = f.read()
                    chunks = [{'content': content, 'header': 'full'}]

                # Score each chunk
                for chunk in chunks:
                    content = chunk.get('content', '')
                    header = chunk.get('header', '')

                    # Vectorize chunk
                    chunk_vector = self.vectorize_text(content)

                    # Semantic similarity
                    similarity = self.cosine_similarity(query_vector, chunk_vector)

                    if similarity > 0.1:  # Threshold to filter noise
                        results.append({
                            'file': file_name,
                            'section': header,
                            'score': similarity,
                            'size_bytes': len(content)
                        })
            except Exception as e:
                logger.debug(f"Error searching {md_file}: {e}")

        return sorted(results, key=lambda x: x['score'], reverse=True)[:top_k]

    def chunk_document(self, name: str) -> List[Dict[str, Any]]:
        """Chunk a document by headers (semantic chunking)"""
        file_path = self.memory_dir / f"{name}.md"
        if not file_path.exists():
            return []

        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()

            chunks = []
            current_chunk = []
            current_header = 'intro'
            max_chunk_size = 2000

            for i, line in enumerate(lines):
                if line.startswith('#'):
                    # Save previous chunk
                    if current_chunk:
                        chunks.append({
                            'header': current_header,
                            'start_line': i - len(current_chunk),
                            'end_line': i,
                            'content': ''.join(current_chunk),
                            'size': sum(len(l) for l in current_chunk)
                        })
                    current_header = line.lstrip('#').strip()
                    current_chunk = [line]
                else:
                    current_chunk.append(line)

                    # Split if too large
                    if sum(len(l) for l in current_chunk) > max_chunk_size:
                        chunks.append({
                            'header': current_header,
                            'start_line': i - len(current_chunk) + 1,
                            'end_line': i + 1,
                            'content': ''.join(current_chunk),
                            'size': sum(len(l) for l in current_chunk)
                        })
                        current_chunk = []

            # Add remaining
            if current_chunk:
                chunks.append({
                    'header': current_header,
                    'start_line': len(lines) - len(current_chunk),
                    'end_line': len(lines),
                    'content': ''.join(current_chunk),
                    'size': sum(len(l) for l in current_chunk)
                })

            return chunks
        except Exception as e:
            logger.debug(f"Error chunking {name}: {e}")
            return []

    def search(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """Search memory files using TF-IDF + keyword matching on chunks"""
        import math
        from collections import Counter

        results = []
        keyword_set = {kw.lower() for kw in keywords}

        # Build document corpus for IDF calculation
        all_docs = []
        for md_file in self.memory_dir.glob('*.md'):
            try:
                with open(md_file, 'r') as f:
                    content = f.read().lower()
                    # Split into terms
                    terms = set(word.strip('.,!?;:') for word in content.split() if len(word) > 2)
                    all_docs.append(terms)
            except:
                pass

        # Calculate IDF for each keyword
        doc_count = len(all_docs)
        idf_scores = {}
        for kw in keyword_set:
            docs_with_kw = sum(1 for doc in all_docs if kw in doc)
            if docs_with_kw > 0:
                idf_scores[kw] = math.log(doc_count / docs_with_kw)
            else:
                idf_scores[kw] = 0

        # Score each document and its chunks
        for md_file in self.memory_dir.glob('*.md'):
            try:
                file_name = md_file.stem

                # Get chunks for this document
                chunks = self.chunk_document(file_name)
                if not chunks:
                    # Fall back to full document
                    with open(md_file, 'r') as f:
                        content = f.read()
                    chunks = [{'content': content, 'header': 'full'}]

                # Score each chunk
                for chunk in chunks:
                    content = chunk.get('content', '').lower()
                    header = chunk.get('header', '')

                    # TF calculation
                    terms = [word.strip('.,!?;:').lower() for word in content.split() if len(word) > 2]
                    term_freq = Counter(terms)
                    doc_length = len(terms)

                    # TF-IDF score
                    score = 0
                    matched_kw = []
                    for kw in keyword_set:
                        if kw in term_freq:
                            tf = term_freq[kw] / max(doc_length, 1)
                            idf = idf_scores.get(kw, 0)
                            score += tf * idf
                            matched_kw.append(kw)

                    if score > 0:
                        results.append({
                            'file': file_name,
                            'section': header,
                            'score': score,
                            'matched_keywords': len(matched_kw),
                            'size_bytes': len(content)
                        })
            except Exception as e:
                logger.debug(f"Error searching {md_file}: {e}")

        return sorted(results, key=lambda x: x['score'], reverse=True)[:10]  # Top 10


class MemoryService:
    """Memory service daemon"""

    def __init__(self, socket_path: Path, memory_dir: Path):
        self.socket_path = Path(socket_path)
        self.store = MemoryStore(memory_dir)
        self.socket = None

    def start(self):
        """Start the service"""
        logger.info("Starting RH Memory Service")

        # Clean up old socket if it exists
        if self.socket_path.exists():
            self.socket_path.unlink()

        # Create Unix domain socket
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(str(self.socket_path))
        self.socket.listen(5)
        self.socket.settimeout(None)

        logger.info(f"Listening on {self.socket_path}")

        try:
            while True:
                conn, _ = self.socket.accept()
                thread = threading.Thread(target=self._handle_client, args=(conn,), daemon=True)
                thread.start()
        except KeyboardInterrupt:
            logger.info("Shutting down")
            self.stop()
        except Exception as e:
            logger.error(f"Service error: {e}")
            self.stop()

    def stop(self):
        """Stop the service"""
        if self.socket:
            self.socket.close()
        if self.socket_path.exists():
            self.socket_path.unlink()
        logger.info("Memory service stopped")

    def _handle_client(self, conn: socket.socket):
        """Handle client request"""
        try:
            conn.settimeout(5.0)
            # Read request (ends with newline)
            data = b''
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b'\n' in data:  # End of request
                    break

            request_str = data.decode('utf-8').strip()
            if not request_str:
                return

            response = self._process_request(request_str)

            # Send response
            conn.sendall((response + '\n').encode('utf-8'))
        except socket.timeout:
            logger.debug("Client timeout")
            try:
                conn.sendall(b'{"ok": false, "error": "timeout"}\n')
            except:
                pass
        except Exception as e:
            logger.error(f"Client error: {e}")
            try:
                conn.sendall(b'{"ok": false, "error": "server error"}\n')
            except:
                pass
        finally:
            try:
                conn.close()
            except:
                pass

    def _process_request(self, request: str) -> str:
        """Process a request, return JSON response"""
        try:
            req_data = json.loads(request)
            operation = req_data.get('op')

            if operation == 'read':
                name = req_data.get('name')
                content = self.store.read_file(name)
                return json.dumps({'ok': content is not None, 'content': content})

            elif operation == 'write':
                name = req_data.get('name')
                content = req_data.get('content')
                success = self.store.write_file(name, content)
                return json.dumps({'ok': success})

            elif operation == 'append':
                name = req_data.get('name')
                entry = req_data.get('entry', {})
                success = self.store.append_entry(name, entry)
                return json.dumps({'ok': success})

            elif operation == 'list':
                files = self.store.list_files()
                return json.dumps({'ok': True, 'files': files})

            elif operation == 'search':
                keywords = req_data.get('keywords', [])
                results = self.store.search(keywords)
                return json.dumps({'ok': True, 'results': results})

            elif operation == 'chunk':
                name = req_data.get('name')
                chunks = self.store.chunk_document(name)
                return json.dumps({'ok': True, 'chunks': chunks})

            elif operation == 'search_semantic':
                query = req_data.get('query', '')
                top_k = req_data.get('top_k', 10)
                results = self.store.search_semantic(query, top_k)
                return json.dumps({'ok': True, 'results': results})

            elif operation == 'search_hybrid':
                # Combine TF-IDF keyword search + semantic search
                query = req_data.get('query', '')
                keywords = query.lower().split()
                top_k = req_data.get('top_k', 10)

                # Get both result sets
                keyword_results = self.store.search(keywords)
                semantic_results = self.store.search_semantic(query, top_k)

                # Merge and deduplicate by file+section
                merged = {}
                for r in keyword_results:
                    key = (r['file'], r.get('section', 'full'))
                    if key not in merged:
                        merged[key] = {'keyword_score': 0, 'semantic_score': 0}
                    merged[key]['keyword_score'] = r['score']

                for r in semantic_results:
                    key = (r['file'], r.get('section', 'full'))
                    if key not in merged:
                        merged[key] = {'keyword_score': 0, 'semantic_score': 0}
                    merged[key]['semantic_score'] = r['score']

                # Combine scores (0.4 keyword + 0.6 semantic = emphasis on meaning)
                results = []
                for (file, section), scores in merged.items():
                    combined_score = (0.4 * scores['keyword_score']) + (0.6 * scores['semantic_score'])
                    results.append({
                        'file': file,
                        'section': section,
                        'score': combined_score,
                        'keyword_score': scores['keyword_score'],
                        'semantic_score': scores['semantic_score']
                    })

                results = sorted(results, key=lambda x: x['score'], reverse=True)[:top_k]
                return json.dumps({'ok': True, 'results': results})

            elif operation == 'ping':
                return json.dumps({'ok': True, 'message': 'pong'})

            else:
                return json.dumps({'ok': False, 'error': f'Unknown operation: {operation}'})

        except json.JSONDecodeError:
            return json.dumps({'ok': False, 'error': 'Invalid JSON'})
        except Exception as e:
            logger.error(f"Request error: {e}")
            return json.dumps({'ok': False, 'error': str(e)})


if __name__ == '__main__':
    service = MemoryService(SOCKET_PATH, MEMORY_DIR)
    service.start()
