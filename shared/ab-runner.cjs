/**
 * Automated A/B Testing Runner
 *
 * Runs multiple experiment variants, computes statistical significance,
 * and generates markdown reports with cost/latency/quality tradeoff analysis.
 *
 * Features:
 * 1. Multi-variant A/B testing with feature toggles
 * 2. Welch's t-test for p-values between variants
 * 3. Cohen's d effect size calculation
 * 4. Bootstrap confidence intervals
 * 5. Cost/latency/quality tradeoff analysis
 * 6. Markdown report generation
 *
 * Example:
 *   const { runABTest } = require('./ab-runner.cjs');
 *   const results = await runABTest('thompson-vs-random', [
 *     { name: 'baseline', features: [] },
 *     { name: 'thompson', features: ['thompson_sampling'] },
 *   ]);
 *
 * Created: 2026-06-28
 */

// ============================================================================
// CONFIGURATION
// ============================================================================

const DEFAULT_CONFIG = {
  iterations_per_variant: 30,   // Minimum for CLT approximation
  warmup_iterations: 3,         // Discarded warmup runs
  timeout_ms: 30000,            // Per-iteration timeout
  confidence_level: 0.95,       // For confidence intervals
  bootstrap_iterations: 1000,   // Bootstrap resamples
  parallel_variants: false,     // Run variants sequentially by default
  seed: null,                   // Optional RNG seed for reproducibility
};

// ============================================================================
// FEATURE TOGGLE REGISTRY
// ============================================================================

/**
 * Feature toggle state -- tracks which features are enabled for
 * the current experiment variant.
 */
const _featureState = {};

/**
 * Enable a set of feature flags for the current variant.
 *
 * @param {string[]} features - Feature names to enable
 */
function enableFeatures(features) {
  // Reset all
  for (const key of Object.keys(_featureState)) {
    delete _featureState[key];
  }
  // Enable requested
  for (const f of features) {
    _featureState[f] = true;
  }
}

/**
 * Check if a feature is currently enabled.
 *
 * @param {string} featureName - Feature to check
 * @returns {boolean}
 */
function isFeatureEnabled(featureName) {
  return !!_featureState[featureName];
}

/**
 * Get all currently enabled features.
 *
 * @returns {string[]}
 */
function getEnabledFeatures() {
  return Object.keys(_featureState).filter(function(k) { return _featureState[k]; });
}

/**
 * Clear all feature toggles.
 */
function clearFeatures() {
  for (const key of Object.keys(_featureState)) {
    delete _featureState[key];
  }
}

// ============================================================================
// STATISTICAL FUNCTIONS
// ============================================================================

/**
 * Calculate mean of an array.
 *
 * @param {number[]} arr
 * @returns {number}
 */
function mean(arr) {
  if (arr.length === 0) return 0;
  return arr.reduce(function(s, x) { return s + x; }, 0) / arr.length;
}

/**
 * Calculate sample standard deviation.
 *
 * @param {number[]} arr
 * @returns {number}
 */
function stddev(arr) {
  if (arr.length < 2) return 0;
  var m = mean(arr);
  var sumSq = arr.reduce(function(s, x) { return s + Math.pow(x - m, 2); }, 0);
  return Math.sqrt(sumSq / (arr.length - 1));
}

/**
 * Calculate median of an array.
 *
 * @param {number[]} arr
 * @returns {number}
 */
function median(arr) {
  if (arr.length === 0) return 0;
  var sorted = arr.slice().sort(function(a, b) { return a - b; });
  var mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 0) {
    return (sorted[mid - 1] + sorted[mid]) / 2;
  }
  return sorted[mid];
}

/**
 * Calculate percentile of an array.
 *
 * @param {number[]} arr
 * @param {number} p - Percentile (0-100)
 * @returns {number}
 */
function percentile(arr, p) {
  if (arr.length === 0) return 0;
  var sorted = arr.slice().sort(function(a, b) { return a - b; });
  var idx = (p / 100) * (sorted.length - 1);
  var lower = Math.floor(idx);
  var upper = Math.ceil(idx);
  if (lower === upper) return sorted[lower];
  var frac = idx - lower;
  return sorted[lower] * (1 - frac) + sorted[upper] * frac;
}

/**
 * Approximate the inverse of the standard normal CDF (probit function).
 * Uses Abramowitz and Stegun approximation 26.2.23.
 *
 * @param {number} p - Probability (0 < p < 1)
 * @returns {number}
 */
