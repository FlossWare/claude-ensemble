# Audit: Existing Multi-Stage Review Implementation

**Date:** 2026-09-30  
**Scope:** claude-ensemble arbitration/orchestration system  
**Goal:** Understand current information flow and identify gaps

---

## Executive Summary

Claude Ensemble HAS a working multi-stage arbitration system with sophisticated phase orchestration, model pool management, and cost tracking. However, the system is currently **tailored to code review** (PR analysis, git diffs, bug analysis) and does NOT natively support generic artifact types (documents, designs, proposals).

**Key Finding:** The system correctly implements multi-phase orchestration with independent worker re-examination. Later stages receive prior arbiter syntheses appended to original context. However, the context is optimized for git-based code artifacts and would need adaptation for generic artifact types.

---

## What Currently Exists

### 1. Multi-Stage Orchestrator ✓

**File:** `arbitration/orchestrator.py` (lines 291-513)

**Class:** `ArbitrationOrchestrator`

**Capabilities:**
- ✓ Configurable number of phases
- ✓ Configurable workers per phase
- ✓ Automatic model diversity (different models in each phase)
- ✓ Phase-specific instructions (discovery → challenge → validation)
- ✓ Context preservation across stages
- ✓ Arbiter synthesis between phases

**Information Flow:**

```
Phase 1 Workers:
  Receive: git_diff + full_files + related_context

Phase 1 Arbiter:
  Receives: git_diff + full_files + related_context + all_worker_results
  Returns: synthesis + selected_best_worker
  
Phase 2 Workers:
  Receive: git_diff + full_files + related_context + ARBITER_1_SYNTHESIS
  
Phase 2 Arbiter:
  Receives: git_diff + full_files + related_context + ARBITER_1_SYNTHESIS + new_worker_results
  Returns: synthesis + selected_best_worker
```

**Data Structures:**
- `WorkerResult` — model, phase, analysis, confidence, key_findings
- `ArbiterResult` — model, phase, synthesis, selected_best, rationale, next_phase_questions
- `PhaseConfig` — phase_num, workers, arbiter, instructions

### 2. Context Management ✓

**File:** `arbitration/orchestrator.py` (lines 124-288)

**Class:** `ContextManager`

**Methods:**
- `load_git_diff(repo_path, target_branch)` — Loads git diffs and changed files
- `load_directory(dir_path, extensions, max_files)` — Loads modules/packages
- `load_files(file_paths)` — Loads specific files
- `load_related_context(repo_path, changed_files)` — Auto-loads imports
- `get_worker_context()` — Assembles context string
- `add_arbiter_output(arbiter_output)` — Appends synthesis to context for next phase

**Token Estimation:**
- Estimates ~4 chars per token
- Truncates files >10K lines (line 280)
- Limits directory loads to 50 files (line 159)

### 3. Model Pool Management ✓

**File:** `arbitration/orchestrator.py` (lines 68-122)

**Class:** `ModelPool`

**Tiers:**
- cheap: [haiku]
- balanced: [sonnet, gemini-flash]
- expensive: [opus, cursor, gemini-pro]

**Guarantees:**
- No worker model repeats across phases
- All arbiters are different
- Phase 1 uses balanced tier, phases 2+ use expensive tier

### 4. Cost Tracking ✓

**File:** `arbitration/cost_tracker.py` (lines 144-333)

**Class:** `CostTracker`

**Tracking:**
- Per-worker token usage
- Per-arbiter token usage
- Token counts by input/output
- Model pricing lookup
- Estimates total USD cost

**Persistence:**
- Memory Service (Markdown with semantic signals)
- Canonical log (`cost_tracking/api_costs.jsonl`)
- Human-readable reports

### 5. Testing Infrastructure ✓

**Files:**
- `test_request_correlation.py` — Request lifecycle
- `test_validators.py` — Field validation
- `cost_tracking/test_*.py` — Cost tracking tests
- `alert_service/test_*.py` — Alert delivery tests

---

## What Is Missing / Limited

### 1. Generic Artifact Support ✗

**Current State:** System assumes git-based code artifacts
- `load_git_diff()` — Specific to git repos
- `load_directory()` — Assumes filesystem
- `load_related_context()` — Looks for imports (Python/JS/Go specific)

**Missing:** General artifact ingestion for non-code artifacts
- Documents (Markdown, Word)
- Designs (Figma descriptions, architecture diagrams)
- Proposals, requirements, specifications
- Research papers, reports, configurations

### 2. Finding Schema ✗

**Current State:** `WorkerResult` has unstructured `analysis` and `key_findings`
```python
@dataclass
class WorkerResult:
    model: str
    phase: int
    analysis: str  # Prose, not structured
    confidence: float
    key_findings: List[str]  # Simple strings, not structured findings
```

**Missing:**
- Structured Finding objects with severity, category, location, evidence
- Disposition tracking (confirmed, refuted, modified, new)
- Prior finding references for later stages
- Evidence preservation for independent verification

### 3. Arbiter Decision Model ✗

