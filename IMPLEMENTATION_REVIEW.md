# Implementation Review - Mock Removal Fixes

## Summary
Review of three critical implementations that enforce real API execution.

## File 1: review/worker_runner.py - _call_model()

**Before (Mock Fallback):**
```python
def _call_model(self, model: str, prompt: str) -> tuple:
    """Call model API. Returns (response_text, tokens_used, cost)"""
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

**After (Real API Only):**
```python
def _call_model(self, model: str, prompt: str) -> tuple:
    """Call model API. Returns (response_text, tokens_used, cost)"""
    if not self.api_client:
        raise RuntimeError("API client required for worker execution. Cannot use mock fallbacks.")
    return self.api_client.call_model(model, prompt)
```

**Changes:**
- Removed conditional logic for api_client
- Now raises RuntimeError if api_client is None
- Eliminates silent failures with fake (0 tokens, $0 cost)
- Clear error message guides users to provide real API client

**Validation:**
- ✓ RuntimeError raised when api_client is None
- ✓ Real API call executed when api_client provided
- ✓ No fallback mock responses

---

## File 2: review/arbiter_runner.py - _call_arbiter_model()

**Before (Mock Fallback):**
```python
def _call_arbiter_model(self, model: str, prompt: str) -> tuple:
    """Call arbiter model API. Returns (response_text, tokens_used, cost)"""
    if self.api_client:
        return self.api_client.call_model(model, prompt)
    else:
        # Fallback mock response
        logger.debug(f"No API client, returning mock response")
        return (json.dumps({
            "findings": [],
            "summary": "Mock arbiter synthesis",
            "contradictions": [],
            "unresolved": [],
            "confidence": 0.8,
        }), 0, 0.0)
```

**After (Real API Only):**
```python
def _call_arbiter_model(self, model: str, prompt: str) -> tuple:
    """Call arbiter model API. Returns (response_text, tokens_used, cost)"""
    if not self.api_client:
        raise RuntimeError("API client required for arbiter execution. Cannot use mock fallbacks.")
    return self.api_client.call_model(model, prompt)
```

**Changes:**
- Removed conditional logic for api_client
- Now raises RuntimeError if api_client is None
- Eliminates silent failures with fake (0 tokens, $0 cost)
- Clear error message guides users to provide real API client

**Validation:**
- ✓ RuntimeError raised when api_client is None
- ✓ Real API call executed when api_client provided
- ✓ No fallback mock responses

---

## File 3: solve/pipeline.py - run()

**Before (Complete Mock Implementation):**
```python
def run(self) -> SolveResult:
    """Execute multi-stage solving pipeline"""
    # ... setup code ...
    
    # Mock execution: populate with sample solutions
    for stage_num, stage_config in enumerate(self.config.stages, 1):
        if stage_num == 1:
            # First stage: hardcoded mock solutions
            solutions = []
            for i, problem in enumerate(self.request.problems):
                sol = SolutionProposal(
                    problem_statement=problem,
                    solution_description=f"Solution to: {problem[:50]}...",
                    confidence=0.85 + (i * 0.05),  # Fake confidence
                    # ... more mock data ...
                )
            # ... stage_cost.worker_tokens = 2000 + (stage_num * 500)  <- HARDCODED MOCK
            # ... stage_cost.arbiter_tokens = 3000 + (stage_num * 1000)  <- HARDCODED MOCK
            # ... stage_cost.worker_cost = 0.060 + (stage_num * 0.015)  <- HARDCODED MOCK
```

**After (Real Worker/Arbiter Execution):**
```python
def run(self) -> SolveResult:
    """Execute multi-stage solving pipeline with real API calls"""
    if not self.api_client:
        raise RuntimeError("API client required for solve execution. Cannot use mock solutions.")
    
    # ... setup code ...
    
    # Real execution: use workers and arbiters for each stage
    for stage_num, stage_config in enumerate(self.config.stages, 1):
        from solve.worker_runner import SolveWorkerRunner
        from solve.arbiter_runner import SolveArbiterRunner
        
        # Run workers to generate solutions (REAL API CALL)
        worker_runner = SolveWorkerRunner(self.api_client, self.request, stage_config)
        worker_outputs = worker_runner.run_workers(self.request.problems, prior_solutions)
        
        # Track worker costs (FROM REAL API RESPONSES)
        for output in worker_outputs:
            stage_cost.worker_tokens += output.tokens_used  <- REAL TOKENS
            stage_cost.worker_cost += output.cost_usd  <- REAL COST
        
        # Run arbiter to synthesize (REAL API CALL)
        arbiter_runner = SolveArbiterRunner(self.api_client, self.request, stage_config)
        arbiter_output = arbiter_runner.run_arbiter(...)
        
        # Track arbiter costs (FROM REAL API RESPONSE)
        stage_cost.arbiter_tokens = arbiter_output.tokens_used  <- REAL TOKENS
        stage_cost.arbiter_cost = arbiter_output.cost_usd  <- REAL COST
```

**Changes:**
- Removed entire mock solution generation (was 60+ lines of hardcoded fake data)
- Added real worker/arbiter execution with API calls
- Imports SolveWorkerRunner and SolveArbiterRunner
- Tracks REAL tokens and costs from API responses
- Raises RuntimeError if api_client is None (no silent failures)
- Now actually generates solutions from Claude API

**Validation:**
- ✓ RuntimeError raised when api_client is None
- ✓ Workers called with real API (via SolveWorkerRunner)
- ✓ Arbiters called with real API (via SolveArbiterRunner)
- ✓ Token/cost tracking from actual API responses
- ✓ No hardcoded fake data

---

## Acceptance Criteria

### All Three Implementations:
- [x] No mock responses in code
- [x] No fake tokens/costs (0 tokens, $0 amounts)
- [x] No silent failures (raises RuntimeError if api_client missing)
- [x] Real API calls required
- [x] Error messages guide users to provide credentials

### Testing Verified:
- [x] worker_runner._call_model() raises RuntimeError when api_client is None
- [x] arbiter_runner._call_arbiter_model() raises RuntimeError when api_client is None
- [x] solve.pipeline.run() requires api_client (RuntimeError if None)

### Production Readiness:
- [x] No fallback mechanisms
- [x] No silent data loss
- [x] No misleading zero costs
- [x] All paths require real API execution
- [x] Clear error messages for missing credentials

## Impact
This refactor ensures:
1. **No Silent Failures** - Code fails loudly if API is not configured
2. **Real Metrics** - All tokens/costs come from actual Claude API calls
3. **Production Safe** - Cannot accidentally deploy with mock data
4. **Development Clear** - Developers know immediately if credentials are missing
