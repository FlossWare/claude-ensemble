# Multi-Stage Generic Review System Design

## Overview

A fully generic, artifact-agnostic multi-stage review pipeline that independently re-examines artifacts at each stage, using prior reviews as untrusted evidence to challenge, not conclusions to inherit.

## Core Architecture

### 1. Data Model

#### Review Request
```
ReviewRequest:
  id: str                          # Unique request ID
  artifact_type: str               # Generic: "code" | "document" | "design" | "proposal" | etc.
  objective: str                   # What to review and why
  artifact: ArtifactRef            # Pointer to artifact(s) being reviewed
  criteria: List[str]              # Review criteria (generic, e.g. "correctness", "completeness")
  context: Dict[str, Any]          # Optional supporting evidence
  metadata: Dict[str, Any]         # Custom metadata (varies by artifact type)
```

#### Artifact Reference (Generic)
```
ArtifactRef:
  location: str                    # Path, URL, or identifier
  content: str | List[str]         # Artifact content directly
  format: str                      # e.g. "code", "markdown", "json", "yaml"
  size_bytes: int                  # For large artifacts
  language: str                    # If applicable (Python, Rust, English, etc.)
```

#### Finding (Structured, Non-Code-Centric)
```
Finding:
  id: str                          # Unique finding ID
  severity: str                    # "critical" | "high" | "medium" | "low" | "info"
  category: str                    # e.g. "correctness", "performance", "clarity", "completeness"
  subject: str                     # Where in artifact (generic location description)
  description: str                 # What was found
  evidence: str                    # Concrete evidence from artifact
  impact: str                       # Why this matters
  recommendation: str              # How to address
  confidence: float                # 0.0-1.0
  
  # Disposition tracking (for later stages)
  disposition: str                 # "new" | "confirmed" | "refuted" | "modified" | "insufficient-evidence"
  prior_finding_id: str            # If disposition != "new"
  reasoning: str                   # Why prior finding was challenged
```

#### Stage Review
```
StageReview:
  stage_number: int                # 1, 2, 3, ...
  findings: List[Finding]          # All findings from this stage
  summary: str                      # Stage-level summary
  evidence_assessment: Dict         # Which findings have strong evidence
  contradictions: List[str]         # Contradictions within or across findings
  unresolved: List[str]            # Findings needing additional investigation
  confidence: float                # Overall stage confidence (0.0-1.0)
```

#### Multi-Stage Result
```
MultiStageReviewResult:
  request_id: str
  stages: List[StageReview]
  final_findings: List[Finding]    # Merged, deduplicated findings
  consensus: Dict                  # Agreement level by category
  open_questions: List[str]        # Unresolved issues
  recommendations: List[str]       # Actionable next steps
```

### 2. Filesystem Structure

```
review_workspace/
  {review_id}/
    request.json                   # Original review request
    artifact/
      original/
        {artifact_files}           # Complete original artifact(s)
    
    stages/
      001/
        stage_config.json          # Stage configuration
        workers/
          worker-001.json          # Worker result
          worker-002.json
          worker-003.json
        arbiter/
          arbiter-input.json       # What arbiter received
          arbiter-output.json      # Arbiter synthesis
        stage_review.json          # Compiled stage findings
      
      002/
        stage_config.json
        workers/
          worker-001.json
          worker-002.json
          worker-003.json
        arbiter/
          arbiter-input.json
          arbiter-output.json
        stage_review.json
    
    result.json                    # Final merged results
    log.jsonl                      # Event log
```

### 3. Configuration

```yaml
# review_config.yaml (reuses existing config pattern)
multistage_review:
  num_stages: 3                    # Number of stages
  workers_per_stage: 3             # Workers per stage
  
  stage_config:
    - stage: 1
      tier: "balanced"             # Model tier
      workers: 3
      arbiter: "sonnet"            # Model for this arbiter
      temperature: 0.7
      role: "discovery"
    
    - stage: 2
      tier: "balanced"
      workers: 3
      arbiter: "opus"
      temperature: 0.5
      role: "challenge"           # Challenge stage 1
    
    - stage: 3
      tier: "expensive"
      workers: 2
      arbiter: "opus"
      temperature: 0.3
      role: "validation"          # Final validation
  
  worker_diversity: true           # Ensure different models per stage
  preserve_originals: true         # Never replace artifact with reviews
  max_workers: 5                   # Maximum unique models to use
```

### 4. Stage Roles (Semantic Guidance)

#### Stage 1: Discovery
- Workers: Analyze thoroughly from their own perspective
- Focus: Find all possible issues, observations, opportunities
- Arbiter: Synthesize findings into coherent assessment
- Prompt: "Analyze this artifact thoroughly and independently..."

#### Stage 2: Challenge  
- Workers: Review ORIGINAL + Stage 1 results
- Focus: Find what Stage 1 missed, refute false positives, test assumptions
- Arbiter: Identify genuine issues vs. false alarms
- Prompt: "Review the original artifact and the prior review. Challenge the prior conclusions. What did they miss? What assumptions are unsupported?"