function normalInverseCDF(p) {
  if (p <= 0) return -Infinity;
  if (p >= 1) return Infinity;
  if (p === 0.5) return 0;

  var sign = p < 0.5 ? -1 : 1;
  var pp = p < 0.5 ? p : 1 - p;

  var t = Math.sqrt(-2 * Math.log(pp));

  // Rational approximation coefficients
  var c0 = 2.515517;
  var c1 = 0.802853;
  var c2 = 0.010328;
  var d1 = 1.432788;
  var d2 = 0.189269;
  var d3 = 0.001308;

  var result = t - (c0 + c1 * t + c2 * t * t) / (1 + d1 * t + d2 * t * t + d3 * t * t * t);
  return sign * result;
}

/**
 * Approximate the t-distribution CDF using normal approximation.
 * Accurate for df > 30; reasonable for df > 5.
 *
 * @param {number} t - t statistic
 * @param {number} df - degrees of freedom
 * @returns {number} - Probability P(T <= t)
 */
function tDistCDF(t, df) {
  // For large df, t-distribution converges to normal
  // Use refined approximation for smaller df
  var x = df / (df + t * t);
  // Regularized incomplete beta function approximation
  // For two-tailed p-value we use normal approximation with correction
  var z = t * (1 - 1 / (4 * df)) / Math.sqrt(1 + t * t / (2 * df));
  return normalCDF(z);
}

/**
 * Standard normal CDF approximation.
 *
 * @param {number} z
 * @returns {number}
 */
function normalCDF(z) {
  // Horner form approximation
  var a1 = 0.254829592;
  var a2 = -0.284496736;
  var a3 = 1.421413741;
  var a4 = -1.453152027;
  var a5 = 1.061405429;
  var p = 0.3275911;

  var sign = z < 0 ? -1 : 1;
  z = Math.abs(z) / Math.sqrt(2);

  var t = 1.0 / (1.0 + p * z);
  var y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-z * z);

  return 0.5 * (1.0 + sign * y);
}

/**
 * Welch's t-test (unequal variances t-test).
 * Compares two independent samples.
 *
 * @param {number[]} sample1 - First sample
 * @param {number[]} sample2 - Second sample
 * @returns {Object} { t_statistic, degrees_of_freedom, p_value, significant }
 */
function welchTTest(sample1, sample2) {
  var n1 = sample1.length;
  var n2 = sample2.length;

  if (n1 < 2 || n2 < 2) {
    return {
      t_statistic: 0,
      degrees_of_freedom: 0,
      p_value: 1,
      significant: false,
      warning: 'insufficient_samples',
    };
  }

  var m1 = mean(sample1);
  var m2 = mean(sample2);
  var s1 = stddev(sample1);
  var s2 = stddev(sample2);

  var v1 = s1 * s1;
  var v2 = s2 * s2;

  // Guard against zero variance
  if (v1 === 0 && v2 === 0) {
    return {
      t_statistic: 0,
      degrees_of_freedom: n1 + n2 - 2,
      p_value: m1 === m2 ? 1 : 0,
      significant: m1 !== m2,
    };
  }

  var se = Math.sqrt(v1 / n1 + v2 / n2);
  var t = (m1 - m2) / se;

  // Welch-Satterthwaite degrees of freedom
  var num = Math.pow(v1 / n1 + v2 / n2, 2);
  var denom = Math.pow(v1 / n1, 2) / (n1 - 1) + Math.pow(v2 / n2, 2) / (n2 - 1);
  var df = num / denom;

  // Two-tailed p-value
  var pValue = 2 * (1 - tDistCDF(Math.abs(t), df));

  return {
    t_statistic: t,
    degrees_of_freedom: df,
    p_value: pValue,
    significant: pValue < 0.05,
  };
}

/**
 * Cohen's d effect size.
 * Measures the magnitude of difference between two groups.
 *
 * Interpretation:
 *   |d| < 0.2: negligible
 *   0.2 <= |d| < 0.5: small
 *   0.5 <= |d| < 0.8: medium
 *   |d| >= 0.8: large
 *
 * @param {number[]} sample1
 * @param {number[]} sample2
 * @returns {Object} { d, magnitude }
 */