**Current State:** Arbiter returns synthesis + "selected best worker"
```python
@dataclass
class ArbiterResult:
    model: str
    phase: int
    synthesis: str  # Prose
    selected_best: str  # Which worker was "best"
    rationale: str
    next_phase_questions: Optional[List[str]]
```

**Missing:**
- Structured findings (not just prose synthesis)
- Explicit disposition per finding (confirmed/refuted/modified/new)
- Evidence assessment (which findings are well-supported)
- Contradiction detection (conflicts between findings)
- Confidence scoring per finding (not just overall)

### 4. Information Flow Verification ✓ Partial

**Positive:**
- Original artifact IS preserved across stages
- Original context IS passed forward
- Arbiter synthesis IS appended to later-stage context

**Concern:**
- Arbiter returns prose synthesis, not structured findings
- Workers receive synthesis, may focus on it instead of re-examining artifact
- No explicit instruction to challenge prior findings (only "Challenge the prior synthesis")
- Deduplication/consolidation happens in arbiter prose, not structured data

### 5. Finding Deduplication ✗

**Current State:** None. Each worker's findings are separate `key_findings: List[str]`

**Missing:**
- Formal consolidation of duplicate findings
- Identification of same finding found by multiple workers
- Dedup efficiency metrics (5 workers × 3 findings each = ? unique findings)
- Confidence boosting when finding confirmed by multiple workers

### 6. Storage / Persistence ✗

**Current State:** Results stored only in memory during execution
- Results in `ArbitrationOrchestrator.results` list
- Cost tracker writes to `cost_tracking/api_costs.jsonl`
- Memory Service stores cost summaries (Markdown)

**Missing:**
- Persistent storage of worker outputs
- Persistent storage of arbiter outputs per stage
- Complete audit trail of findings evolution across stages
- Queryable review database

### 7. Independent Re-examination Guidance ✗ Partial

**Current State:** Phase-specific instructions
- Phase 0: "Analyze independently"
- Phase 1: "Challenge the prior synthesis"
- Phase 2+: "Does the decision hold up?"

**Concern:**
- No explicit instruction that previous reviews may be wrong
- No specific guidance to look for missed edge cases, false positives, unsupported assumptions
- Instruction says "challenge synthesis" but workers get prose synthesis, not structured claims to evaluate

**Needed:**
- Explicit anti-anchoring instructions
- Structured claims to challenge (from Finding schema)
- Evidence to independently verify
- Specific examples of what prior stage may have missed

---

## What's Working Well (Don't Rewrite)

1. ✓ **Multi-phase orchestration** — Core loop is solid
2. ✓ **Model diversity** — ModelPool prevents confirmation bias
3. ✓ **Context management** — Artifact loading and passing is robust
4. ✓ **Cost tracking** — Token counting and pricing is accurate
5. ✓ **Phase progression** — Instructions change appropriately
6. ✓ **Worker/arbiter separation** — No model repeats

---

## Information Flow Assessment

### What Each Stage Actually Receives

**Stage 1 Worker:**
- ✓ Complete git diff (all changed lines)
- ✓ Complete files (entire source files that changed)
- ✓ Related files (auto-detected imports/dependencies)
- ✗ No structured review objective (only task description)
- ✗ No structured finding schema for output

**Stage 1 Arbiter:**
- ✓ Same context as workers
- ✓ All worker analyses (unstructured prose)
- ✓ Worker confidence scores
- ✗ No way to track which worker found what
- ✗ No structured finding schema

**Stage 2+ Workers:**
- ✓ Original context (git diff + files + related)
- ✓ Arbiter synthesis from prior stage (appended as text)
- ✗ No access to individual worker results from prior stage
- ✗ No structured findings to refute/confirm
- ✗ Prone to anchoring on arbiter's prose synthesis

**Stage 2+ Arbiter:**
- ✓ Original context
- ✓ Prior arbiter synthesis
- ✓ New worker analyses
- ✗ No structured findings from prior stage to compare against
- ✗ Cannot explicitly confirm/refute prior findings
- ✗ Cannot track finding disposition evolution

---

## Missing Information Causing Blind Spots

**Blind Spot 1: Unstructured Findings**
- Workers produce prose analysis + list of string findings
- Arbiter produces prose synthesis
- Later stages cannot independently verify or refute because claims aren't parsed

**Blind Spot 2: No Finding Deduplication**
- 3 workers × 3 findings = unclear if 9 unique issues or duplicates
- No efficiency metric
- No confidence boosting

**Blind Spot 3: Arbiter Consolidation Loss**
- Arbiter reads all worker prose
- Arbiter returns synthesis
- Later worker receives synthesis, not original worker findings
- Original finding details lost

**Blind Spot 4: No Explicit Disposition Tracking**
- Cannot mark finding as "confirmed" vs. "new" vs. "refuted"
- Later stages re-discover same issues (wasted analysis)
- No audit trail of how findings evolved across stages

**Blind Spot 5: Weak Anti-Anchoring**
- Workers told to "challenge prior synthesis" but prior is prose summary
- Cannot see original evidence/reasoning
- Cannot identify which claims lack support
- Default behavior: validate synthesis instead of independently examine artifact

---

## Needed Changes (Minimal, Surgical)

