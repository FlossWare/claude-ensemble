# Claude Ensemble

Claude Ensemble is being redesigned from a clean baseline.

The previous implementation is preserved in [FlossWare-Archives/claude-ensemble-legacy](https://github.com/FlossWare-Archives/claude-ensemble-legacy). Treat it as historical evidence, not as an architectural blueprint.

## Restart approach

We will specify the system before implementing it:

1. Functional inventory
2. Service, component, and algorithm boundaries
3. Language-neutral contracts
4. Ownership of persistence, identity, provenance, indexing, and recovery
5. Acceptance criteria
6. Implementation in complete, testable vertical slices

See [docs/RESTART.md](docs/RESTART.md) for the working plan.

## Notion documentation

The companion Notion index is the [claude-ensemble documentation entry](https://app.notion.com/p/405cc41ae77d81baa3afc297260e9b2c). It links to the project's Notion-side documentation and identifies the current review status. Public web access to that Notion page must be enabled separately in Notion.

## Current architecture review

The current proposal is under review in [PR #8: Resolve architecture and contract findings](https://github.com/FlossWare/claude-ensemble/pull/8). The documents linked here describe proposed behavior; they do not authorize implementation.

- [Service contracts](docs/contracts/)
- [JSON Schemas](docs/contracts/schemas/)
- [Architecture review acceptance baseline](docs/ARCHITECTURE-REVIEW-ACCEPTANCE.md)
- [Functional traceability matrix](docs/TRACEABILITY.md)
- [Owner decision register](docs/OWNER-DECISIONS.md)
- [Service call-graph validator](scripts/check_service_call_graph.py)
- [Contract validation GitHub Actions workflow](.github/workflows/contract-validation.yml)

The contract-validation workflow runs the Draft 2020-12 schema/reference/endpoint-binding/JSON-example validator and the service call-graph validator. The latest observed workflow run passed both checks. These are static contract checks, not endpoint-fixture, runtime, crash/recovery, integration, or latency test evidence. Owner decisions remain pending until explicitly confirmed.
