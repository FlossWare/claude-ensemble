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

## Current architecture review

The current proposal is under review in [PR #8: Resolve architecture and contract findings](https://github.com/FlossWare/claude-ensemble/pull/8). The documents linked here describe proposed behavior; they do not authorize implementation.

- [Service contracts](docs/contracts/)
- [JSON Schemas](docs/contracts/schemas/)
- [Architecture review acceptance baseline](docs/ARCHITECTURE-REVIEW-ACCEPTANCE.md)
- [Functional traceability matrix](docs/TRACEABILITY.md)
- [Owner decision register](docs/OWNER-DECISIONS.md)
- [Declared service call graph](docs/SERVICE-CALL-GRAPH.md)

The acceptance scenarios specify required behavior; they are not evidence that runtime tests have passed. The current PR description records which static checks and runtime tests remain outstanding. Owner decisions remain pending until explicitly confirmed.
