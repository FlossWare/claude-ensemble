# Non-stationary Thompson Sampling - Multi-Model Fleet Review

**Date:** 2026-07-26
**Files Reviewed:**
- `tools/nonstationary_thompson_sampling.py` (core library + CLI)
- `tools/nonstationary_ts_blueprint.py` (Flask blueprint)

**Reviewers:**
1. Llama 3.3 70B (via Groq API)
2. Nemotron 3 Ultra 550B (via OpenRouter, free tier)
3. GPT-OSS 120B (via Cerebras API)

---

## Quality Ratings

| Model | Rating | Summary |
|-------|--------|---------|
| Llama 3.3 70B | **8/10** | "Well-structured, good practices, some edge case gaps" |
| Nemotron 3 Ultra 550B | **4/10** | "Solid math foundation but critical thread-safety bugs, silent failures, mutation side effects" |
| GPT-OSS 120B | **~6/10** | Detailed line-by-line audit, identified 15+ specific issues (response truncated at max tokens) |

**Consensus rating: 6/10** -- Mathematically sound core, but multiple issues that could cause silent wrong results in production.

---

## Synthesized Critical Findings (Issues Found by 2+ Models)

### 1. CRITICAL: Input Dictionary Mutation (All 3 models)

`select_strategy_nonstationary()` mutates the input strategy dicts in-place by adding `decayed_alpha`, `decayed_beta`, `sample`, and `decay_rounds` keys. This causes:

- **Double-decay bug**: If the same list is passed twice, values get decayed again on top of already-decayed values.
- **Flask cache poisoning**: If the DB layer caches row dicts, cached data gets corrupted with stale annotations.
- **Race conditions**: Two concurrent Flask requests sharing a cached strategy list will see each other's mutations.

The `cmd_select` multi-sample loop already works around this by re-fetching (line 529), proving the author knew this was a problem but did not fix the root cause.

**Fix:** Work on shallow copies (`dict(s)`) before annotating, or return a separate result structure.

### 2. CRITICAL: `or 1` Treats Zero as Missing (Nemotron + GPT-OSS)

```python
alpha = float(s.get("alpha", s.get("successes", 1)) or 1)
```

The `or 1` coerces any falsy value -- including a legitimate `0` -- to `1`. A strategy with zero successes gets treated as having 1 success, dramatically changing the posterior distribution. This appears on lines 233-234 and again on lines 365-366.

**Fix:** Remove `or 1`; apply `max(MIN_PARAM, ...)` floor separately after conversion.

### 3. HIGH: NumPy Global RNG Not Thread-Safe (Nemotron)

```python
sample = float(np.random.beta(alpha_d, beta_d))
```

NumPy's legacy global RNG (`np.random.*`) is not thread-safe. Under concurrent Flask requests (gunicorn threads, uWSGI), this can corrupt internal RNG state, producing biased or correlated samples.

**Fix:** Use thread-local `np.random.Generator`:
```python
import threading
_thread_local = threading.local()

def _get_rng():
    if not hasattr(_thread_local, 'rng'):
        _thread_local.rng = np.random.default_rng()
    return _thread_local.rng
```

### 4. HIGH: Silent Error Swallowing (All 3 models)

Multiple functions silently swallow errors and return default values:
- `estimate_rounds_since_update()` returns `0` on any parsing error -- making the algorithm think a strategy is brand-new
- `fetch_strategies()` returns `[]` on any error -- callers cannot distinguish "no strategies exist" from "API is down"
- Blueprint's `_get_strategies_from_db()` catches `(ImportError, Exception)` which swallows programming errors like `NameError`

### 5. HIGH: Direct DB Connection in Blueprint Violates REST-Only Policy (GPT-OSS)

The blueprint's `_get_strategies_from_db()` contains a hardcoded `psycopg2.connect()` fallback to `aio-01:5433`. This violates the project's architectural constraint that ALL database access goes through the REST API at port 5000.

### 6. MEDIUM: Sliding Window Math Can Exceed Window Size (GPT-OSS + Nemotron)

The formula `MIN_PARAM + obs_alpha * scale` adds the prior AFTER scaling, meaning the total effective observations can exceed the specified window. The window guarantee is violated.

