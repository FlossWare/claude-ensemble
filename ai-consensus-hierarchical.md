# ai-consensus-hierarchical

Hierarchical multi-AI consensus with specialized sub-teams and cross-domain meta-synthesis.

## Overview

`ai-consensus-hierarchical` implements a two-level consensus architecture where specialized sub-teams independently analyze different domain aspects of a task, each producing a synthesized result through a sub-arbiter, and a meta-arbiter then integrates all domain-specific findings into a unified cross-domain answer.

This workflow excels at complex tasks that span multiple domains (security + architecture + testing, for example), where a single flat consensus would either miss domain-specific nuances or require every worker to be a generalist.

The protocol follows: **classify -> sub-team workers -> sub-arbiters -> meta-arbiter**

## When to Use

- **Multi-domain tasks** where different aspects require different expertise (e.g., "review this service for production readiness" touches security, architecture, testing, performance)
- **Production readiness reviews** where you need depth across security, scalability, correctness, and documentation
- **Complex architectural decisions** where trade-offs span performance, maintainability, security, and cost
- **Comprehensive code audits** covering correctness, security, style, and test coverage simultaneously
- **Cross-functional analysis** where domain-specific insights need integration

## When NOT to Use

- Single-domain tasks (use `ai-consensus` or `ai-consensus-weighted` instead)
- Simple factual questions (use `ai-consensus`)
- Tasks requiring adversarial debate rather than parallel domain analysis (use `ai-consensus-debate`)
- Tasks where iterative refinement matters more than breadth (use `ai-consensus-refinement`)
- Low-stakes or time-sensitive queries where the overhead is not justified

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `task` | string | *required* | The question or task for analysis |
| `context` | string | `''` | Additional context provided to all workers |
| `schema` | object | `{ answer: string }` | JSON Schema for the answer portion |
| `arbiter_instructions` | string | `'Synthesize sub-team analyses...'` | Custom instructions for the meta-arbiter |
| `sub_teams` | object[] | auto-detected | Array of `{ domain, models }` for manual team configuration |
| `meta_arbiter_model` | string | `'opus'` | Model for the Level 2 meta-arbiter |
| `budget` | string | `'medium'` | Budget tier for auto-detection when `sub_teams` not specified |
| `min_sub_teams` | number | `2` | Minimum sub-teams to form during auto-detection |
| `max_sub_teams` | number | `5` | Maximum sub-teams to form during auto-detection |

Both camelCase (`subTeams`, `metaArbiterModel`, `minSubTeams`) and snake_case (`sub_teams`, `meta_arbiter_model`, `min_sub_teams`) parameter names are accepted.

## How It Works

```
Phase 1: CLASSIFY
         Detect domains from task keywords
         Form sub-teams with specialized models
         |
         v
Phase 2: LEVEL 1 - SUB-TEAMS (parallel)
         +---------------------------+---------------------------+
         |                           |                           |
     [Security Team]          [Architecture Team]          [Testing Team]
      opus + sonnet            opus + haiku               sonnet + haiku
         |                           |                           |
         v                           v                           v
Phase 3: LEVEL 1 - SUB-ARBITERS (parallel)
      haiku judges             sonnet judges              opus judges
      security findings        architecture findings      testing findings
         |                           |                           |
         +---------------------------+---------------------------+
                                     |
                                     v
Phase 4: LEVEL 2 - META-ARBITER
         opus synthesizes across all domain findings
         Identifies cross-domain insights and conflicts
         Produces unified answer
```

### Phase Details

1. **Classify** -- Analyzes the task text and context for domain keywords (security, architecture, testing, performance, etc.). If domains are auto-detected, sub-teams are formed by selecting models whose specializations best match each domain. If no domains are detected, two general-purpose sub-teams are created split by model tier (deep-analysis with opus+sonnet, broad-analysis with sonnet+haiku).

2. **Sub-Teams (Level 1 Workers)** -- All sub-team workers execute in parallel across all teams simultaneously. Each worker receives the full task but is instructed to analyze it through the lens of its assigned domain. Workers produce domain-specific answers with confidence scores, reasoning, domain insights, and caveats.

3. **Sub-Arbiters (Level 1 Synthesis)** -- Each sub-team gets its own sub-arbiter, selected as the highest-tier model NOT already used as a worker in that team (to avoid self-judging). Sub-arbiters synthesize their team's worker responses into a single domain-specific finding, noting agreements and disagreements within the team.

4. **Meta-Arbiter (Level 2 Synthesis)** -- The meta-arbiter receives all sub-team synthesis results and integrates them into a unified cross-domain answer. It identifies insights that only emerge from combining domain perspectives, flags conflicts between domains, ranks each domain's contribution, and notes coverage gaps.

5. **Update State & Learning** -- Records arbiter rotation state, sends per-worker feedback to the learning system with domain metadata, and extracts learnings.

### Auto-Detection: Domain Keywords

The classifier recognizes these domain signals:

| Domain | Keywords |
|---|---|
| security | security, vulnerability, CVE, injection, XSS, auth, CSRF, SSRF, encrypt, permission, access control |
| architecture | architecture, design, pattern, microservice, scalability, system design, coupling, cohesion, API |
| code-review | review, code review, bug, defect, correctness, lint, code quality |
| testing | test, spec, coverage, unit test, integration test, e2e, QA, regression |
| performance | performance, optimize, latency, throughput, bottleneck, profiling, memory, CPU |
| documentation | document, readme, jsdoc, docstring, comment, explain, onboarding |
| refactoring | refactor, simplify, clean, extract, rename, reorganize, technical debt |
| logic | logic, algorithm, concurrent, race condition, distributed, state machine |

### Model Selection per Domain

Models are scored per domain based on:
1. **Specialization match** (50 points if model lists domain in specializations)
2. **Quality score** (up to 30 points based on model quality tier)
3. **Tier bonus** (10 points for flagship models)

This means security sub-teams tend to get opus+sonnet (both list security), while documentation sub-teams get sonnet+haiku (sonnet lists documentation, haiku is cost-effective for simpler tasks).

### Sub-Arbiter Selection

Sub-arbiters are chosen to avoid self-judging: the system picks the highest-tier model NOT already used as a worker in that sub-team. If a team uses opus+sonnet as workers, haiku becomes the sub-arbiter. This ensures independent judgment at each level.

## Return Value

```javascript
{
  status: 'success',
  confidence: 85,                              // meta-arbiter's cross-domain confidence
  result: { ... },                             // final unified answer (matches schema)
  synthesis_notes: '...',                      // how meta-arbiter combined sub-team results
  cross_domain_insights: ['...', '...'],       // insights from combining domain perspectives
  cross_domain_conflicts: ['...'],             // conflicts between domain findings
  coverage_gaps: ['...'],                      // domains/aspects not analyzed
  domain_rankings: [                           // how much each domain contributed
    { domain: 'security', contribution_weight: 40, assessment: '...' },
    { domain: 'architecture', contribution_weight: 35, assessment: '...' },
    { domain: 'testing', contribution_weight: 25, assessment: '...' },
  ],

  hierarchy: {                                 // full hierarchical result tree
    level_2: {
      meta_arbiter_model: 'opus',
      confidence: 85,
    },
    level_1: [
      {
        domain: 'security',
        sub_arbiter_model: 'haiku',
        confidence: 88,
        winning_worker: 'opus',
        why_selected: '...',
        key_findings: ['...', '...'],
        agreements: ['...'],
        disagreements: ['...'],
        workers: [
          { model: 'opus', confidence: 90, reasoning: '...' },
          { model: 'sonnet', confidence: 82, reasoning: '...' },
        ],
      },
      // ... more sub-teams
    ],
  },

  summary: {
    sub_team_count: 3,
    total_workers: 6,
    total_sub_arbiters: 3,
    meta_arbiter_calls: 1,
    total_agent_calls: 10,                     // 6 workers + 3 sub-arbiters + 1 meta-arbiter
    avg_sub_team_confidence: 82.3,
    domains_analyzed: ['security', 'architecture', 'testing'],
  },

  execution_id: 'hierarchical_1718..._abc123',
}
```

## Examples

### Basic Usage (Auto-Detected Domains)

```javascript
const result = await workflow('ai-consensus-hierarchical', {
  task: 'Review this API service for production readiness: check security, architecture, and test coverage',
  context: serviceSourceCode,
})
// Auto-detects: security, architecture, testing domains
// Forms 3 sub-teams with specialized model assignments
```

### Manual Sub-Team Configuration

```javascript
const result = await workflow('ai-consensus-hierarchical', {
  task: 'Evaluate this database migration plan',
  context: migrationPlan,
  sub_teams: [
    { domain: 'data-integrity', models: ['opus', 'sonnet'] },
    { domain: 'performance',    models: ['opus', 'haiku'] },
    { domain: 'rollback-safety', models: ['sonnet', 'haiku'] },
  ],
  meta_arbiter_model: 'opus',
  schema: {
    type: 'object',
    properties: {
      recommendation: { type: 'string', enum: ['approve', 'approve-with-changes', 'reject'] },
      risk_level: { type: 'string', enum: ['low', 'medium', 'high', 'critical'] },
      findings: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            domain: { type: 'string' },
            finding: { type: 'string' },
            severity: { type: 'string' },
            remediation: { type: 'string' },
          },
        },
      },
    },
  },
  arbiter_instructions: 'Synthesize all domain findings into a go/no-go recommendation with clear risk assessment.',
})
```

### Comprehensive Code Audit

```javascript
const result = await workflow('ai-consensus-hierarchical', {
  task: 'Full audit of this microservice codebase',
  context: codebaseSnapshot,
  min_sub_teams: 4,
  max_sub_teams: 5,
  // Auto-detects domains from codebase content
  // Might form: security, code-review, testing, performance, documentation
})

// Access hierarchical results
console.log('Cross-domain insights:', result.cross_domain_insights)
console.log('Coverage gaps:', result.coverage_gaps)

// Drill into specific domains
for (const team of result.hierarchy.level_1) {
  console.log(`${team.domain}: ${team.confidence}% confidence`)
  console.log(`  Findings: ${team.key_findings.join(', ')}`)
}
```