function cohensD(sample1, sample2) {
  var m1 = mean(sample1);
  var m2 = mean(sample2);
  var s1 = stddev(sample1);
  var s2 = stddev(sample2);

  // Pooled standard deviation
  var n1 = sample1.length;
  var n2 = sample2.length;

  if (n1 < 2 || n2 < 2) {
    return { d: 0, magnitude: 'insufficient_data' };
  }

  var pooledVar = ((n1 - 1) * s1 * s1 + (n2 - 1) * s2 * s2) / (n1 + n2 - 2);
  var pooledSD = Math.sqrt(pooledVar);

  if (pooledSD === 0) {
    return { d: 0, magnitude: 'negligible' };
  }

  var d = (m1 - m2) / pooledSD;
  var absD = Math.abs(d);

  var magnitude;
  if (absD < 0.2) magnitude = 'negligible';
  else if (absD < 0.5) magnitude = 'small';
  else if (absD < 0.8) magnitude = 'medium';
  else magnitude = 'large';

  return { d: d, magnitude: magnitude };
}

/**
 * Bootstrap confidence interval for a metric.
 *
 * @param {number[]} data
 * @param {number} confidence - Confidence level (0-1)
 * @param {number} iterations - Number of bootstrap resamples
 * @returns {Object} { lower, upper, mean, median }
 */
function bootstrapCI(data, confidence, iterations) {
  confidence = confidence || 0.95;
  iterations = iterations || 1000;

  if (data.length < 2) {
    var val = data.length === 1 ? data[0] : 0;
    return { lower: val, upper: val, mean: val, median: val };
  }

  var estimates = [];
  for (var i = 0; i < iterations; i++) {
    var sample = [];
    for (var j = 0; j < data.length; j++) {
      sample.push(data[Math.floor(Math.random() * data.length)]);
    }
    estimates.push(mean(sample));
  }

  estimates.sort(function(a, b) { return a - b; });

  var alpha = 1 - confidence;
  var lowerIdx = Math.floor(iterations * alpha / 2);
  var upperIdx = Math.floor(iterations * (1 - alpha / 2));

  return {
    lower: estimates[lowerIdx],
    upper: estimates[upperIdx],
    mean: mean(estimates),
    median: median(estimates),
  };
}

// ============================================================================
// COMPUTE STATISTICS
// ============================================================================

/**
 * Compute comprehensive statistics for A/B test results.
 *
 * Analyzes each metric across all variant pairs:
 * - Welch's t-test (p-value)
 * - Cohen's d (effect size)
 * - Bootstrap confidence intervals
 * - Cost/latency/quality tradeoff scores
 *
 * @param {Object} results - Raw results from runABTest
 * @returns {Object} Statistical analysis
 */