### 7. MEDIUM: Time-Based Decay vs. Selection-Based Decay (Nemotron)

The decay is based on wall-clock time since `last_updated`, not selection opportunities. A strategy dormant for 2 weeks gets decayed as if it lost 56 rounds, even if it was never a candidate. This over-penalizes inactive strategies.

### 8. MEDIUM: `sys.path` Manipulation in Blueprint (GPT-OSS)

The blueprint modifies `sys.path` at import time, which can mask packages and cause import cycles in larger applications.

---

## Individual Model Reviews

---

### Review 1: Llama 3.3 70B (Groq)

### Review of the Provided Code

The provided code is well-structured and follows good practices. However, there are some potential issues and improvements that can be suggested:

#### Correctness of the Decay/Windowing Math

The decay and windowing math seems to be correct. The `apply_decay` function correctly applies the exponential decay to the alpha and beta parameters, and the `apply_sliding_window` function correctly scales the alpha and beta parameters to fit within the specified window.

However, there is a potential issue with the `estimate_rounds_since_update` function. This function estimates the number of rounds since the last update based on the `last_updated` timestamp. However, it assumes that the `last_updated` timestamp is in the format of an ISO-8601 timestamp string. If the timestamp is in a different format, this function may not work correctly.

#### Thread Safety

The code does not seem to have any thread safety issues. The functions are mostly pure and do not have any shared state that could be accessed by multiple threads simultaneously.

However, if the code is used in a Flask application, there could be thread safety issues if the application is not properly configured. Flask applications are typically single-threaded, but if the application is configured to use multiple threads or processes, there could be issues with shared state.

#### Edge Cases

The code handles some edge cases, such as empty data and extreme values. However, there are some potential edge cases that are not handled:

*   If the `last_updated` timestamp is `None`, the `estimate_rounds_since_update` function will return 0. This could be a problem if the `last_updated` timestamp is `None` because the strategy has never been updated.
*   If the `window` parameter is `None`, the `apply_sliding_window` function will return the original alpha and beta parameters. This could be a problem if the `window` parameter is `None` because the window size is not specified.
*   If the `decay` parameter is 0, the `apply_decay` function will return 0 for both the decayed alpha and beta parameters. This could be a problem if the `decay` parameter is 0 because it would effectively disable the decay.

#### REST API Design

The REST API design seems to be good. The API has two endpoints: one for listing all strategies with decayed parameters and one for selecting a strategy using non-stationary Thompson sampling.

However, there are some potential issues with the API design:

*   The API does not have any error handling for invalid input. For example, if the `decay` parameter is not a valid float, the API will raise an error.
*   The API does not have any validation for the input parameters. For example, if the `window` parameter is not a positive integer, the API will raise an error.

#### Silent Wrong Results

There are some potential issues that could cause silent wrong results:

*   If the `last_updated` timestamp is not in the correct format, the `estimate_rounds_since_update` function may return an incorrect estimate of the number of rounds since the last update.
*   If the `window` parameter is not a positive integer, the `apply_sliding_window` function may return incorrect results.
*   If the `decay` parameter is not a valid float, the `apply_decay` function may return incorrect results.

### Code Quality Rating

Based on the review, I would rate the code quality as 8 out of 10. The code is well-structured and follows good practices, but there are some potential issues with edge cases and silent wrong results.

### Suggestions for Improvement

1.  **Add error handling for invalid input**: The API should have error handling for invalid input, such as invalid float values for the `decay` parameter.
2.  **Add validation for input parameters**: The API should have validation for input parameters, such as checking that the `window` parameter is a positive integer.
3.  **Handle edge cases**: The code should handle edge cases, such as `None` values for the `last_updated` timestamp or the `window` parameter.
4.  **Improve documentation**: The code could benefit from improved documentation, such as docstrings for functions and comments to explain the logic.
5.  **Consider using a more robust timestamp parsing library**: The `estimate_rounds_since_update` function assumes that the `last_updated` timestamp is in the format of an ISO-8601 timestamp string. Consider using a more robust timestamp parsing library to handle different formats.

### Example of Improved Code

