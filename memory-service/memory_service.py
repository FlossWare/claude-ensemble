#!/usr/bin/env python3
"""
RH Memory Service Daemon

Central memory authority for all Claude Code sessions.
Runs as systemd user service, listens on a private Unix socket.
Handles concurrent access, memory operations, and path validation.
"""

import json
import logging
import math
import os
import re
import socket
import stat
import sys
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Allow execution from the repository without requiring package installation.
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.runtime_config import log_dir, memory_dir, runtime_dir, socket_path


RUNTIME_SUBDIR = "claude-ensemble"
SOCKET_FILENAME = "memory.sock"
MEMORY_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def get_runtime_dir() -> Path:
    """Return and harden the per-user runtime directory."""
    xdg_runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    base_dir = Path(xdg_runtime_dir) if xdg_runtime_dir else Path.home() / ".cache"
    runtime_dir = base_dir / RUNTIME_SUBDIR
    runtime_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(runtime_dir, 0o700)
    return runtime_dir


def get_socket_path() -> Path:
    """Return the private memory service socket path."""
    return get_runtime_dir() / SOCKET_FILENAME


def validate_memory_name(name: str) -> str:
    """Validate a memory name before using it as part of a filesystem path."""
    if not isinstance(name, str) or not MEMORY_NAME_PATTERN.fullmatch(name) or name in (
        "..",
        ".",
    ):
        raise ValueError(
            "Invalid memory name: use only letters, numbers, '.', '_' and '-'; not '.' or '..'"
        )
    return name


MEMORY_DIR = memory_dir()
SOCKET_PATH = socket_path(
    "ENSEMBLE_MEMORY_SOCKET", str(runtime_dir() / "memory.sock")
)
LOG_DIR = log_dir()
LOG_DIR.mkdir(parents=True, exist_ok=True)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "claude-memory.log"),
    ],
)
logger = logging.getLogger(__name__)


