# Mock Audit - Production Code Review

## Summary
Audit of claude-ensemble production code for remaining mock implementations that bypass real execution.

## Files with Mock Fallbacks

### 1. review/worker_runner.py (Line 126-132)
**Issue:** Fallback mock response when api_client is None
```python
if self.api_client:
    return self.api_client.call_model(model, prompt)
else:
    # Fallback mock response
    logger.debug(f"No API client, returning mock response")
    return (json.dumps({
        "findings": [],
        "summary": "Mock worker response",
        "confidence": 0.8,
    }), 0, 0.0)
```
**Problem:** Returns (0 tokens, $0 cost) instead of raising error if API client missing

### 2. review/arbiter_runner.py (Line 92-96)
**Issue:** Fallback mock response when api_client is None
```python
if self.api_client:
    return self.api_client.call_model(model, prompt)
else:
    # Fallback mock response
    logger.debug(f"No API client, returning mock response")
    return (json.dumps({
        "findings": [],
        "summary": "Mock arbiter synthesis",
    }), 0, 0.0)
```
**Problem:** Returns (0 tokens, $0 cost) instead of raising error if API client missing

### 3. solve/pipeline.py (Lines 132-189)
**Issue:** Entire run() method is mock - no real Claude API calls
```python
def run(self) -> SolveResult:
    """Execute multi-stage solving pipeline"""
    # Mock execution: populate with sample solutions
    
    for stage_num, stage_config in enumerate(self.config.stages, 1):
        if stage_num == 1:
            # First stage: propose solutions to each problem
            solutions = []
            for i, problem in enumerate(self.request.problems):
                sol = SolutionProposal(
                    problem_statement=problem,
                    solution_description=f"Solution to: {problem[:50]}...",
                    confidence=0.85 + (i * 0.05),
                    # ... mock data ...
                )
```
**Problem:** No worker/arbiter execution, just hardcoded mock solutions

## Requirements
1. **Remove fallback mocks in worker_runner.py** - Require api_client, don't silently fail
2. **Remove fallback mocks in arbiter_runner.py** - Require api_client, don't silently fail  
3. **Replace mock execution in solve/pipeline.py** - Use real worker/arbiter execution
4. **Verify** - All pipelines now require real API client, no silent fallbacks

## Test Coverage Needed
- Multi-stage solve with real Claude API calls
- Multi-stage review with real Claude API calls
- Cost/token tracking from real API responses
- Service interaction metrics from real execution

## Acceptance Criteria
- [ ] No mock responses in worker_runner.py (raise error instead)
- [ ] No mock responses in arbiter_runner.py (raise error instead)
- [ ] solve/pipeline.py uses real worker/arbiter execution
- [ ] Multi-multi-review passes with real data only
- [ ] All tokens/costs reflect real API usage
