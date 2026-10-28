# Graph library evaluation

Status: **provisional; simulated-load comparison pending**.

## Decision so far

NetworkX 3.5 is currently integrated in the Graph runtime as an initial candidate, not a proven winner. Do not treat that integration as final until the candidates have been compared against the same CE-like workload and Graph contract tests.

SQLite remains the canonical durable store. The candidate library supplies in-memory graph representation and traversal primitives; it does not own CE's REST contract or domain semantics.

## Candidates and comparison

Compare NetworkX, rustworkx, and igraph using the optional deterministic harness [scripts/benchmark_graph_libraries.py](../scripts/benchmark_graph_libraries.py). Run the same generated graph, query starts, depth bound, visited-node bound, and path bound against all three candidates. The harness rejects a run if the candidate result signatures differ.

The harness warms up all candidates, rotates candidate order, and performs three measurement rounds per workload by default. It reports graph build time, aggregate/median/p95 query time, and Python-tracked peak allocations. tracemalloc does not capture all native allocations, so memory figures are directional rather than complete process RSS. CI runs all candidates on the same machine and Python version; treat small differences cautiously.

Install the optional candidate packages in an isolated environment:

~~~sh
python -m pip install 'networkx==3.5' 'rustworkx>=0.17,<1' 'igraph>=0.11,<1'
python scripts/benchmark_graph_libraries.py
~~~

Use --quick for a short smoke run. The default run includes a larger scenario capped at CE's 10,000 materialized-edge contract limit. GitHub Actions runs the comparison on changes to the harness or this document and retains the JSON results as an artifact. These are synthetic stress cases, not claims about production traffic. If results are close, add workload shapes based on measured CE traces before choosing a winner.

## Initial simulated-load results

First three-round GitHub Actions run (Ubuntu runner, Python 3.12; medians across rounds):

| Nodes / edges | Library | Build ms | 100-query total ms | Median query ms | p95 query ms | Python-tracked peak |
|---|---|---:|---:|---:|---:|---:|
| 1,000 / 5,189 | NetworkX | 16.268 | 30.762 | 0.290 | 0.458 | 1,150,960 B |
| 1,000 / 5,189 | rustworkx | 2.598 | 33.283 | 0.315 | 0.501 | 203,600 B |
| 1,000 / 5,189 | igraph | 0.886 | 33.464 | 0.323 | 0.507 | 38,096 B |
| 5,000 / 10,000 | NetworkX | 34.956 | 9.074 | 0.094 | 0.134 | 3,618,296 B |
| 5,000 / 10,000 | rustworkx | 5.919 | 10.298 | 0.104 | 0.157 | 504,796 B |
| 5,000 / 10,000 | igraph | 1.434 | 10.047 | 0.102 | 0.151 | 38,608 B |

All candidates produced identical result signatures for the tested workloads. The compiled libraries built graphs substantially faster; NetworkX had slightly lower query latency in this harness, which uses the same Python-level bounded traversal for all candidates. This is a data-structure/integration comparison, **not** a comparison of each library's native path algorithms. The memory column is not a fair total-memory comparison because tracemalloc misses native allocations, particularly for rustworkx and igraph.

These results do not establish a winner. The workloads are synthetic, only two graph sizes/shapes have been exercised, and CE's full traversal includes direction, source supports, scope filtering, and deterministic result rules. Next, run the candidate structures through representative contract-level scenarios and measure native/process memory if memory is a deciding factor. If the current query algorithm remains NetworkX-specific, separately compare native algorithm implementations before claiming equivalent coverage.

## Contract constraints that remain CE-owned

Regardless of library choice, CE must continue to enforce:

- source-supported nodes and relationships, tombstones, revision watermarks, and idempotency;
- scope filtering before graph construction;
- stable support/provenance payloads and deterministic ordering;
- maximum depth, visited-node count, path count, and materialized-edge bounds;
- SQLite persistence, owner journal replay, checkpoints, and readiness;
- the public REST contract and error behavior.

The in-memory graph is a query structure, not canonical storage. It is rebuilt from bounded, scoped persisted rows so it cannot become a second mutable source of truth after a restart or failed projection.

## Selection criteria

Choose based on evidence across:

1. Correctness and parity with the Graph contract, including directed/undirected semantics and deterministic bounded results.
2. Build cost and query latency under sparse, high-fanout, and cyclic graph shapes.
3. Memory consumption, including native allocations where the measurement environment permits it.
4. Python/runtime compatibility, dependency footprint, maintenance, and license.
5. Integration complexity and how much CE-specific code is still required.

A raw speed win does not justify a library that changes result semantics or makes CE's contract harder to enforce. If performance is similar, prefer the simplest dependable integration. Keep NetworkX provisional until the benchmark and Graph runtime tests provide evidence.
