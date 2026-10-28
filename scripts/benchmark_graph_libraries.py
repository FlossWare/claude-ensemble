#!/usr/bin/env python3
"""Compare graph-library data structures under deterministic CE-like synthetic load.

Optional benchmark only; this is not part of CE's runtime dependency path.
Install candidates with:
  python -m pip install 'networkx==3.5' 'rustworkx>=0.17,<1' 'igraph>=0.11,<1'
Run:
  python scripts/benchmark_graph_libraries.py
The benchmark uses the same generated directed graph and bounded Python traversal
for every library. It measures graph construction and neighbor-access/traversal,
not each library's unrelated algorithm implementations. tracemalloc does not
account for all native allocations made by compiled libraries.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import time
import tracemalloc
from collections import deque
from typing import Callable, Iterable


MAX_EDGES = 10_000
MAX_DEPTH = 3
MAX_VISITED = 500
MAX_PATHS = 10
REPEATS = 100
ROUNDS = 3


def workload(node_count: int, edge_count: int, seed: int) -> tuple[list[tuple[int, int]], list[int]]:
    rng = random.Random(seed)
    edges: set[tuple[int, int]] = set()
    while len(edges) < min(edge_count, node_count * (node_count - 1), MAX_EDGES):
        source = rng.randrange(node_count)
        target = rng.randrange(node_count)
        if source != target:
            edges.add((source, target))
    # Include a deterministic chain and a hub to exercise deep and high-fanout cases.
    for node in range(min(node_count - 1, 64)):
        edges.add((node, node + 1))
    for target in range(1, min(node_count, 128)):
        edges.add((0, target))
    ordered_edges = sorted(edges)[:MAX_EDGES]
    starts = [((i * 97) % node_count) for i in range(min(REPEATS, node_count))]
    return ordered_edges, starts


def bounded_query(neighbors: Callable[[int], Iterable[int]], start: int) -> tuple[int, int, int]:
    """Return reached count, bounded simple-path count, and stable checksum."""
    reached: dict[int, int] = {start: 0}
    queue = deque([start])
    while queue and len(reached) < MAX_VISITED:
        node = queue.popleft()
        depth = reached[node]
        if depth >= MAX_DEPTH:
            continue
        for nxt in sorted(neighbors(node)):
            if nxt not in reached and len(reached) < MAX_VISITED:
                reached[nxt] = depth + 1
                queue.append(nxt)

    paths = 0
    checksum = sum((node + 1) * (depth + 1) for node, depth in sorted(reached.items()))
    # Enumerate at most MAX_PATHS paths to reachable nodes, matching the CE depth cap.
    emitted: set[tuple[int, ...]] = set()
    stack: list[tuple[int, tuple[int, ...]]] = [(start, (start,))]
    while stack and len(emitted) < MAX_PATHS:
        node, path = stack.pop()
        if len(path) - 1 >= MAX_DEPTH:
            continue
        for nxt in reversed(sorted(neighbors(node))):
            if nxt in path:
                continue
            candidate = path + (nxt,)
            if candidate not in emitted:
                emitted.add(candidate)
                if len(emitted) >= MAX_PATHS:
                    break
            stack.append((nxt, candidate))
    paths = len(emitted)
    checksum += sum(sum((node + 1) for node in path) for path in sorted(emitted))
    return len(reached), paths, checksum


def build_networkx(node_count: int, edges: list[tuple[int, int]]):
    import networkx as nx

    graph = nx.DiGraph()
    graph.add_nodes_from(range(node_count))
    graph.add_edges_from(edges)
    return graph, lambda node: graph.successors(node)


def build_rustworkx(node_count: int, edges: list[tuple[int, int]]):
    import rustworkx as rx

    graph = rx.PyDiGraph(multigraph=False)
    graph.add_nodes_from(range(node_count))
    graph.add_edges_from_no_data(edges)
    return graph, lambda node: graph.successor_indices(node)


def build_igraph(node_count: int, edges: list[tuple[int, int]]):
    import igraph as ig

    graph = ig.Graph(n=node_count, edges=edges, directed=True)
    return graph, lambda node: graph.neighbors(node, mode="OUT")


BUILDERS = {
    "networkx": build_networkx,
    "rustworkx": build_rustworkx,
    "igraph": build_igraph,
}


def run_one(name: str, builder, node_count: int, edges: list[tuple[int, int]], starts: list[int], round_index: int) -> dict:
    tracemalloc.start()
    started = time.perf_counter()
    graph, neighbors = builder(node_count, edges)
    build_seconds = time.perf_counter() - started

    query_times: list[float] = []
    signatures = []
    for start in starts:
        query_started = time.perf_counter()
        signatures.append(bounded_query(neighbors, start))
        query_times.append(time.perf_counter() - query_started)
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return {
        "round": round_index,
        "library": name,
        "nodes": node_count,
        "edges": len(edges),
        "queries": len(starts),
        "build_ms": round(build_seconds * 1000, 3),
        "query_total_ms": round(sum(query_times) * 1000, 3),
        "query_median_ms": round(statistics.median(query_times) * 1000, 3),
        "query_p95_ms": round(sorted(query_times)[int((len(query_times) - 1) * 0.95)] * 1000, 3),
        "python_tracemalloc_peak_bytes": peak_bytes,
        "result_signature": signatures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20261028)
    parser.add_argument("--repeats", type=int, default=REPEATS)
    parser.add_argument("--rounds", type=int, default=ROUNDS, help="independent measurement rounds per scenario")
    parser.add_argument("--quick", action="store_true", help="run only the smaller workload")
    args = parser.parse_args()

    available = {}
    for name, builder in BUILDERS.items():
        try:
            __import__({"networkx": "networkx", "rustworkx": "rustworkx", "igraph": "igraph"}[name])
            available[name] = builder
        except ImportError:
            print(json.dumps({"warning": f"{name} is not installed; install all candidates for a fair comparison"}))

    if len(available) != len(BUILDERS):
        print(json.dumps({"error": "incomplete candidate set; no ranking produced", "available": sorted(available)}))
        return 2
    if args.repeats < 1 or args.rounds < 1:
        parser.error("--repeats and --rounds must both be positive")

    # Warm up each library before collecting timings to avoid charging one-time
    # initialization to whichever candidate happens to run first.
    warmup_edges = [(node, node + 1) for node in range(31)]
    for builder in available.values():
        warmup_graph, _ = builder(32, warmup_edges)
        del warmup_graph

    sizes = [(1_000, 5_000)]
    if not args.quick:
        sizes.append((5_000, 10_000))

    all_results = []
    for scenario_index, (node_count, edge_count) in enumerate(sizes):
        edges, starts = workload(node_count, edge_count, args.seed + scenario_index)
        starts = starts[:max(1, args.repeats)]
        for round_index in range(args.rounds):
            candidates = list(available.items())
            rotation = round_index % len(candidates)
            candidates = candidates[rotation:] + candidates[:rotation]
            scenario_results = [
                run_one(name, builder, node_count, edges, starts, round_index + 1)
                for name, builder in candidates
            ]
            signatures = {
                json.dumps(item["result_signature"], separators=(",", ":"))
                for item in scenario_results
            }
            if len(signatures) != 1:
                print(json.dumps({
                    "error": "candidate result mismatch",
                    "scenario": [node_count, edge_count],
                    "round": round_index + 1,
                }))
                for item in scenario_results:
                    item.pop("result_signature", None)
                print(json.dumps(scenario_results, indent=2))
                return 1
            for item in scenario_results:
                item.pop("result_signature", None)
            all_results.extend(scenario_results)

    print(json.dumps({
        "benchmark": "CE bounded directed traversal synthetic load",
        "seed": args.seed,
        "rounds_per_scenario": args.rounds,
        "limits": {"max_materialized_edges": MAX_EDGES, "max_depth": MAX_DEPTH, "max_visited_nodes": MAX_VISITED, "max_paths": MAX_PATHS},
        "note": "All candidates use identical generated edges and identical bounded traversal logic. tracemalloc captures Python-tracked allocations, not all native memory.",
        "results": all_results,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