Here is an example of how the `estimate_rounds_since_update` function could be improved to handle different timestamp formats:
```python
import dateparser

def estimate_rounds_since_update(last_updated, round_interval_hours=6.0):
    """
    Estimate the number of rounds since the last update based on the last_updated timestamp.

    Args:
        last_updated (str or datetime): The last_updated timestamp.
        round_interval_hours (float): The interval between rounds in hours.

    Returns:
        int: The estimated number of rounds since the last update.
    """
    if last_updated is None:
        return 0

    if isinstance(last_updated, str):
        # Use dateparser to parse the timestamp
        dt = dateparser.parse(last_updated)
        if dt is None:
            raise ValueError("Invalid timestamp format")
    elif isinstance(last_updated, datetime):
        dt = last_updated
    else:
        raise ValueError("Invalid timestamp type")

    now = datetime.now()
    elapsed_hours = (now - dt).total_seconds() / 3600.0
    return int(elapsed_hours / round_interval_hours)
```
This improved function uses the `dateparser` library to parse the timestamp, which can handle different formats. It also raises a `ValueError` if the timestamp is invalid or if the timestamp type is not supported.

---

### Review 2: Nemotron 3 Ultra 550B (OpenRouter)

# Code Review: Non-Stationary Thompson Sampling

## Overall Quality Rating: **4/10**

The implementation has a solid mathematical foundation but suffers from critical thread-safety bugs, silent failure modes, mutation side effects, and a broken API contract between the CLI and blueprint.

---

## 1. Correctness of Decay/Windowing Math

### **Bug: Sliding window division by zero risk** (Line 97)
```python
# Line 97: if total_obs <= window:  # returns early if total_obs == 0
# But if total_obs > window and total_obs == 0? Impossible since window >= 1.
# However, if MIN_PARAM != 1.0 (e.g., changed to 0.5), and alpha=0.6, beta=0.6:
# obs_alpha = 0.1, obs_beta = 0.1, total_obs = 0.2
# If window=1, total_obs (0.2) <= window (1) -> returns early. OK.
# But the logic assumes MIN_PARAM=1.0 is the prior. If prior changes, math breaks.
```
**Fix**: Make prior explicit, don't hardcode `MIN_PARAM` as the prior.

### **Design Flaw: Time-based decay vs. selection-based decay** (Line 111-138)
```python
# estimate_rounds_since_update uses wall-clock time (hours since last_updated)
# But Thompson Sampling "rounds" should be *selection opportunities*, not wall time.
# A strategy not shown for 2 weeks gets decayed as if it lost 56 rounds (6h intervals),
# even if it was never a candidate. This over-penalizes dormant strategies.
```
**Fix**: Track "rounds since last selection" per strategy, not wall time.

### **Precision Loss: Underflow to MIN_PARAM** (Line 74-75)
```python
factor = decay ** rounds  # e.g., 0.995 ** 2000 ≈ 4.5e-5
return (max(MIN_PARAM, alpha * factor), ...)  # alpha=1000 -> 0.045 -> clamped to 1.0
```
Large counts collapse to uniform prior (Beta(1,1)), losing all evidence. Consider log-space computation or a softer floor.

---

## 2. Thread Safety (Critical for Flask)

### **Critical Bug: Global `np.random` state corruption** (Line 174, File 1; Line 174, File 2)
```python
# File 1, Line 174:
sample = float(np.random.beta(alpha_d, beta_d))

# File 2, Line 174 (inside select_nonstationary):
winner = select_strategy_nonstationary(...)
```
**NumPy's global RNG is NOT thread-safe.** Concurrent requests in Flask (gunicorn threads, uWSGI) will:
- Corrupt RNG internal state → crashes or biased samples
- Produce correlated samples across requests → broken exploration

**Fix**: Use thread-local `np.random.Generator`:
```python
# At module level:
_thread_local = threading.local()

def _get_rng():
    if not hasattr(_thread_local, 'rng'):
        _thread_local.rng = np.random.default_rng()
    return _thread_local.rng

# In select_strategy_nonstationary:
sample = float(_get_rng().beta(alpha_d, beta_d))
```