function computeStatistics(results) {
  var variants = results.variants;
  var variantNames = Object.keys(variants);

  if (variantNames.length < 2) {
    return {
      status: 'insufficient_variants',
      message: 'Need at least 2 variants for comparison',
      variants: variantNames,
    };
  }

  var metrics = ['quality', 'latency_ms', 'cost_usd'];
  var pairwise = {};
  var summaries = {};

  // Per-variant summary statistics
  for (var vi = 0; vi < variantNames.length; vi++) {
    var vname = variantNames[vi];
    var v = variants[vname];
    var summary = {};

    for (var mi = 0; mi < metrics.length; mi++) {
      var metric = metrics[mi];
      var values = v.measurements.map(function(m) { return m[metric] || 0; });

      summary[metric] = {
        mean: mean(values),
        median: median(values),
        stddev: stddev(values),
        min: values.length > 0 ? Math.min.apply(null, values) : 0,
        max: values.length > 0 ? Math.max.apply(null, values) : 0,
        p5: percentile(values, 5),
        p95: percentile(values, 95),
        ci: bootstrapCI(values, DEFAULT_CONFIG.confidence_level, DEFAULT_CONFIG.bootstrap_iterations),
        n: values.length,
      };
    }

    // Tradeoff score: higher quality, lower cost, lower latency
    var qMean = summary.quality ? summary.quality.mean : 0;
    var cMean = summary.cost_usd ? summary.cost_usd.mean : 0;
    var lMean = summary.latency_ms ? summary.latency_ms.mean : 0;

    // Normalize latency to 0-1 scale (assuming max 30s)
    var latencyNorm = Math.max(0, 1 - (lMean / 30000));
    // Normalize cost to 0-1 scale (assuming max $0.10 per call)
    var costNorm = Math.max(0, 1 - (cMean / 0.10));

    summary.tradeoff_score = {
      quality_weight: 0.5,
      cost_weight: 0.3,
      latency_weight: 0.2,
      score: 0.5 * qMean + 0.3 * costNorm + 0.2 * latencyNorm,
    };

    summaries[vname] = summary;
  }

  // Pairwise comparisons
  for (var ai = 0; ai < variantNames.length; ai++) {
    for (var bi = ai + 1; bi < variantNames.length; bi++) {
      var nameA = variantNames[ai];
      var nameB = variantNames[bi];
      var pairKey = nameA + '_vs_' + nameB;
      var comparison = {};

      for (var mj = 0; mj < metrics.length; mj++) {
        var met = metrics[mj];
        var valuesA = variants[nameA].measurements.map(function(m) { return m[met] || 0; });
        var valuesB = variants[nameB].measurements.map(function(m) { return m[met] || 0; });

        comparison[met] = {
          t_test: welchTTest(valuesA, valuesB),
          effect_size: cohensD(valuesA, valuesB),
          mean_diff: mean(valuesA) - mean(valuesB),
          relative_diff_pct: mean(valuesB) !== 0
            ? ((mean(valuesA) - mean(valuesB)) / Math.abs(mean(valuesB))) * 100
            : 0,
        };
      }

      pairwise[pairKey] = comparison;
    }
  }

  // Determine winner by tradeoff score
  var bestName = variantNames[0];
  var bestScore = summaries[variantNames[0]].tradeoff_score.score;

  for (var wi = 1; wi < variantNames.length; wi++) {
    var sc = summaries[variantNames[wi]].tradeoff_score.score;
    if (sc > bestScore) {
      bestScore = sc;
      bestName = variantNames[wi];
    }
  }

  return {
    status: 'success',
    winner: bestName,
    winner_score: bestScore,
    summaries: summaries,
    pairwise: pairwise,
    metadata: {
      confidence_level: DEFAULT_CONFIG.confidence_level,
      bootstrap_iterations: DEFAULT_CONFIG.bootstrap_iterations,
      variant_count: variantNames.length,
      variants: variantNames,
    },
  };
}

// ============================================================================
// REPORT GENERATION
// ============================================================================

/**
 * Generate a markdown report from A/B test statistics.
 *
 * @param {Object} stats - Output from computeStatistics()
 * @param {string} experimentName - Name of the experiment
 * @returns {string} Markdown report
 */
