#!/usr/bin/env python3
"""
Simple GraphDB Service

Lightweight file-based graph database for Thompson relationship queries.
Stores nodes (models, tasks, outcomes) and edges (relationships, success chains).

Pattern: Like Memory Service + Learning Service, but for relationship graphs.

Data Flow:
  Arbitration outcomes → Learning Service
                      → ArbitrationOutcomesBridge
                      → GraphDB (populate nodes/edges)
                      → Thompson queries (which models work together?)

REST API (via ensemble_server.py):
  POST /graph/add-node      — Create/update node
  POST /graph/add-edge      — Create/update relationship
  GET  /graph/node/<id>     — Get node + adjacent edges
  GET  /graph/traverse      — BFS/DFS from node
  GET  /graph/query         — Path queries (A→B→C)
"""

import json
import logging
import sys
import os
import tempfile
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Storage paths (JSONL for atomic append)
GRAPH_STORAGE_DIR = Path(os.environ.get('GRAPH_STORAGE_DIR', Path.home() / '.ensemble' / 'graph_storage'))
NODES_FILE = GRAPH_STORAGE_DIR / 'nodes.jsonl'
EDGES_FILE = GRAPH_STORAGE_DIR / 'edges.jsonl'


@dataclass
class GraphNode:
    """Graph node: represents model, task, outcome, etc."""
    id: str
    type: str  # "model", "task_type", "arbitration_outcome", "scope", etc.
    properties: Dict[str, Any]
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GraphEdge:
    """Graph edge: relationship between nodes"""
    from_id: str
    to_id: str
    relationship: str  # "succeeded_on", "selected_model", "produced", etc.
    properties: Dict[str, Any]
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SimpleGraphDB:
    """In-memory graph with file persistence (JSONL)"""

    def __init__(self, storage_dir: Path = GRAPH_STORAGE_DIR):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.nodes_file = self.storage_dir / 'nodes.jsonl'
        self.edges_file = self.storage_dir / 'edges.jsonl'

        # Thread safety: RWLock for in-memory graph
        self._lock = threading.RLock()

        # In-memory cache (loaded on init)
        self.nodes: Dict[str, GraphNode] = {}  # id → node
        self.edges: List[GraphEdge] = []  # list of all edges
        self.adjacency: Dict[str, List[str]] = {}  # id → [edge_ids]

        # Load existing data
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Load nodes and edges from JSONL files"""
        try:
            # Load nodes
            if self.nodes_file.exists():
                with open(self.nodes_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            node = GraphNode(**data)
                            self.nodes[node.id] = node
                logger.info(f"Loaded {len(self.nodes)} nodes from {self.nodes_file}")

            # Load edges
            if self.edges_file.exists():
                with open(self.edges_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            edge = GraphEdge(**data)
                            self.edges.append(edge)
                            self._add_to_adjacency(edge)
                logger.info(f"Loaded {len(self.edges)} edges from {self.edges_file}")

        except Exception as e:
            logger.error(f"Error loading graph from disk: {e}")

    def _add_to_adjacency(self, edge: GraphEdge) -> None:
        """Update adjacency index for fast traversal"""
        if edge.from_id not in self.adjacency:
            self.adjacency[edge.from_id] = []
        self.adjacency[edge.from_id].append(len(self.edges) - 1)

    def add_node(self, node_id: str, node_type: str, properties: Dict[str, Any] = None) -> bool:
        """Add or update a node, persist to disk"""
        try:
            if properties is None:
                properties = {}

            with self._lock:
                node = GraphNode(id=node_id, type=node_type, properties=properties)
                self.nodes[node_id] = node

            # Atomic append (outside lock to minimize contention)
            with open(self.nodes_file, 'a') as f:
                f.write(json.dumps(node.to_dict()) + '\n')

            logger.info(f"Added node: {node_id} ({node_type})")
            return True

        except Exception as e:
            logger.error(f"Error adding node {node_id}: {e}")
            return False

    def add_edge(self, from_id: str, to_id: str, relationship: str,
                 properties: Dict[str, Any] = None) -> bool:
        """Add or update an edge, persist to disk"""
        try:
            if properties is None:
                properties = {}

            with self._lock:
                # Validate nodes exist (within lock to prevent TOCTOU)
                if from_id not in self.nodes:
                    logger.warning(f"Edge source node not found: {from_id}")
                    return False
                if to_id not in self.nodes:
                    logger.warning(f"Edge target node not found: {to_id}")
                    return False

                edge = GraphEdge(from_id=from_id, to_id=to_id, relationship=relationship,
                               properties=properties)
                self.edges.append(edge)
                self._add_to_adjacency(edge)
                edge_index = len(self.edges) - 1

            # Atomic append (outside lock)
            with open(self.edges_file, 'a') as f:
                f.write(json.dumps(edge.to_dict()) + '\n')

            logger.info(f"Added edge: {from_id} -[{relationship}]-> {to_id}")
            return True

        except Exception as e:
            logger.error(f"Error adding edge {from_id}->{to_id}: {e}")
            return False

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get node by ID"""
        with self._lock:
            return self.nodes.get(node_id)

    def get_node_with_edges(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get node + all adjacent edges (incoming and outgoing)"""
        if node_id not in self.nodes:
            return None

        node = self.nodes[node_id]
        outgoing = [self.edges[i].to_dict() for i in self.adjacency.get(node_id, [])]
        incoming = [e.to_dict() for e in self.edges if e.to_id == node_id]

        return {
            'node': node.to_dict(),
            'outgoing_edges': outgoing,
            'incoming_edges': incoming,
        }

    def traverse_bfs(self, start_id: str, max_depth: int = 3) -> Dict[str, Any]:
        """BFS traversal from node (breadth-first search)"""
        with self._lock:
            if start_id not in self.nodes:
                return {'error': f'Node not found: {start_id}'}

            visited: Set[str] = set()
            queue: List[Tuple[str, int]] = [(start_id, 0)]
            result = {'start': start_id, 'nodes': {}, 'edges': []}

            while queue:
                current_id, depth = queue.pop(0)

                if current_id in visited or depth > max_depth:
                    continue

                visited.add(current_id)
                result['nodes'][current_id] = self.nodes[current_id].to_dict()

                # Add outgoing edges
                for edge_idx in self.adjacency.get(current_id, []):
                    edge = self.edges[edge_idx]
                    result['edges'].append(edge.to_dict())

                    # Queue next node
                    if edge.to_id not in visited:
                        queue.append((edge.to_id, depth + 1))

        return result

    def find_paths(self, from_id: str, to_id: str, max_depth: int = 3) -> List[List[Dict[str, Any]]]:
        """Find all paths from from_id to to_id (DFS)"""
        if from_id not in self.nodes or to_id not in self.nodes:
            return []

        paths = []

        def dfs(current_id: str, target_id: str, path: List[Dict[str, Any]], depth: int) -> None:
            if depth > max_depth or current_id in [p['from_id'] for p in path]:
                return

            if current_id == target_id:
                paths.append(path)
                return

            for edge_idx in self.adjacency.get(current_id, []):
                edge = self.edges[edge_idx]
                dfs(edge.to_id, target_id, path + [edge.to_dict()], depth + 1)

        dfs(from_id, to_id, [], 0)
        return paths

    def query_edges(self, from_type: str = None, to_type: str = None,
                   relationship: str = None) -> List[Dict[str, Any]]:
        """Query edges by node types and/or relationship"""
        results = []

        for edge in self.edges:
            from_node = self.nodes.get(edge.from_id)
            to_node = self.nodes.get(edge.to_id)

            if from_type and from_node and from_node.type != from_type:
                continue
            if to_type and to_node and to_node.type != to_type:
                continue
            if relationship and edge.relationship != relationship:
                continue

            results.append(edge.to_dict())

        return results

    def stats(self) -> Dict[str, Any]:
        """Get graph statistics"""
        return {
            'total_nodes': len(self.nodes),
            'total_edges': len(self.edges),
            'node_types': list(set(n.type for n in self.nodes.values())),
            'relationship_types': list(set(e.relationship for e in self.edges)),
        }


class GraphService:
    """REST service wrapper for SimpleGraphDB"""

    def __init__(self, storage_dir: Path = GRAPH_STORAGE_DIR):
        self.db = SimpleGraphDB(storage_dir)
        logger.info(f"GraphService initialized with {len(self.db.nodes)} nodes, {len(self.db.edges)} edges")

    # REST endpoint handlers
    def handle_add_node(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle POST /graph/add-node"""
        node_id = request_data.get('id')
        node_type = request_data.get('type')
        properties = request_data.get('properties', {})

        if not node_id or not node_type:
            return {'ok': False, 'error': 'Missing id or type'}

        success = self.db.add_node(node_id, node_type, properties)
        return {'ok': success, 'id': node_id}

    def handle_add_edge(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle POST /graph/add-edge"""
        from_id = request_data.get('from')
        to_id = request_data.get('to')
        relationship = request_data.get('relationship')
        properties = request_data.get('properties', {})

        if not from_id or not to_id or not relationship:
            return {'ok': False, 'error': 'Missing from, to, or relationship'}

        success = self.db.add_edge(from_id, to_id, relationship, properties)
        return {'ok': success, 'edge': f'{from_id}-[{relationship}]->{to_id}'}

    def handle_get_node(self, node_id: str) -> Dict[str, Any]:
        """Handle GET /graph/node/<id>"""
        result = self.db.get_node_with_edges(node_id)
        if not result:
            return {'ok': False, 'error': f'Node not found: {node_id}'}
        return {'ok': True, 'data': result}

    def handle_traverse(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle GET /graph/traverse"""
        start_id = request_data.get('start')
        max_depth = request_data.get('max_depth', 3)

        if not start_id:
            return {'ok': False, 'error': 'Missing start node'}

        result = self.db.traverse_bfs(start_id, max_depth)
        return {'ok': True, 'data': result}

    def handle_query(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle GET /graph/query"""
        query_type = request_data.get('type')

        if query_type == 'edges':
            # Query edges by type/relationship
            from_type = request_data.get('from_type')
            to_type = request_data.get('to_type')
            relationship = request_data.get('relationship')
            edges = self.db.query_edges(from_type, to_type, relationship)
            return {'ok': True, 'edges': edges}

        elif query_type == 'paths':
            # Find paths between nodes
            from_id = request_data.get('from')
            to_id = request_data.get('to')
            max_depth = request_data.get('max_depth', 3)
            paths = self.db.find_paths(from_id, to_id, max_depth)
            return {'ok': True, 'paths': paths}

        else:
            return {'ok': False, 'error': 'Unknown query type'}

    def handle_stats(self) -> Dict[str, Any]:
        """Handle GET /graph/stats"""
        stats = self.db.stats()
        return {'ok': True, 'stats': stats}


def main():
    """Run graph service as daemon - listens on HTTP via ensemble_server"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize service (loads graph from disk)
    service = GraphService()
    logger.info("GraphService initialized and ready for requests via ensemble_server")

    # Service runs via ensemble_server HTTP routing, not standalone
    # This process stays alive to maintain graph state in memory
    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("GraphService shutting down")


if __name__ == '__main__':
    main()
