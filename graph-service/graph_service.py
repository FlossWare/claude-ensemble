#!/usr/bin/env python3
"""Claude Ensemble graph service with a real HTTP boundary.

The graph is intentionally small and dependency-free.  It provides durable,
thread-safe graph mutations and read operations over HTTP.  The service is
local by default; federation belongs to a later recovery issue.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


MAX_REQUEST_BYTES = 1_048_576
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8766


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _stable_id(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest}"


class GraphStore:
    """Thread-safe durable graph store backed by one JSON file."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.lock = threading.RLock()
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        with self.lock:
            if not self.path.exists():
                return
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict) or not isinstance(data.get("nodes", {}), dict) or not isinstance(data.get("edges", {}), dict):
                raise ValueError(f"Invalid graph store: {self.path}")
            self.nodes = data["nodes"]
            self.edges = data["edges"]

    def _persist(
        self,
        nodes: dict[str, dict[str, Any]] | None = None,
        edges: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "nodes": self.nodes if nodes is None else nodes,
            "edges": self.edges if edges is None else edges,
        }
        fd, tmp_name = tempfile.mkstemp(prefix=".graph-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
            dir_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except Exception:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise

    def add_node(self, node_type: str, properties: dict[str, Any], node_id: str | None = None) -> dict[str, Any]:
        if not isinstance(node_type, str) or not node_type:
            raise ValueError("node_type must be a non-empty string")
        if not isinstance(properties, dict):
            raise ValueError("properties must be an object")
        with self.lock:
            identity = {"type": node_type, "properties": properties}
            node_id = node_id or _stable_id("node", identity)
            existing = self.nodes.get(node_id)
            node = {"id": node_id, "type": node_type, "properties": properties}
            if existing is not None and existing != node:
                raise ValueError(f"node id already exists with different content: {node_id}")
            if existing is None:
                proposed_nodes = dict(self.nodes)
                proposed_nodes[node_id] = node
                self._persist(proposed_nodes, self.edges)
                self.nodes = proposed_nodes
            return dict(node)

    def add_edge(
        self,
        source: str,
        target: str,
        edge_type: str,
        properties: dict[str, Any],
        edge_id: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(source, str) or not source:
            raise ValueError("source must be a non-empty string")
        if not isinstance(target, str) or not target:
            raise ValueError("target must be a non-empty string")
        if not isinstance(edge_type, str) or not edge_type:
            raise ValueError("edge_type must be a non-empty string")
        if not isinstance(properties, dict):
            raise ValueError("properties must be an object")
        with self.lock:
            if source not in self.nodes or target not in self.nodes:
                raise KeyError("source and target nodes must exist")
            identity = {
                "source": source,
                "target": target,
                "type": edge_type,
                "properties": properties,
            }
            edge_id = edge_id or _stable_id("edge", identity)
            existing = self.edges.get(edge_id)
            edge = {
                "id": edge_id,
                "source": source,
                "target": target,
                "type": edge_type,
                "properties": properties,
            }
            if existing is not None and existing != edge:
                raise ValueError(f"edge id already exists with different content: {edge_id}")
            if existing is None:
                proposed_edges = dict(self.edges)
                proposed_edges[edge_id] = edge
                self._persist(self.nodes, proposed_edges)
                self.edges = proposed_edges
            return dict(edge)

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        with self.lock:
            node = self.nodes.get(node_id)
            return dict(node) if node is not None else None

    def query(self, node_type: str | None, properties: dict[str, Any]) -> list[dict[str, Any]]:
        if not isinstance(properties, dict):
            raise ValueError("properties must be an object")
        with self.lock:
            result = []
            for node in self.nodes.values():
                if node_type is not None and node["type"] != node_type:
                    continue
                if all(node["properties"].get(key) == value for key, value in properties.items()):
                    result.append(dict(node))
            return sorted(result, key=lambda node: node["id"])

    def traverse(
        self,
        start: str,
        direction: str = "out",
        max_depth: int = 1,
        edge_type: str | None = None,
    ) -> list[dict[str, Any]]:
        if direction not in {"out", "in", "both"}:
            raise ValueError("direction must be out, in, or both")
        if not isinstance(max_depth, int) or max_depth < 1 or max_depth > 100:
            raise ValueError("max_depth must be an integer from 1 to 100")
        with self.lock:
            if start not in self.nodes:
                raise KeyError(f"node not found: {start}")
            visited = {start}
            frontier = {start}
            result = []
            for depth in range(1, max_depth + 1):
                next_frontier: set[str] = set()
                for edge in self.edges.values():
                    if edge_type is not None and edge["type"] != edge_type:
                        continue
                    neighbors: list[str] = []
                    if direction in {"out", "both"} and edge["source"] in frontier:
                        neighbors.append(edge["target"])
                    if direction in {"in", "both"} and edge["target"] in frontier:
                        neighbors.append(edge["source"])
                    for neighbor in neighbors:
                        if neighbor in visited:
                            continue
                        visited.add(neighbor)
                        next_frontier.add(neighbor)
                        result.append({"depth": depth, "node": dict(self.nodes[neighbor]), "via": dict(edge)})
                frontier = next_frontier
                if not frontier:
                    break
            return result


class GraphRequestHandler(BaseHTTPRequestHandler):
    server_version = "ClaudeEnsembleGraph/1"

    @property
    def store(self) -> GraphStore:
        return self.server.graph_store  # type: ignore[attr-defined]

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = (_canonical(payload) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("request body must be between 1 byte and 1 MiB")
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/health":
                self._send(200, {"ok": True, "service": "graph"})
                return
            if path.startswith("/graph/node/"):
                node_id = unquote(path[len("/graph/node/"):])
                node = self.store.get_node(node_id)
                if node is None:
                    self._send(404, {"ok": False, "error": "node not found"})
                else:
                    self._send(200, {"ok": True, "node": node})
                return
            self._send(404, {"ok": False, "error": "not found"})
        except Exception as exc:
            self._send(500, {"ok": False, "error": str(exc)})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            body = self._read_json()
            if path == "/graph/add-node":
                node = self.store.add_node(body.get("type"), body.get("properties", {}), body.get("id"))
                self._send(200, {"ok": True, "node": node})
                return
            if path == "/graph/add-edge":
                edge = self.store.add_edge(
                    body.get("source"),
                    body.get("target"),
                    body.get("type"),
                    body.get("properties", {}),
                    body.get("id"),
                )
                self._send(200, {"ok": True, "edge": edge})
                return
            if path == "/graph/query":
                nodes = self.store.query(body.get("type"), body.get("properties", {}))
                self._send(200, {"ok": True, "nodes": nodes})
                return
            if path == "/graph/traverse":
                result = self.store.traverse(
                    body.get("start"),
                    body.get("direction", "out"),
                    body.get("max_depth", 1),
                    body.get("edge_type"),
                )
                self._send(200, {"ok": True, "results": result})
                return
            self._send(404, {"ok": False, "error": "not found"})
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self._send(400, {"ok": False, "error": str(exc)})
        except Exception as exc:
            self._send(500, {"ok": False, "error": str(exc)})

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def _validate_loopback_host(host: str) -> None:
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("Graph service only accepts loopback binds; remote access belongs to federation")


def create_server(host: str, port: int, store_path: str | Path) -> ThreadingHTTPServer:
    _validate_loopback_host(host)
    server = ThreadingHTTPServer((host, port), GraphRequestHandler)
    server.graph_store = GraphStore(store_path)  # type: ignore[attr-defined]
    return server


def main() -> None:
    host = os.environ.get("ENSEMBLE_GRAPH_HOST", DEFAULT_HOST)
    try:
        _validate_loopback_host(host)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    port = int(os.environ.get("ENSEMBLE_GRAPH_PORT", str(DEFAULT_PORT)))
    store_path = os.environ.get(
        "ENSEMBLE_GRAPH_STORE",
        str(Path.home() / ".local" / "share" / "claude-ensemble" / "graph.json"),
    )
    server = create_server(host, port, store_path)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