function generateReport(stats, experimentName) {
  if (stats.status !== 'success') {
    return '# A/B Test Report: ' + (experimentName || 'unknown') + '\n\n'
      + 'Status: ' + stats.status + '\n'
      + 'Message: ' + (stats.message || 'N/A') + '\n';
  }

  var lines = [];

  lines.push('# A/B Test Report: ' + experimentName);
  lines.push('');
  lines.push('**Winner:** ' + stats.winner + ' (tradeoff score: ' + stats.winner_score.toFixed(4) + ')');
  lines.push('');

  // Summary table
  lines.push('## Variant Summaries');
  lines.push('');
  lines.push('| Variant | Quality (mean) | Latency ms (mean) | Cost USD (mean) | Tradeoff Score |');
  lines.push('|---------|---------------|-------------------|-----------------|----------------|');

  var variantNames = stats.metadata.variants;
  for (var si = 0; si < variantNames.length; si++) {
    var vn = variantNames[si];
    var s = stats.summaries[vn];
    var marker = vn === stats.winner ? ' *' : '';
    lines.push('| ' + vn + marker
      + ' | ' + s.quality.mean.toFixed(4)
      + ' | ' + s.latency_ms.mean.toFixed(1)
      + ' | ' + s.cost_usd.mean.toFixed(5)
      + ' | ' + s.tradeoff_score.score.toFixed(4) + ' |');
  }
  lines.push('');

  // Confidence intervals
  lines.push('## Confidence Intervals (' + (stats.metadata.confidence_level * 100) + '%)');
  lines.push('');

  for (var ci = 0; ci < variantNames.length; ci++) {
    var vn2 = variantNames[ci];
    var s2 = stats.summaries[vn2];
    lines.push('### ' + vn2);
    lines.push('');
    lines.push('| Metric | Mean | CI Lower | CI Upper | Std Dev |');
    lines.push('|--------|------|----------|----------|---------|');

    var metricList = ['quality', 'latency_ms', 'cost_usd'];
    for (var mci = 0; mci < metricList.length; mci++) {
      var mk = metricList[mci];
      var ms = s2[mk];
      lines.push('| ' + mk
        + ' | ' + ms.mean.toFixed(4)
        + ' | ' + ms.ci.lower.toFixed(4)
        + ' | ' + ms.ci.upper.toFixed(4)
        + ' | ' + ms.stddev.toFixed(4) + ' |');
    }
    lines.push('');
  }

  // Pairwise comparisons
  lines.push('## Pairwise Comparisons');
  lines.push('');

  var pairKeys = Object.keys(stats.pairwise);
  for (var pi = 0; pi < pairKeys.length; pi++) {
    var pk = pairKeys[pi];
    var pair = stats.pairwise[pk];
    lines.push('### ' + pk.replace(/_/g, ' '));
    lines.push('');
    lines.push('| Metric | p-value | Significant | Effect Size (d) | Magnitude | Relative Diff % |');
    lines.push('|--------|---------|-------------|-----------------|-----------|-----------------|');

    var metricList2 = ['quality', 'latency_ms', 'cost_usd'];
    for (var pmi = 0; pmi < metricList2.length; pmi++) {
      var pmk = metricList2[pmi];
      var pc = pair[pmk];
      lines.push('| ' + pmk
        + ' | ' + pc.t_test.p_value.toFixed(4)
        + ' | ' + (pc.t_test.significant ? 'YES' : 'no')
        + ' | ' + pc.effect_size.d.toFixed(4)
        + ' | ' + pc.effect_size.magnitude
        + ' | ' + pc.relative_diff_pct.toFixed(2) + '% |');
    }
    lines.push('');
  }

  // Tradeoff analysis
  lines.push('## Cost/Latency/Quality Tradeoff');
  lines.push('');
  lines.push('Tradeoff score = 0.5 * quality + 0.3 * cost_efficiency + 0.2 * latency_efficiency');
  lines.push('');
  lines.push('| Variant | Quality | Cost Efficiency | Latency Efficiency | Combined |');
  lines.push('|---------|---------|-----------------|--------------------|---------| ');

  for (var ti = 0; ti < variantNames.length; ti++) {
    var tvn = variantNames[ti];
    var ts = stats.summaries[tvn];
    var qVal = ts.quality.mean;
    var cEff = Math.max(0, 1 - (ts.cost_usd.mean / 0.10));
    var lEff = Math.max(0, 1 - (ts.latency_ms.mean / 30000));
    lines.push('| ' + tvn
      + ' | ' + qVal.toFixed(4)
      + ' | ' + cEff.toFixed(4)
      + ' | ' + lEff.toFixed(4)
      + ' | ' + ts.tradeoff_score.score.toFixed(4) + ' |');
  }
  lines.push('');

  lines.push('---');
  lines.push('*Generated by ab-runner.cjs at ' + new Date().toISOString() + '*');

  return lines.join('\n');
}

// ============================================================================
// A/B TEST RUNNER
// ============================================================================

/**
 * Run an A/B test across multiple variants.
 *
 * Each variant config must include:
 *   - name: string - variant identifier
 *   - features: string[] - feature toggles to enable
 *   - handler: async function(iteration, features) => { quality, latency_ms, cost_usd }
 *     (optional -- if omitted, a default synthetic handler is used)
 *
 * @param {string} experimentName - Name for this experiment
 * @param {Object[]} configs - Array of variant configurations
 * @param {Object} [options] - Override default config
 * @returns {Promise<Object>} { winner, statistics, report, raw }
 */
