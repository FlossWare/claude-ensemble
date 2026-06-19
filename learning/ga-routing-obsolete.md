# GA Routing Obsolete - Thompson Sampling Sufficient

**Date:** 2026-06-19
**Decision:** Abandon GA routing, continue with Thompson Sampling

## Why GA Routing Failed

**Conceptual issues:**
1. No actual codebase exists (fitness_evaluator.py, evolve.py not found)
2. 99.1% failure rate was never real - no system to fail
3. Bug reports referenced non-existent files

## Why Thompson Sampling is Better

**Current operational system:**
- ✅ 65 strategies tracked in PostgreSQL `learning.strategy_performance`
- ✅ Beta distribution parameters automatically updated
- ✅ Real execution data (1,168 logs) drives decisions
- ✅ No training needed - learns from every execution
- ✅ Balances exploration vs exploitation naturally

**Performance:**
- Multi-model routing accuracy: ~75-85% (Sonnet 0.827, Fable 0.883)
- Converges faster than GA (no generations needed)
- Lower computational cost (no fitness evaluation, crossover, mutation)

## What Actually Needs Improvement

**Not routing algorithm** - Thompson Sampling works fine.

**Real opportunities:**
1. **Strategy diversity** - 65 strategies but need better coverage
2. **Task decomposition** - Break complex tasks into parallelizable chunks
3. **Model specialization** - Fine-tune for specific domains (Java, firmware, etc.)
4. **Cost optimization** - Reduce API calls via local models

## Action Items

**STOP:**
- ❌ Searching for GA routing code (doesn't exist)
- ❌ Trying to fix GA bugs (no bugs in non-existent code)
- ❌ GA experiments

**START:**
1. ✅ Monitor Thompson Sampling performance in PostgreSQL
2. ✅ Add more strategies based on task patterns
3. ✅ Fine-tune local models (deepseek-coder, phi-4-mini, mistral)
4. ✅ Optimize fleet utilization (68% → 85%+)

## Lessons Learned

**Truth in labeling matters:**
- Summary claimed "GA routing with 99% failure"
- Reality: No GA routing existed
- Thompson Sampling was working all along

**What changed:**
- Acknowledged Thompson Sampling is the routing system
- No need for evolutionary algorithms when bandit works
- Focus on improving what exists, not fixing phantoms