To make the system support generic artifacts and preserve information flow:

### Phase 1: Add Finding Schema

1. **Define `Finding` dataclass** (artifact-agnostic)
   - `id`, `subject`, `description`, `evidence`, `severity`, `category`
   - `confidence`, `disposition` (new/confirmed/refuted/modified)
   - `prior_finding_id` (if disposition != new)

2. **Update `WorkerResult`**
   - Add `findings: List[Finding]` field
   - Keep `analysis` for chain-of-thought (optional)

3. **Update `ArbiterResult`**
   - Add `findings: List[Finding]` field (synthesized)
   - Add `prior_dispositions: Dict[str, str]` (finding_id → disposition)
   - Keep `synthesis` field

### Phase 2: Preserve Prior Findings for Later Stages

1. **Store prior stage findings in context**
   - Instead of: just appending arbiter prose synthesis
   - Do: Append structured findings JSON to context
   - Workers can parse and challenge specific claims

2. **Update context passing**
   ```python
   # Instead of:
   current_context += f"\n\n## Prior Arbiter Synthesis\n\n{arbiter_output}"
   
   # Do:
   prior_findings_json = json.dumps([f.to_dict() for f in arbiter_output.findings])
   current_context += f"\n\n## Prior Stage Findings\n\n{prior_findings_json}"
   ```

### Phase 3: Update Worker Prompts

For Stage 2+ workers, add explicit anti-anchoring instruction:

```
"Previous stage findings are shown above. Treat them as HYPOTHESES TO TEST.
Do not merely validate them. Independently examine the original artifact.

Specifically:
- Which prior findings are strongly supported by the evidence?
- Which lack sufficient evidence?
- Which might be false positives?
- What assumptions did prior reviewers make?
- What did they miss?
- Mark your findings as: new | confirmed | refuted | modified"
```

### Phase 4: Add Finding Consolidation

```python
def consolidate_findings(worker_outputs: List[WorkerResult]) -> List[Finding]:
    """Deduplicate similar findings from multiple workers"""
    # Group similar findings
    # Mark duplicates
    # Return unique findings with source attribution
```

### Phase 5: Support Generic Artifacts

**Update `ContextManager`:**
```python
class ArtifactProvider:
    """Abstract artifact source"""
    def load() -> str: ...

class GitDiffProvider(ArtifactProvider):
    """Git repo artifact"""
    
class FileProvider(ArtifactProvider):
    """Raw file artifact"""
    
class DirectoryProvider(ArtifactProvider):
    """Directory of files"""
    
class URLProvider(ArtifactProvider):
    """Remote artifact (document, etc.)"""
```

Then:
```python
def load_artifact_by_type(artifact_type: str, location: str) -> str:
    if artifact_type == "code_review":
        return GitDiffProvider(location).load()
    elif artifact_type == "document":
        return FileProvider(location).load()
    elif artifact_type == "design":
        return DirectoryProvider(location).load()
    # ... etc
```

---

## Test Plan

### Existing Tests (Keep) ✓
- `test_request_correlation.py` — Still valid
- `test_validators.py` — Still valid
- Cost tracking tests — Still valid
- Alert tests — Still valid

### New Tests (Add)

1. **Information Flow Tests** ✓ *Already created*
   - Verify Stage 1 receives original
   - Verify Stage 2 receives original + prior findings
   - Verify findings preserve evidence
   - Verify disposition tracking

2. **Finding Schema Tests**
   - Validate Finding dataclass
   - Serialization/deserialization
   - Disposition tracking

3. **Consolidation Tests**
   - Deduplicate identical findings
   - Preserve minority findings with evidence
   - Confidence boosting

4. **Generic Artifact Tests**
   - Load document artifact
   - Load design artifact
   - Load proposal artifact
   - Verify context assembly is artifact-agnostic

5. **End-to-End Tests**
   - Run 2-stage review on non-code artifact
   - Verify Stage 2 finds something Stage 1 missed
   - Verify findings have dispositions
   - Verify evidence is preserved

---

## Implementation Roadmap

**Week 1:** Core data structures ✓ *Partially done*
- Finding schema
- Updated WorkerResult/ArbiterResult
- Finding consolidation logic

**Week 2:** Information flow
- Update context passing to include structured findings
- Update prompts for later stages
- Add disposition tracking logic

**Week 3:** Generic artifacts
- Add artifact provider abstraction
- Remove code-review-specific assumptions
- Add storage/persistence

**Week 4:** Testing & validation
- Information flow tests
- End-to-end tests
- Real artifact testing

---

## Conclusion

The existing system is **architecturally sound** for multi-stage review. It correctly implements independent worker re-examination, model diversity, and context preservation.

**Required changes are surgical, not structural:**
1. Add Finding schema (artifact-agnostic)
2. Preserve structured findings across stages (not just prose)
3. Update prompts to challenge prior findings explicitly
4. Add finding consolidation (dedup, disposition tracking)
5. Abstract artifact loading for generic types

These changes require < 500 lines of new code and minimal modifications to existing orchestrator.

---

**Next Step:** Implement Phase 1 (Finding Schema) and integrate with existing orchestrator.