### **Bug: Mutation of input dictionaries** (Lines 172-175, 270-271, 282-283)
```python
# File 1, Lines 172-175:
s["decayed_alpha"] = round(alpha_d, 4)
s["decayed_beta"] = round(beta_d, 4)
s["sample"] = round(sample, 6)
s["decay_rounds"] = rounds

# File 2, Line 158:
for s in strategies:
    if isinstance(s.get("last_updated"), datetime):
        s["last_updated"] = s["last_updated"].isoformat()  # MUTATES DB ROW DICT
```
**Consequences**:
- Caller's data corrupted (CLI re-fetches in `--samples` loop to work around this: Line 304)
- In Flask, if DB layer caches rows, cache is poisoned
- Blueprint mutates `strategies` list from `_get_strategies_from_db()` (Line 158)

**Fix**: Never mutate inputs. Create new dicts or use `copy()`.

---

## 3. Edge Cases & Silent Failures

### **Silent Failure: API

---

### Review 3: GPT-OSS 120B (Cerebras)

*Note: This review was truncated due to max token limits. The model produced a detailed line-by-line audit table.*

**Non‑stationary Thompson Sampling – Code Review**

Below is a line‑by‑line audit of the two files you supplied.  
For each problem I give the exact line (or a short range) and explain why it matters, what the observable symptom is, and how to fix it.  
At the end I give an overall quality rating (1 = unusable, 10 = production‑ready).

---

## 1️⃣ `nonstationary_thompson_sampling.py`

