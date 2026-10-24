# Clean-Slate Restart Plan

## Purpose

Redesign Claude Ensemble around an explicit functional model and stable contracts rather than carrying forward historical implementation decisions. The archived repository is reference material only.

## Scope to specify first

Initial capability areas are:

- **Memory**: capture, update, retrieve, inject relevant context automatically, and explain provenance.
- **Graph**: represent and traverse relationships where graph semantics add value.
- **Thompson**: own the agreed Thompson-sampling functionality and its state/decision contract.
- **Learning**: define what is learned, from which evidence, with what feedback and lifecycle.

Alerting and messaging are not in the initial scope unless the functional inventory demonstrates a necessary requirement.

## Design sequence

1. **Functional inventory**: enumerate user-visible and system-level behavior, triggers, inputs, outputs, failure cases, and acceptance evidence.
2. **Boundary classification**: classify every item as a service, component, algorithm, data model, adapter, or operational concern. Do not turn every algorithm into a network service just because it has a name.
3. **Contracts**: specify language-neutral HTTP/REST contracts where a capability needs independent addressability. Define models, errors, lifecycle, deadlines, cancellation, retries, idempotency, and versioning as applicable. Consider decorator/composition implementations when defining each contract.
4. **Ownership**: make explicit who owns persistence, identity, provenance, indexing, retention, recovery, and cross-service consistency.
5. **Acceptance criteria**: define observable tests before implementation, including fresh-process recovery, failure injection, and end-to-end integration where relevant.
6. **Vertical slices**: implement only after the specification is reviewed. Each slice must have contract tests and an end-to-end acceptance path.

## Non-negotiable acceptance requirement: automatic memory

Memory retrieval/injection must work during the normal prompt lifecycle without requiring a manual memory lookup, special prefix, or user reminder. Tests must verify both that relevant stored memories are injected and that the assistant does not falsely claim no memories exist when retrievable memories are available.

## Working rules

- Existing code is evidence, not the design.
- Do not preserve an endpoint, class, schema, or service solely because it exists in the archive.
- Distinguish independently addressable services from internal components and algorithms.
- Prefer clear contracts over language-specific implementation assumptions.
- Do not declare distributed safety based only on an in-process or single-host test.
- Do not begin implementation before the functional inventory, boundaries, contracts, ownership, and acceptance criteria are sufficiently specified and reviewed.

## Historical reference

- Archived repository: [FlossWare-Archives/claude-ensemble-legacy](https://github.com/FlossWare-Archives/claude-ensemble-legacy)
