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
