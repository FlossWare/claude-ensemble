# Claude Ensemble Graph Service

The Graph service is a local HTTP service backed by a durable JSON store.

## Boundary

Default listener:

`127.0.0.1:8766`

Health:

`GET /health`

Graph operations:

- `POST /graph/add-node`
- `POST /graph/add-edge`
- `GET /graph/node/{id}`
- `POST /graph/query`
- `POST /graph/traverse`

The service uses only Python's standard library. It does not depend on a graph database and does not claim success before a mutation has been durably persisted.

## Persistence

The default store is:

`~/.local/share/claude-ensemble/graph.json`

Set `ENSEMBLE_GRAPH_STORE` to use another location.

Mutations are serialized under an in-process reentrant lock and persisted by writing a temporary file, flushing it with `fsync`, and atomically replacing the store. A new process reconstructs the graph from that file.

Automatically generated node and edge IDs are SHA-256 identifiers over canonical JSON content, so the same logical object gets the same ID after a restart.

## Configuration

- `ENSEMBLE_GRAPH_HOST`, default `127.0.0.1`
- `ENSEMBLE_GRAPH_PORT`, default `8766`
- `ENSEMBLE_GRAPH_STORE`, default `~/.local/share/claude-ensemble/graph.json`

Remote federation and authentication are intentionally outside this issue.

## Test

From the repository root:

`python graph-service/test_graph_service.py`

The test starts the actual HTTP server, performs mutations and reads through HTTP, shuts it down, starts a fresh server against the same store, and verifies the data and deterministic IDs survive the restart.