class MemoryStore:
    """Thread-safe memory file operations."""

    def __init__(self, memory_dir: Path, chunk_size: int = 500):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.chunk_size = chunk_size

    def _memory_path(self, name: str, suffix: str) -> Path:
        """Build a validated memory path."""
        validate_memory_name(name)
        path = self.memory_dir / f"{name}{suffix}"
        resolved_root = self.memory_dir.resolve()
        resolved_path = path.resolve()
        if resolved_path.parent != resolved_root:
            raise ValueError("Memory path escapes the configured memory directory")
        return path

    def read_file(self, name: str) -> Optional[str]:
        """Read a memory file."""
        path = self._memory_path(name, ".md")
        if not path.exists():
            return None
        try:
            with open(path, "r") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading {name}: {e}")
            return None

    def write_file(self, name: str, content: str) -> bool:
        """Write a memory file."""
        path = self._memory_path(name, ".md")
        try:
            with self.lock:
                with open(path, "w") as f:
                    f.write(content)
            logger.info(f"Wrote memory: {name}")
            return True
        except Exception as e:
            logger.error(f"Error writing {name}: {e}")
            return False

    def append_entry(self, name: str, entry: Dict[str, Any]) -> bool:
        """Append entry to a memory file (JSONL style)."""
        path = self._memory_path(name, ".jsonl")
        try:
            with self.lock:
                with open(path, "a") as f:
                    entry["timestamp"] = datetime.utcnow().isoformat()
                    f.write(json.dumps(entry) + "\n")
            logger.info(f"Appended to {name}")
            return True
        except Exception as e:
            logger.error(f"Error appending to {name}: {e}")
            return False

    def read_entries(self, name: str) -> List[Dict[str, Any]]:
        """Read persisted JSONL records without interpreting their semantics."""
        path = self._memory_path(name, ".jsonl")
        if not path.exists():
            return []
        entries: List[Dict[str, Any]] = []
        try:
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entries.append(json.loads(line))
        except Exception as e:
            logger.error(f"Error reading entries from {name}: {e}")
        return entries

    def list_files(self) -> List[str]:
        """List all memory files."""
        return [f.stem for f in self.memory_dir.glob("*.md")]

    def vectorize_text(self, text: str) -> Dict[str, float]:
        """Convert text to TF-IDF vector (local, no API calls)."""
        terms = [
            word.strip(".,!?;:").lower()
            for word in text.split()
            if len(word) > 2
        ]
        term_freq = Counter(terms)
        doc_length = len(terms)
        vector = {}
        for term, freq in term_freq.items():
            vector[term] = freq / max(doc_length, 1)
        return vector

    def cosine_similarity(
        self, vec1: Dict[str, float], vec2: Dict[str, float]
    ) -> float:
        """Calculate cosine similarity between two vectors."""
        all_terms = set(vec1.keys()) | set(vec2.keys())
        if not all_terms:
            return 0.0
        dot_product = sum(
            vec1.get(term, 0) * vec2.get(term, 0) for term in all_terms
        )
        mag1 = math.sqrt(sum(v**2 for v in vec1.values()))
        mag2 = math.sqrt(sum(v**2 for v in vec2.values()))
        if mag1 == 0 or mag2 == 0:
            return 0.0
        return dot_product / (mag1 * mag2)

    def search_semantic(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Semantic search using cosine similarity on vectors."""
        query_vector = self.vectorize_text(query)
        results = []
        for md_file in self.memory_dir.glob("*.md"):
            try:
                file_name = md_file.stem
                chunks = self.chunk_document(file_name)
                if not chunks:
                    with open(md_file, "r") as f:
                        content = f.read()
                    chunks = [{"content": content, "header": "full"}]
                for chunk in chunks:
                    content = chunk.get("content", "")
                    header = chunk.get("header", "")
                    chunk_vector = self.vectorize_text(content)
                    similarity = self.cosine_similarity(query_vector, chunk_vector)
                    if similarity > 0.1:
                        results.append(
                            {
                                "file": file_name,
                                "section": header,
                                "score": similarity,
                                "size_bytes": len(content),
                            }
                        )
            except Exception as e:
                logger.debug(f"Error searching {md_file}: {e}")
        return sorted(results, key=lambda x: x["score"], reverse=True)[:top_k]

    def chunk_document(self, name: str) -> List[Dict[str, Any]]:
        """Chunk a document by headers (semantic chunking)."""
        file_path = self._memory_path(name, ".md")
        if not file_path.exists():
            return []
        try:
            with open(file_path, "r") as f:
                lines = f.readlines()
            chunks = []
            current_chunk = []
            current_header = "intro"
            max_chunk_size = 2000
            for i, line in enumerate(lines):
                if line.startswith("#"):
                    if current_chunk:
                        chunks.append(
                            {
                                "header": current_header,
                                "start_line": i - len(current_chunk),
                                "end_line": i,
                                "content": "".join(current_chunk),
                                "size": sum(len(l) for l in current_chunk),
                            }
                        )
                    current_header = line.lstrip("#").strip()
                    current_chunk = [line]
                else:
                    current_chunk.append(line)
                    if sum(len(l) for l in current_chunk) > max_chunk_size:
                        chunks.append(
                            {
                                "header": current_header,
                                "start_line": i - len(current_chunk) + 1,
                                "end_line": i + 1,
                                "content": "".join(current_chunk),
                                "size": sum(len(l) for l in current_chunk),
                            }
                        )
                        current_chunk = []
            if current_chunk:
                chunks.append(
                    {
                        "header": current_header,
                        "start_line": len(lines) - len(current_chunk),
                        "end_line": len(lines),
                        "content": "".join(current_chunk),
                        "size": sum(len(l) for l in current_chunk),
                    }
                )
            return chunks
        except Exception as e:
            logger.debug(f"Error chunking {name}: {e}")
            return []

    def search(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """Search memory files using TF-IDF + keyword matching on chunks."""
        results = []
        keyword_set = {kw.lower() for kw in keywords}
        all_docs = []
        for md_file in self.memory_dir.glob("*.md"):
            try:
                with open(md_file, "r") as f:
                    content = f.read().lower()
                    terms = set(
                        word.strip(".,!?;:")
                        for word in content.split()
                        if len(word) > 2
                    )
                    all_docs.append(terms)
            except Exception:
                pass
        doc_count = len(all_docs)
        idf_scores = {}
        for kw in keyword_set:
            docs_with_kw = sum(1 for doc in all_docs if kw in doc)
            idf_scores[kw] = math.log(doc_count / docs_with_kw) if docs_with_kw else 0
        for md_file in self.memory_dir.glob("*.md"):
            try:
                file_name = md_file.stem
                chunks = self.chunk_document(file_name)
                if not chunks:
                    with open(md_file, "r") as f:
                        content = f.read()
                    chunks = [{"content": content, "header": "full"}]
                for chunk in chunks:
                    content = chunk.get("content", "").lower()
                    header = chunk.get("header", "")
                    terms = [
                        word.strip(".,!?;:").lower()
                        for word in content.split()
                        if len(word) > 2
                    ]
                    term_freq = Counter(terms)
                    doc_length = len(terms)
                    score = 0
                    matched_kw = []
                    for kw in keyword_set:
                        if kw in term_freq:
                            tf = term_freq[kw] / max(doc_length, 1)
                            score += tf * idf_scores.get(kw, 0)
                            matched_kw.append(kw)
                    if score > 0:
                        results.append(
                            {
                                "file": file_name,
                                "section": header,
                                "score": score,
                                "matched_keywords": len(matched_kw),
                                "size_bytes": len(content),
                            }
                        )
            except Exception as e:
                logger.debug(f"Error searching {md_file}: {e}")
        return sorted(results, key=lambda x: x["score"], reverse=True)[:10]


class MemoryService:
    """Memory service daemon."""

    def __init__(self, socket_path: Path, memory_dir: Path):
        self.socket_path = Path(socket_path)
        self.store = MemoryStore(memory_dir)
        self.socket = None

    def _prepare_socket_path(self) -> None:
        """Create a private parent directory and safely remove a stale socket."""
        self.socket_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.socket_path.parent, 0o700)

        if not self.socket_path.exists():
            return

        socket_stat = self.socket_path.stat()
        if socket_stat.st_uid != os.getuid() or not stat.S_ISSOCK(socket_stat.st_mode):
            raise RuntimeError(
                f"Refusing to remove unexpected socket path: {self.socket_path}"
            )
        self.socket_path.unlink()

    def start(self):
        """Start the service."""
        logger.info("Starting Claude Ensemble memory service")
        self._prepare_socket_path()

        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        previous_umask = os.umask(0o077)
        try:
            self.socket.bind(str(self.socket_path))
        finally:
            os.umask(previous_umask)

        os.chmod(self.socket_path, 0o600)
        self.socket.listen(5)
        self.socket.settimeout(None)

        logger.info(f"Listening on {self.socket_path}")

        try:
            while True:
                conn, _ = self.socket.accept()
                thread = threading.Thread(
                    target=self._handle_client, args=(conn,), daemon=True
                )
                thread.start()
        except KeyboardInterrupt:
            logger.info("Shutting down")
            self.stop()
        except Exception as e:
            logger.error(f"Service error: {e}")
            self.stop()

    def stop(self):
        """Stop the service."""
        if self.socket:
            self.socket.close()
        if self.socket_path.exists():
            try:
                socket_stat = self.socket_path.stat()
                if (
                    socket_stat.st_uid == os.getuid()
                    and stat.S_ISSOCK(socket_stat.st_mode)
                ):
                    self.socket_path.unlink()
            except FileNotFoundError:
                pass
        logger.info("Memory service stopped")

    def _handle_client(self, conn: socket.socket):
        """Handle client request."""
        try:
            conn.settimeout(5.0)
            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break

            request_str = data.decode("utf-8").strip()
            if not request_str:
                return

            response = self._process_request(request_str)
            conn.sendall((response + "\n").encode("utf-8"))
        except socket.timeout:
            logger.debug("Client timeout")
            try:
                conn.sendall(b'{"ok": false, "error": "timeout"}\n')
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Client error: {e}")
            try:
                conn.sendall(b'{"ok": false, "error": "server error"}\n')
            except Exception:
                pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _process_request(self, request: str) -> str:
        """Process a request, return JSON response."""
        try:
            req_data = json.loads(request)
            operation = req_data.get("op")

            if operation == "read":
                name = req_data.get("name")
                content = self.store.read_file(name)
                return json.dumps({"ok": content is not None, "content": content})

            if operation == "write":
                name = req_data.get("name")
                content = req_data.get("content")
                success = self.store.write_file(name, content)
                return json.dumps({"ok": success})

            if operation == "append":
                name = req_data.get("name")
                entry = req_data.get("entry", {})
                success = self.store.append_entry(name, entry)
                return json.dumps({"ok": success})

            if operation == "entries":
                name = req_data.get("name")
                validate_memory_name(name)
                entries = self.store.read_entries(name)
                return json.dumps({"ok": True, "entries": entries})

            if operation == "list":
                return json.dumps({"ok": True, "files": self.store.list_files()})

            if operation == "search":
                keywords = req_data.get("keywords", [])
                results = self.store.search(keywords)
                return json.dumps({"ok": True, "results": results})

            if operation == "chunk":
                name = req_data.get("name")
                chunks = self.store.chunk_document(name)
                return json.dumps({"ok": True, "chunks": chunks})

            if operation == "search_semantic":
                query = req_data.get("query", "")
                top_k = req_data.get("top_k", 10)
                results = self.store.search_semantic(query, top_k)
                return json.dumps({"ok": True, "results": results})

            if operation == "search_hybrid":
                query = req_data.get("query", "")
                keywords = query.lower().split()
                top_k = req_data.get("top_k", 10)
                keyword_results = self.store.search(keywords)
                semantic_results = self.store.search_semantic(query, top_k)
                merged = {}
                for result in keyword_results:
                    key = (result["file"], result.get("section", "full"))
                    merged.setdefault(key, {"keyword_score": 0, "semantic_score": 0})
                    merged[key]["keyword_score"] = result["score"]
                for result in semantic_results:
                    key = (result["file"], result.get("section", "full"))
                    merged.setdefault(key, {"keyword_score": 0, "semantic_score": 0})
                    merged[key]["semantic_score"] = result["score"]
                results = []
                for (file, section), scores in merged.items():
                    combined_score = (
                        0.4 * scores["keyword_score"] + 0.6 * scores["semantic_score"]
                    )
                    results.append(
                        {
                            "file": file,
                            "section": section,
                            "score": combined_score,
                            "keyword_score": scores["keyword_score"],
                            "semantic_score": scores["semantic_score"],
                        }
                    )
                results = sorted(results, key=lambda x: x["score"], reverse=True)[:top_k]
                return json.dumps({"ok": True, "results": results})

            if operation == "ping":
                return json.dumps({"ok": True, "message": "pong"})

            return json.dumps({"ok": False, "error": f"Unknown operation: {operation}"})
        except json.JSONDecodeError:
            return json.dumps({"ok": False, "error": "Invalid JSON"})
        except Exception as e:
            logger.error(f"Request error: {e}")
            return json.dumps({"ok": False, "error": str(e)})


if __name__ == "__main__":
    service = MemoryService(SOCKET_PATH, MEMORY_DIR)
    service.start()