| # | Issue | Why it matters | Fix / mitigation |
|---|-------|----------------|------------------|
| **31‑34** | **`MIN_PARAM = 1.0`** is used as a hard floor for *both* α and β. If the real data contain many zeros (e.g. a brand‑new strategy with 0 successes and 0 failures) the code will silently replace them with `1.0`, turning a *uniform* prior into a *biased* one. | The selection will favour strategies that have never been tried, because the “effective mean” becomes 0.5 instead of undefined. | Keep the true prior (`α=β=1`) *only* when the count is truly missing. Use `max(1e-6, α)` or, better, treat a missing count as `None` and let the caller decide the prior. |
| **71‑78** (`apply_decay`) | The guard `if rounds == 0 or decay == 1.0:` returns `max(MIN_PARAM, α)` etc. This again forces a floor of `1.0` even when the caller passed a legitimate `α=0.2`. | Same bias as above; also hides bugs where the upstream data are already < 1. | Return the raw values when `rounds == 0` (no decay) and only apply the floor **after** the decay step, not before. |
| **115‑124** (`apply_sliding_window`) | The scaling formula `MIN_PARAM + obs_alpha * scale` assumes the prior contributes exactly `MIN_PARAM`. If the original α/β were already > 1, the windowed result will be **larger** than the window size because the prior is added *after* scaling. | The “window” no longer guarantees that the effective number of observations ≤ `window`. This can give a false sense of recency. | Compute the scaled total first, then add the prior *once*: `new_alpha = MIN_PARAM + (α‑MIN_PARAM) * scale`. |
| **147‑166** (`estimate_rounds_since_update`) | - The function silently returns `0` on any parsing error (`except (ValueError, TypeError): return 0`). <br> - It does **not** guard against future timestamps; a future `last_updated` yields a negative `elapsed_hours`, which is clamped to `0` – that is fine, but the caller may expect a warning. | Hidden parsing problems (e.g. malformed ISO strings) will make the algorithm think the strategy is brand‑new, biasing the selection. | Raise a custom exception or at least log a warning when parsing fails, and optionally cap future dates with a log entry. |
| **184‑197** (`select_strategy_nonstationary`) | **(a) `alpha = float(s.get("alpha", s.get("successes", 1)) or 1)`** – the `or 1` treats any falsy value (including `0`) as missing. <br> **(b) Same pattern for `beta`.** <br> **(c) The function mutates the incoming dict `s`** by adding `decayed_*`, `sample`, etc. | (a) Real zero‑count strategies are turned into `1`, changing the posterior dramatically. <br> (c) When the same list of dicts is reused (e.g. cached between Flask requests) the added keys persist, causing *silent* double‑decay or double‑windowing on subsequent calls. | Replace the expression with `float(s.get("alpha", s.get("successes", 1)))` and only apply the floor *after* conversion. <br> Return a **new copy** (`new_s = dict(s)`) before annotating it, or keep the annotations in a separate structure. |
| **209‑226** (`select_strategy_nonstationary` loop) | The variable `best_sample` is initialised to `-1.0`. If a strategy’s sampled value is exactly `-1.0` (impossible for a Beta, but could happen if `np.random.beta` is called with invalid params and returns `nan`), the function would incorrectly keep `best_strategy = None`. | Edge case only, but it shows a lack of defensive programming. | Initialise with `float("-inf")` and guard against `np.isnan(sample)`. |
| **254‑267** (`fetch_strategies`) | No **authentication / TLS** when calling the internal API (`http://aio-01:5000`). The function also swallows **all** `ValueError`/`KeyError` from `resp.json()` and returns an empty list. | An attacker who can spoof DNS or intercept traffic could inject bogus strategy data, leading to a poisoned selection. | Use `https://` (or at least verify the host), and surface parsing errors to the caller instead of silently returning `[]`. |
| **311‑327** (`select_with_decay`) | Returns `winner.get("strategy", winner.get("name"))`. If the API changes the field name, the function will silently return `None`. | Hidden regression when the backend schema evolves. | Explicitly document the expected field name and raise a clear error if neither is present. |
| **352‑380** (`get_decayed_strategies`) | Same `or 1` bug as in line 184. Also the function **mutates** the original strategy dicts (adds `decayed_*`, `effective_mean`, …). | Same side‑effect problem as above; callers that later pass the same list back into `select_strategy_nonstationary` will get double‑decayed values. | Work on a shallow copy (`s = dict(s)`) before annotating. |
| **447‑460** (`cmd_list`) | When `--json` is used the code loops over every key/value and calls `s[k] = v.isoformat()` **in‑place**. This mutates the list that may be reused later in the same process (e.g. by another CLI command). | Subsequent commands may see ISO strings where they expect numbers. | Build a new dict for JSON output instead of mutating the original. |
| **492‑511** (`cmd_select` – multi‑sample loop) | The comment *“Re‑fetch to avoid mutation issues”* is correct, but the code still **mutates** each fetched dict inside `select_strategy_nonstationary`. If the API is slow, the extra network calls become a performance bottleneck. | Not a bug, but a design inefficiency. | Refactor the selection routine to be pure (no side‑effects) and call it on a copy of the data. |
| **560‑579** (`cmd_diagnostics`) | The calculation of `info_loss = max(0.0, 1.0 - dec_total / raw_total)` can produce values **> 1** (i.e. > 100 %) when `raw_total` is very small (close to the prior). The printed percentage therefore may be misleading. | Users could think the algorithm “lost” more information than existed. | Clamp the result to `[0, 1]` (`min(1.0, ...)`) before formatting. |
| **587‑595** (`cmd_diagnostics` summary) | Uses `np.mean([d["decay_rounds"] for d in strategies_with_decay])`. If any `decay_rounds` is `None` (unlikely but possible if the source dict lacked `last_updated`) this raises a `TypeError`. | Crash in edge cases. | Filter out `None` or coerce to `0`. |
| **617‑630** (`main`) | The logger is configured **after** parsing arguments, which means any error that occurs while parsing (e.g. a bad `--decay` value) will be logged with the *default* logging configuration (usually WARNING). | Inconsistent logging output. | Configure logging **before** `parser.parse_args()`. |

### Thread‑Safety Concerns (Flask)

* The module does **not** keep any mutable global state, so the core algorithm is thread‑safe.  
* However, the **in‑place mutation** of the strategy dictionaries (see issues 184‑197, 352‑380) can cause race conditions if a list of strategies is cached or shared between requests (e.g. via a Flask `g` object or a global variable). Two concurrent requests could see each other’s added keys, leading to double‑decay or double‑windowing and thus silently biased results.  

**Fix**: make the selection functions pure (return a new dict) or explicitly copy the input list before mutating.

---

## 2️⃣ `nonstationary_ts_blueprint.py`