### Budget-Constrained Analysis

```javascript
const result = await workflow('ai-consensus-hierarchical', {
  task: 'Quick review of this PR for obvious issues',
  context: prDiff,
  min_sub_teams: 2,
  max_sub_teams: 2,
  meta_arbiter_model: 'sonnet',  // cheaper meta-arbiter
})
```

## Cost Considerations

The hierarchical approach invokes more agent calls than flat consensus but provides deeper, domain-specific analysis. The cost formula is:

**Total calls = (workers per team * team count) + team count + 1**

- **Level 1 workers**: N workers per team * T teams (all parallel)
- **Level 1 sub-arbiters**: T calls (all parallel)
- **Level 2 meta-arbiter**: 1 call

| Configuration | Teams | Workers/Team | Total Calls |
|---|---|---|---|
| Minimal (2 teams, 2 workers each) | 2 | 2 | 4 + 2 + 1 = 7 |
| Standard (3 teams, 2 workers each) | 3 | 2 | 6 + 3 + 1 = 10 |
| Thorough (4 teams, 2 workers each) | 4 | 2 | 8 + 4 + 1 = 13 |
| Maximum (5 teams, 2 workers each) | 5 | 2 | 10 + 5 + 1 = 16 |

Despite more total calls, latency is often comparable to flat consensus because Level 1 workers and sub-arbiters execute in parallel within their respective phases.

## Differences from Other Consensus Workflows

| Feature | ai-consensus | ai-consensus-weighted | ai-consensus-debate | ai-consensus-refinement | ai-consensus-hierarchical |
|---|---|---|---|---|---|
| Structure | Flat | Flat | Multi-round | Iterative | Two-level hierarchy |
| Domain specialization | No | No | No | No | Yes |
| Sub-teams | No | No | No | No | Yes |
| Sub-arbiters | No | No | No | No | Yes |
| Meta-arbiter | No | No | No | No | Yes |
| Cross-domain insights | No | No | No | No | Yes |
| Coverage gap detection | No | No | No | No | Yes |
| Best for | Simple consensus | Weighted voting | Adversarial analysis | Iterative improvement | Multi-domain synthesis |

## Hierarchical Result Tree

The `hierarchy` field in the return value provides the full decision tree:

```
hierarchy.level_2                    -- Meta-arbiter synthesis
  |
  +-- hierarchy.level_1[0]           -- Security sub-team
  |     +-- workers[0]               -- opus (security specialist)
  |     +-- workers[1]               -- sonnet (security specialist)
  |     +-- sub_arbiter: haiku       -- synthesized security findings
  |
  +-- hierarchy.level_1[1]           -- Architecture sub-team
  |     +-- workers[0]               -- opus (architecture specialist)
  |     +-- workers[1]               -- haiku (architecture support)
  |     +-- sub_arbiter: sonnet      -- synthesized architecture findings
  |
  +-- hierarchy.level_1[2]           -- Testing sub-team
        +-- workers[0]               -- sonnet (testing specialist)
        +-- workers[1]               -- haiku (testing support)
        +-- sub_arbiter: opus        -- synthesized testing findings
```

This tree structure enables callers to inspect results at any level of granularity: the final cross-domain answer, individual domain findings, or specific worker responses.

## Integration with Model Config

The workflow loads model specializations from two sources (in priority order):

1. `model-config.json` (external override, if present)
2. Built-in `MODEL_SPECIALIZATIONS` constant (mirrors `ai-task-router.js` defaults)

To customize model assignments, either:
- Pass explicit `sub_teams` with `models` arrays
- Create/modify `model-config.json` with custom specialization mappings

## Integration with Learning System

Each hierarchical run records:
- Per-worker feedback with domain metadata (domain, sub-arbiter model, level)
- Winner/non-winner status within each sub-team
- Sub-team confidence scores
- Cross-domain insight and conflict counts
- Coverage gap data

This feeds the learning system to improve future model selection per domain.

## Tips

- **Let auto-detection work first**: The keyword-based domain classifier handles most multi-domain tasks well. Only specify `sub_teams` manually when you need custom domains.
- **Use `min_sub_teams: 2`**: Even for tasks with a single detected domain, having at least two perspectives (deep vs. broad) improves results.
- **Check `coverage_gaps`**: The meta-arbiter explicitly flags aspects not covered by any sub-team. Use this to decide if a follow-up analysis is needed.
- **Cross-domain insights are the key value**: The `cross_domain_insights` field contains findings that no single-domain analysis would surface. This is the primary advantage of hierarchical consensus over flat approaches.
- **Inspect `domain_rankings`**: The meta-arbiter ranks how much each domain contributed. Low-contribution domains may indicate the task does not actually require that domain.