async function runABTest(experimentName, configs, options) {
  options = options || {};
  var iterCount = options.iterations_per_variant || DEFAULT_CONFIG.iterations_per_variant;
  var warmup = options.warmup_iterations || DEFAULT_CONFIG.warmup_iterations;
  var timeoutMs = options.timeout_ms || DEFAULT_CONFIG.timeout_ms;

  var variants = {};

  for (var ci = 0; ci < configs.length; ci++) {
    var config = configs[ci];
    var vName = config.name;
    var features = config.features || [];
    var handler = config.handler || null;

    // Enable feature toggles for this variant
    enableFeatures(features);

    var measurements = [];
    var errors = [];

    // Warmup phase (results discarded)
    for (var w = 0; w < warmup; w++) {
      try {
        if (handler) {
          await withTimeout(handler(w, features), timeoutMs);
        }
      } catch (e) {
        // Warmup errors are ignored
      }
    }

    // Measurement phase
    for (var i = 0; i < iterCount; i++) {
      var start = Date.now();

      try {
        var result;
        if (handler) {
          result = await withTimeout(handler(i, features), timeoutMs);
        } else {
          // Default synthetic handler for testing
          result = syntheticHandler(i, features);
        }

        var elapsed = Date.now() - start;

        measurements.push({
          iteration: i,
          quality: result.quality || 0,
          latency_ms: result.latency_ms || elapsed,
          cost_usd: result.cost_usd || 0,
          timestamp: new Date().toISOString(),
          features_enabled: features.slice(),
        });
      } catch (err) {
        errors.push({
          iteration: i,
          error: err.message || String(err),
          timestamp: new Date().toISOString(),
        });
      }
    }

    variants[vName] = {
      name: vName,
      features: features,
      measurements: measurements,
      errors: errors,
      success_rate: measurements.length / (measurements.length + errors.length),
    };
  }

  // Clear feature toggles
  clearFeatures();

  var raw = {
    experiment: experimentName,
    variants: variants,
    config: {
      iterations_per_variant: iterCount,
      warmup_iterations: warmup,
      timeout_ms: timeoutMs,
    },
    started_at: new Date().toISOString(),
  };

  var statistics = computeStatistics(raw);
  var report = generateReport(statistics, experimentName);

  return {
    winner: statistics.winner || null,
    statistics: statistics,
    report: report,
    raw: raw,
  };
}

/**
 * Default synthetic handler for testing without real workloads.
 * Simulates quality/latency/cost based on enabled features.
 *
 * @param {number} iteration
 * @param {string[]} features
 * @returns {Object} { quality, latency_ms, cost_usd }
 */
function syntheticHandler(iteration, features) {
  // Base metrics
  var quality = 0.5 + (Math.random() * 0.1 - 0.05);
  var latencyMs = 500 + Math.random() * 200;
  var costUsd = 0.01 + Math.random() * 0.005;

  // Feature effects
  for (var fi = 0; fi < features.length; fi++) {
    var f = features[fi];
    if (f === 'thompson_sampling') {
      quality += 0.15 + Math.random() * 0.05;
      latencyMs += 50 + Math.random() * 30;
      costUsd += 0.002;
    } else if (f === 'adversarial_verification') {
      quality += 0.08 + Math.random() * 0.03;
      latencyMs += 200 + Math.random() * 100;
      costUsd += 0.01;
    } else if (f === 'caching') {
      latencyMs -= 200 + Math.random() * 100;
      costUsd -= 0.005;
    } else if (f === 'consensus') {
      quality += 0.10 + Math.random() * 0.04;
      latencyMs += 300 + Math.random() * 150;
      costUsd += 0.03;
    }
  }

  // Clamp values
  quality = Math.max(0, Math.min(1, quality));
  latencyMs = Math.max(10, latencyMs);
  costUsd = Math.max(0, costUsd);

  return {
    quality: quality,
    latency_ms: latencyMs,
    cost_usd: costUsd,
  };
}

/**
 * Wrap a promise with a timeout.
 *
 * @param {Promise} promise
 * @param {number} ms - Timeout in milliseconds
 * @returns {Promise}
 */
function withTimeout(promise, ms) {
  return new Promise(function(resolve, reject) {
    var timer = setTimeout(function() {
      reject(new Error('Timeout after ' + ms + 'ms'));
    }, ms);

    Promise.resolve(promise).then(
      function(val) {
        clearTimeout(timer);
        resolve(val);
      },
      function(err) {
        clearTimeout(timer);
        reject(err);
      }
    );
  });
}

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  // Main API
  runABTest: runABTest,
  computeStatistics: computeStatistics,
  generateReport: generateReport,

  // Feature toggles
  enableFeatures: enableFeatures,
  isFeatureEnabled: isFeatureEnabled,
  getEnabledFeatures: getEnabledFeatures,
  clearFeatures: clearFeatures,

  // Statistical functions (exported for testing)
  welchTTest: welchTTest,
  cohensD: cohensD,
  bootstrapCI: bootstrapCI,
  mean: mean,
  stddev: stddev,
  median: median,
  percentile: percentile,

  // Utilities
  syntheticHandler: syntheticHandler,

  // Configuration
  DEFAULT_CONFIG: DEFAULT_CONFIG,
};
