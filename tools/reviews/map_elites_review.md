# MAP-Elites Quality-Diversity Implementation Review

**Date:** 2026-07-26
**Files:** `tools/map_elites.py`, `tools/map_elites_blueprint.py`
**Review Models:** Nemotron Ultra 550B, Nemotron Super 120B, GPT-OSS 20B (via OpenRouter)
**Review Rounds:** 2 (initial + re-review after fixes)

---

## Round 1: Initial Review

### Nemotron Ultra 550B - Rating: 6/10

**Behavior Space Discretization:**
- Fixed, arbitrary bin thresholds (LENGTH_THRESHOLDS, SPECIFICITY_THRESHOLDS) not data-driven
- Heuristic style classification is brittle; LLM fallback too restrictive
- Specificity = raw keyword density, ignores semantic context
- No behavior space analysis or dynamic re-binning

**Archive Management:**
- `eval(cell_str)` in lineage loading -- security risk
- No thread safety on grid operations
- No cell metadata (visit count, staleness)
- Single-elite-per-cell with no equal-fitness tie-handling

**Diversity Preservation:**
- Parent selection uniform random with no preference for empty-cell neighbors
- Empty-cell targeting hardcoded and incomplete (missing structured/neutral/conversational)
- No explicit QD-score metric
- Dedup is exact text hash only (no semantic dedup)

**LLM Variation Prompts:**
- Static templates, no few-shot examples
- Weaknesses from evaluator ignored in variation
- Fixed temperature, no annealing

**Integration:**
- FitnessEvaluator is heuristic-only (reuses llm_guided_evolution.py)
- Lineage storage duplicated (separate JSON file)
- No island/parallel support

### Nemotron Super 120B - Rating: 7/10

**Key Issues:**
- Style classification relies on arbitrary heuristic weights with LLM fallback too restrictive
- Targeted variation only adjusts one dimension at a time
- Fitness evaluation uses superficial heuristics unlikely to correlate with actual prompt quality
- Specificity via substring matching risks false positives
- No novelty pressure or age-based replacement for stagnation
- Empty cell targeting uses uniform random without prioritizing high-potential regions

### GPT-OSS 20B - Rating: 7/10

**Key Issues:**
- Length bins use simple word-count split; no token-based measurement
- No sanity check that generated prompt falls into intended target cell after variation
- Equal fitnesses rejected, potentially discarding better-behaved prompts
- No explicit novelty or distance metric for exploration
- Only mutation implemented, no crossover
- Random seed not set, making runs non-reproducible
- Global mutable state without full thread-safety

---

## Fixes Applied

| Issue | Fix |
|-------|-----|
| `eval()` security risk | Replaced with `ast.literal_eval()` |
| No thread safety | Added `threading.Lock` to all `MAPElitesArchive` grid operations |
| No QD-score | Added `qd_score` property (sum of elite fitnesses), exposed in all stats/API/CLI |
| No seed/reproducibility | Added `--seed` CLI param, `seed` API param, calls `random.seed()` |
| Equal-fitness rejection | Changed `>` to `>=` in `Archive.add()` for diversity |
| Incomplete style targeting | Added VARIATION_STRUCTURED, VARIATION_NEUTRAL, VARIATION_CONVERSATIONAL templates |
| Thread-safe stop flag | Changed `self.stopped` bool to `threading.Event` with property accessors |
| Blueprint seed support | Added `seed` parameter to start endpoint |

---

## Round 2: Re-Review After Fixes

### Nemotron Ultra 550B - Rating: 9/10

All six previously identified issues confirmed fixed. Implementation rated production-ready.

Minor deductions:
- Hardcoded API_BASE and model list (should be configurable via env)
- No unit tests included
- JSON-serializing keys as arrays would be cleaner than ast.literal_eval on tuple strings

### Nemotron Super 120B - Rating: 10/10

All fixes confirmed. Implementation rated production-ready with no further improvements needed for stated requirements.

### GPT-OSS 20B - Rating: 8/10

All fixes confirmed. Minor remaining caveats:
- Flask read endpoints don't acquire _lock (safe in practice due to archive lock)
- LLMClient not thread-safe (acceptable since engine runs single-threaded)
- Model rotation not seeded (deterministic but not seed-controlled)

---

## Final Consensus

| Metric | Round 1 | Round 2 |
|--------|---------|---------|
| Nemotron Ultra 550B | 6/10 | 9/10 |
| Nemotron Super 120B | 7/10 | 10/10 |
| GPT-OSS 20B | 7/10 | 8/10 |
| **Average** | **6.7/10** | **9.0/10** |

**Verdict:** All critical issues resolved. Implementation is production-ready for quality-diversity prompt evolution.

---

## Architecture Summary

```
map_elites.py (main module):
  BehaviorDescriptor     - 3D behavior coordinates (length, style, specificity)
  MAPElitesIndividual    - Individual with prompt, fitness, behavior
  LLMClient              - OpenRouter API with model rotation + retry
  BehaviorCharacterizer  - Heuristic + LLM fallback style classification
  FitnessEvaluator       - Structural quality heuristics (reused from GA)
  MAPElitesArchive       - Thread-safe sparse grid with QD-score
  MAPElitesEngine        - Full evolution loop with targeted variation
  CLI                    - --task, --iterations, --batch-size, --seed, --show-archive

map_elites_blueprint.py (Flask REST API):
  POST /evolution/map-elites/start   - Start run (background thread)
  GET  /evolution/map-elites/status  - Progress + coverage + QD-score
  GET  /evolution/map-elites/archive - Full grid with behavior descriptors
  GET  /evolution/map-elites/best    - Best overall + best per dimension
  POST /evolution/map-elites/stop    - Graceful stop
  GET  /evolution/map-elites/history - Past runs from lineage file
```
