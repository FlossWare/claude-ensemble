#!/usr/bin/env python3
"""Stress-test NetworkX, rustworkx, and igraph across CE-like graph shapes.

This is an optional benchmark, not a CE runtime dependency. All candidates receive
identical generated edges. It compares graph build, common bounded traversal,
native unweighted shortest paths, result parity, Python allocations, and RSS deltas.
RSS deltas are approximate and can be noisy; run on the same host for comparisons.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import time
import tracemalloc
from collections import deque

import psutil

MAX_EDGES = 10_000
MAX_DEPTH = 3
MAX_VISITED = 500
MAX_PATHS = 10


def make_edges(nodes: int, count: int, seed: int, shape: str) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    edges: set[tuple[int, int]] = set()
    if shape == "sparse":
        while len(edges) < count:
            a, b = rng.randrange(nodes), rng.randrange(nodes)
            if a != b:
                edges.add((a, b))
    elif shape == "hub":
        for node in range(1, nodes):
            edges.add((0, node))
            edges.add((node, 0))
        while len(edges) < count:
            a, b = rng.randrange(nodes), rng.randrange(nodes)
            if a != b:
                edges.add((a, b))
    elif shape == "chain-cycle":
        for node in range(nodes - 1):
            edges.add((node, node + 1))
        edges.add((nodes - 1, 0))
        while len(edges) < count:
            a, b = rng.randrange(nodes), rng.randrange(nodes)
            if a != b:
                edges.add((a, b))
    elif shape == "layered":
        for node in range(nodes):
            for offset in range(1, 5):
                if node + offset < nodes:
                    edges.add((node, node + offset))
        while len(edges) < count:
            a, b = rng.randrange(nodes), rng.randrange(nodes)
            if a != b:
                edges.add((a, b))
    else:
        raise ValueError(shape)
    return sorted(edges)[:min(count, MAX_EDGES)]


def bounded(neighbors, start: int) -> tuple[int, int, int]:
    depths = {start: 0}
    queue = deque([start])
    while queue and len(depths) < MAX_VISITED:
        node = queue.popleft()
        depth = depths[node]
        if depth >= MAX_DEPTH:
            continue
        for nxt in sorted(neighbors(node)):
            if nxt not in depths and len(depths) < MAX_VISITED:
                depths[nxt] = depth + 1
                queue.append(nxt)
    paths: set[tuple[int, ...]] = set()
    stack = [(start, (start,))]
    while stack and len(paths) < MAX_PATHS:
        node, path = stack.pop()
        if len(path) - 1 >= MAX_DEPTH:
            continue
        for nxt in reversed(sorted(neighbors(node))):
            if nxt not in path:
                candidate = path + (nxt,)
                paths.add(candidate)
                if len(paths) >= MAX_PATHS:
                    break
                stack.append((nxt, candidate))
    checksum = sum((n + 1) * (d + 1) for n, d in sorted(depths.items()))
    checksum += sum(sum(n + 1 for n in path) for path in sorted(paths))
    return len(depths), len(paths), checksum


def builders(nodes: int, edges: list[tuple[int, int]]):
    def networkx_builder():
        import networkx as nx
        graph = nx.DiGraph()
        graph.add_nodes_from(range(nodes))
        graph.add_edges_from(edges)
        return graph, lambda n: graph.successors(n), lambda n: dict(nx.single_source_shortest_path_length(graph, n, cutoff=MAX_DEPTH))

    def rustworkx_builder():
        import rustworkx as rx
        graph = rx.PyDiGraph(multigraph=False)
        graph.add_nodes_from(range(nodes))
        graph.add_edges_from_no_data(edges)
        return graph, lambda n: graph.successor_indices(n), lambda n: dict(rx.digraph_dijkstra_shortest_path_lengths(graph, n, lambda _: 1))

    def igraph_builder():
        import igraph as ig
        graph = ig.Graph(n=nodes, edges=edges, directed=True)
        return graph, lambda n: graph.neighbors(n, mode="OUT"), lambda n: dict(enumerate(graph.distances(source=n, mode="OUT", algorithm="unweighted")[0]))

    return {
        "networkx": networkx_builder,
        "rustworkx": rustworkx_builder,
        "igraph": igraph_builder,
    }

def measure(name, builder, starts, shape, nodes, edge_count, round_id):
    proc = psutil.Process()
    rss_before = proc.memory_info().rss
    tracemalloc.start()
    build_started = time.perf_counter()
    graph, neighbors, native_paths = builder()
    build_ms = (time.perf_counter() - build_started) * 1000
    query_times, native_times, signatures, native_signatures = [], [], [], []
    for start in starts[:1]:
        # One warm-up query per candidate, excluded from timing.
        bounded(neighbors, start)
        native_paths(start)

    rss_built = proc.memory_info().rss

    for start in starts:
        t = time.perf_counter()
        signatures.append(bounded(neighbors, start))
        query_times.append(time.perf_counter() - t)
        t = time.perf_counter()
        distances = native_paths(start)
        native_times.append(time.perf_counter() - t)
        normalized = []
        for node, distance in distances.items():
            if distance is None or distance < 0 or distance == float("inf") or distance > MAX_DEPTH:
                continue
            normalized.append((int(node), int(distance)))
        # rustworkx's Dijkstra iterator omits the source vertex at distance zero;
        # normalize that API difference before comparing algorithm results.
        if not any(node == start for node, _ in normalized):
            normalized.append((start, 0))
        native_signatures.append(sorted(normalized))
    rss_after = proc.memory_info().rss
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "round": round_id,
        "shape": shape,
        "library": name,
        "nodes": nodes,
        "edges": edge_count,
        "queries": len(starts),
        "build_ms": round(build_ms, 3),
        "query_total_ms": round(sum(query_times) * 1000, 3),
        "query_median_ms": round(statistics.median(query_times) * 1000, 3),
        "query_p95_ms": round(sorted(query_times)[int((len(query_times) - 1) * 0.95)] * 1000, 3),
        "native_shortest_total_ms": round(sum(native_times) * 1000, 3),
        "native_shortest_median_ms": round(statistics.median(native_times) * 1000, 3),
        "native_shortest_p95_ms": round(sorted(native_times)[int((len(native_times) - 1) * 0.95)] * 1000, 3),
        "rss_delta_bytes": max(0, rss_after - rss_before),
        "python_tracemalloc_peak_bytes": peak,
        "signature": signatures,
        "native_signature": native_signatures,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rounds", type=int, default=5)
    p.add_argument("--queries", type=int, default=100)
    p.add_argument("--quick", action="store_true")
    p.add_argument("--shapes", default="sparse,hub,chain-cycle,layered")
    args = p.parse_args()
    if args.rounds < 1 or args.queries < 1:
        p.error("--rounds and --queries must be positive")

    sizes = [(1_000, 5_000)] if args.quick else [(1_000, 5_000), (5_000, 10_000)]
    shapes = [x.strip() for x in args.shapes.split(",") if x.strip()]
    allowed = {"sparse", "hub", "chain-cycle", "layered"}
    if not shapes or not set(shapes) <= allowed:
        p.error(f"--shapes must be selected from {sorted(allowed)}")

    results = []
    for shape_index, shape in enumerate(shapes):
        for size_index, (nodes, count) in enumerate(sizes):
            edges = make_edges(nodes, count, 20261028 + shape_index * 10 + size_index, shape)
            starts = [((i * 97) % nodes) for i in range(min(args.queries, nodes))]
            expected_bounded = None
            expected_native = None
            for round_id in range(1, args.rounds + 1):
                # Rotate order to reduce systematic first-candidate bias.
                candidates = list(builders(nodes, edges).items())
                rotate = (round_id - 1) % len(candidates)
                candidates = candidates[rotate:] + candidates[:rotate]
                for name, builder in candidates:
                    result = measure(name, builder, starts, shape, nodes, len(edges), round_id)
                    bounded_values = result.pop("signature")
                    native_values = result.pop("native_signature")
                    signature = json.dumps(bounded_values, separators=(",", ":"))
                    native_signature = json.dumps(native_values, separators=(",", ":"))
                    if expected_bounded is None:
                        expected_bounded = signature
                    elif signature != expected_bounded:
                        print(json.dumps({"error": "bounded traversal mismatch", "shape": shape, "round": round_id, "library": name}))
                        return 1
                    if expected_native is None:
                        expected_native = native_signature
                    elif native_signature != expected_native:
                        print(json.dumps({
                            "error": "native shortest-path mismatch",
                            "shape": shape,
                            "round": round_id,
                            "library": name,
                            "expected_first_queries": json.loads(expected_native)[:3],
                            "actual_first_queries": native_values[:3],
                        }))
                        return 1
                    results.append(result)

    print(json.dumps({
        "benchmark": "CE graph-library stress and native shortest-path comparison",
        "python": __import__("sys").version,
        "rounds": args.rounds,
        "queries_per_round": args.queries,
        "shapes": shapes,
        "sizes": sizes,
        "note": "RSS deltas are process-level but noisy; tracemalloc misses native allocations. Native shortest-path timing is separate from common bounded traversal.",
        "results": results,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