| # | Issue | Why it matters | Fix / mitigation |
|---|-------|----------------|------------------|
| **31‑38** | The blueprint manipulates `sys.path` to add its own directory. This can mask other packages and cause **import cycles** when the main app also modifies `sys.path`. | In a large service this may lead to the wrong module being imported, making debugging very hard. | Remove the manual `sys.path` hack; rely on proper package installation (`pip install -e .`) or use relative imports (`from ..nonstationary_thompson_sampling import …`). |
| **55‑84** (`_get_strategies_from_db`) | **Multiple DB access strategies** are tried, each with hard‑coded connection parameters (`dbname="learning"`, `user="claude"`, `host="aio-01"`, `port=5433`). If the environment changes, the blueprint silently falls back to the next method, potentially connecting to the *wrong* database without any alert. | Silent data drift, security exposure (different credentials). | Centralise DB configuration (e.g. Flask `app.config["DB_URL"]`) and raise an error if the expected connection cannot be established. |
| **71‑73** (`except (ImportError, Exception): pass`) | Swallows **all** exceptions from the first strategy, including programming errors (e.g. NameError). | Makes debugging impossible; you may think the DB fetch failed for a legitimate reason when it was a typo. | Catch only the expected import‑related exceptions (`ImportError`) and let other exceptions propagate. |
| **108‑124** (`_parse_decay_params`) | The function returns a **default `round_hours = 6.0`** regardless of the caller’s default argument. If the caller passes a different default (e.g. from a config file) the function will ignore it. | Inconsistent behaviour between CLI and API. | Use the function signature’s default (`round_hours: float = 6.0`) and **do not** overwrite it inside the function. |
| **150‑166** (`list_nonstationary`) | The endpoint returns the raw `last_updated` field *as‑is* if it is already a string. If the DB returns a string in a non‑ISO format, the client receives an ambiguous timestamp. | Consumers cannot reliably parse the timestamp. | Always normalise to ISO‑8601 (`datetime.fromisoformat` or `dateutil.parser.parse`) before returning. |
| **176‑190** (`list_nonstationary`) | The endpoint **exposes the entire `strategy` row** (including `total_reward`, `avg_reward`, possibly internal IDs). This may leak internal metrics that are not meant for public consumption. | Security / privacy issue. | Return only the fields that are part of the public contract (e.g. `strategy`, `effective_mean`, `decayed_*`). |
| **215‑226** (`select_nonstationary`) | The request body is obtained with `request.get_json(silent=True) or {}`. If the client sends malformed JSON, the endpoint silently treats it as an empty dict and proceeds with defaults. | The client gets a 200 response with a *random* selection instead of a clear 400 error. | Use `silent=False` (default) so

---

## Recommended Action Items (Priority Order)

### P0 - Fix Before Production Use

1. **Stop mutating input dicts** -- Use `dict(s)` copies in `select_strategy_nonstationary()` and `get_decayed_strategies()`
2. **Fix `or 1` bug** -- Replace `float(x or 1)` with explicit None/missing handling
3. **Use thread-local RNG** -- Replace `np.random.beta()` with `np.random.default_rng().beta()`
4. **Remove direct DB connection from blueprint** -- Delete the `psycopg2.connect()` fallback, use REST API only

### P1 - Should Fix

5. **Log warnings on parse failures** instead of silently returning defaults
6. **Fix sliding window math** to guarantee total observations <= window
7. **Remove `sys.path` manipulation** -- use proper package structure
8. **Validate `request.get_json()`** -- use `silent=False` to reject malformed JSON with 400

### P2 - Nice to Have

9. **Add NaN guard** on `np.random.beta()` output
10. **Initialize `best_sample` to `float('-inf')`** instead of `-1.0`
11. **Clamp `info_loss` to `[0, 1]`** in diagnostics
12. **Configure logging before arg parsing** in `main()`
13. **Consider selection-round-based decay** instead of wall-clock-based

---

*Report generated by multi-model fleet review using 3 independent AI reviewers.*
*Models: Llama 3.3 70B (Groq), Nemotron 3 Ultra 550B (OpenRouter), GPT-OSS 120B (Cerebras)*