#### Stage 3: Validation
- Workers: Final review with full history
- Focus: Confirm critical findings, identify contradictions, validate recommendations
- Arbiter: Final synthesis, confidence assessment
- Prompt: "This is your final validation. Do the prior stages' conclusions hold under scrutiny? Any remaining concerns?"

## Implementation Plan

### Phase 1: Core Data Structures (Week 1)

1. **Create `review/` module**
   - `models.py` — Dataclasses for Finding, StageReview, ArtifactRef, ReviewRequest, etc.
   - `schema.py` — JSON schemas for validation
   - `storage.py` — Filesystem I/O (save/load findings, reviews, artifacts)

2. **Create `review/config.py`**
   - Load review_config.yaml
   - Provide stage/worker configuration
   - Validate config

3. **Tests**
   - `test_models.py` — Dataclass serialization
   - `test_storage.py` — Save/load cycle
   - `test_config.py` — Configuration loading

### Phase 2: Review Pipeline (Week 2)

1. **Create `review/pipeline.py`**
   - `ReviewPipeline` class
   - `initialize_workspace()` — Set up directory structure
   - `run_stage()` — Execute single stage
   - `run_all_stages()` — Execute full pipeline
   - Coordinate workers and arbiter per stage

2. **Create `review/worker_runner.py`**
   - `run_workers_parallel()` — Execute N workers on original artifact
   - Build worker prompts with original artifact + prior reviews
   - Collect findings

3. **Create `review/arbiter_runner.py`**
   - `run_arbiter()` — Synthesize worker results
   - Challenge prior findings
   - Identify contradictions
   - Compile stage review

4. **Tests**
   - `test_pipeline.py` — Full mock pipeline
   - `test_worker_runner.py` — Worker execution
   - `test_arbiter_runner.py` — Arbiter logic

### Phase 3: Prompting & Instructions (Week 3)

1. **Create `review/prompts.py`**
   - `build_worker_prompt()` — Generic worker instruction
   - `build_arbiter_prompt()` — Arbiter synthesis instructions
   - Stage-specific prompt variants (discovery, challenge, validation)
   - Include anti-anchoring guidance for later stages

2. **Create `review/instructions.py`**
   - Finding extraction instructions
   - Format expectations
   - Examples for different artifact types

3. **Tests**
   - `test_prompts.py` — Prompt building
   - Integration test with mock model responses

### Phase 4: Integration & Testing (Week 4)

1. **Integration**
   - Connect to existing `api_client.py` for model calls
   - Use existing `RequestContext` for tracing
   - Integrate with alert service if critical findings

2. **End-to-End Tests**
   - Mock artifact (code, document, design)
   - Run full 3-stage pipeline
   - Verify findings structure
   - Check that later stages challenge earlier findings
   - Verify originals are preserved

3. **CLI Interface**
   - Expose through existing ensemble CLI
   - `ensemble review <artifact> --objective "..." --stages 3`
   - No separate command — one generic interface

## Key Implementation Details

### Preventing Anchoring (Critical)

Later-stage workers receive explicit instructions:
```
"You are reviewing the underlying artifact and review objective.
Previous reviews are untrusted evidence to challenge, not conclusions to inherit.

Specifically, look for:
- Things previous reviewers missed
- Assumptions previous reviewers made without evidence
- Evidence contradicting previous findings
- False positives (things marked wrong but actually correct)
- Requirements not addressed
- Alternative interpretations
- Areas where previous reviewers stopped investigating too early"
```

### Original Artifact Preservation

Always pass original artifact to every stage:
```python
worker_context = {
    'original_artifact': original,
    'review_request': request,
    'prior_reviews': [stage1_review, stage2_review],  # If applicable
    'stage_number': current_stage,
    'worker_id': worker_id,
}
```

Never replace artifact with previous review.

### Finding Deduplication (Arbiter Responsibility)

Arbiter must:
1. Identify findings that are duplicates of prior stage
2. Mark as "confirmed" with supporting evidence
3. Mark as "refuted" with evidence why
4. Mark as "modified" if finding changed
5. Preserve minority findings with evidence

## Testing Strategy

1. **Unit Tests**
   - Dataclass serialization
   - Config loading
   - Filesystem operations
   - Prompt building

2. **Integration Tests**
   - Mock 3-stage pipeline with fake model responses
   - Verify findings structure
   - Check workspace structure
   - Verify challenge prompts are different from discovery

3. **Mock Tests**
   - Real orchestrator with mock API client
   - Verify worker/arbiter call sequence
   - Check that originals are preserved through all stages

4. **Acceptance Tests**
   - Small real artifact (brief code snippet or document)
   - Run with real models (use cheapest tier)
   - Verify findings are coherent
   - Check that stage 2 actually challenges stage 1

## What NOT to Do

- ❌ Don't replace artifact with prior review
- ❌ Don't create code-specific field requirements
- ❌ Don't assume findings have line numbers, commits, etc.
- ❌ Don't build a majority-vote system
- ❌ Don't use external databases or services
- ❌ Don't require domain-specific metadata
- ❌ Don't create separate review commands per artifact type
- ❌ Don't store chain-of-thought (conclusions + evidence only)
- ❌ Don't use hard-coded model names
