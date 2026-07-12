# Architecture Decision Records (ADR)

This directory contains Architecture Decision Records (ADRs) for significant architectural decisions made in the Distributed LLM Orchestration Framework.

## What is an ADR?

An Architecture Decision Record captures an important architectural decision made along with its context and consequences.

**Format:**
- **Status:** Proposed | Accepted | Deprecated | Superseded
- **Date:** When the decision was made
- **Context:** What is the issue we're seeing that is motivating this decision?
- **Decision:** What is the change that we're actually proposing or doing?
- **Consequences:** What becomes easier or more difficult to do because of this change?

## Index

### Active ADRs

| ID | Title | Status | Date | Summary |
|----|-------|--------|------|---------|
| [001](001-hybrid-scraper-storage-architecture.md) | Hybrid Scraper Storage Architecture | Accepted | 2026-07-10 | Scrapers POST to orchestrator API (aio-01:5000), which writes to centralized filesystem, rather than direct local/NFS writes |

## How to Use ADRs

### When to Create an ADR

Create an ADR when making a decision that:
- Has significant impact on the system architecture
- Is difficult or expensive to reverse
- Affects multiple components or teams
- Has tradeoffs that need to be documented
- Future developers will ask "why did we do it this way?"

### How to Create an ADR

1. **Copy template:**
   ```bash
   cp adr/000-template.md adr/NNN-short-title.md
   ```

2. **Fill in sections:**
   - Context: What problem are we solving?
   - Decision: What approach did we choose?
   - Rationale: Why this approach over alternatives?
   - Consequences: What are the tradeoffs?

3. **Get review:**
   - Technical review from team
   - Approve or iterate

4. **Update index:**
   - Add row to table above
   - Link to related documentation

### ADR Statuses

- **Proposed:** Under discussion, not yet approved
- **Accepted:** Approved and implemented
- **Deprecated:** No longer recommended, but not yet replaced
- **Superseded:** Replaced by a newer ADR (link to replacement)

## ADR Naming Convention

Format: `NNN-short-title.md`

- `NNN` = Sequential number (001, 002, 003, ...)
- `short-title` = Lowercase, hyphen-separated
- Examples:
  - `001-hybrid-scraper-storage-architecture.md`
  - `002-redis-queue-implementation.md`
  - `003-multi-region-orchestrators.md`

## Related Documentation

- [Architecture Summary](../ARCHITECTURE_SUMMARY.md) - Current system architecture
- [API Reference](../API_REFERENCE.md) - API endpoints and contracts
- [Feedback: Scrape Then Process](../../memory/feedback_scrape_then_process.md) - User preference for async processing

## Questions?

If unsure whether to create an ADR:
- **YES:** If decision affects >1 component or is hard to reverse
- **NO:** If decision is trivial or easily reversible (just document in code)
- **MAYBE:** Discuss with team first

When in doubt, **create the ADR**. Over-documentation is better than under-documentation for architectural decisions.
