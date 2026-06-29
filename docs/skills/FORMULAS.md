# Learning Metrics - Complete Formula Reference

## Master Equation: Learning Intelligence Score (LIS)

```
LIS = 0.35 × Q_score + 0.25 × C_score + 0.20 × S_score + 0.20 × Cons_score

Constraints: LIS ∈ [0, 100]
```

---

## Quality Score (Q_score)

**35% weight in LIS**

### 1. Base Quality Score
```
Q_base = percentile_rank(avg_quality_model, {avg_quality_all_models}) × 100

Where percentile_rank(x, list) = count(e ∈ list where e < x) / len(list)
```

### 2. Recent Trend Bonus
```
Q_slope = linear_regression_slope(last_10_quality_samples)

Q_bonus = max(0, min(Q_slope × 10, 10))
# Cap bonus at 10 points
# Only positive slope (improving) contributes
```

### 3. Final Quality Score
```
Q_score = min(100, Q_base + Q_bonus) / 1.1

Where division by 1.1 normalizes to [0, 100]
```

### 4. Example Calculation
```
Model: opus/code-review
- avg_quality = 0.87 (87th percentile) → Q_base = 87
- recent_slope = +0.015 per sample → Q_bonus = 1.5
- Q_score = min(100, 88.5) / 1.1 = 80.4
```

---

## Cost Score (C_score)

**25% weight in LIS**

### 1. Base Cost Score (Inverted Percentile)
```
C_percentile = percentile_rank(avg_cost_model, {avg_cost_all_models})

C_base = (1 - C_percentile) × 100
# Lower cost → higher score
```

### 2. Cost Reduction Bonus
```
C_slope = linear_regression_slope(last_10_cost_samples)

C_bonus = max(0, min(-C_slope × 15, 15))
# Negative slope (decreasing cost) is good
# Cap bonus at 15 points
```

### 3. Final Cost Score
```
C_score = min(100, C_base + C_bonus) / 1.15

Where division by 1.15 normalizes
```

### 4. Example Calculation
```
Model: opus/code-review
- avg_cost = $0.025 (25th percentile/cheapest 25%) → C_percentile = 0.25
- C_base = (1 - 0.25) × 100 = 75
- cost_slope = -$0.0002 per call → C_bonus = 3.0
- C_score = min(100, 78) / 1.15 = 67.8
```

---

## Speed Score (S_score)

**20% weight in LIS**

### 1. Base Speed Score (Inverted Percentile)
```
S_percentile = percentile_rank(avg_duration_model, {avg_duration_all_models})

S_base = (1 - S_percentile) × 100
# Lower duration → higher score
```

### 2. Speedup Bonus
```
S_slope = linear_regression_slope(last_10_duration_samples)

S_bonus = max(0, min(-S_slope × 10, 10))
# Negative slope (faster) is good
# Cap bonus at 10 points
```

### 3. Final Speed Score
```
S_score = min(100, S_base + S_bonus) / 1.1

Where division by 1.1 normalizes
```

### 4. Example Calculation
```
Model: opus/code-review
- avg_duration = 2500ms (90th percentile/fast) → S_percentile = 0.10
- S_base = (1 - 0.10) × 100 = 90
- duration_slope = -50ms per call → S_bonus = 5.0
- S_score = min(100, 95) / 1.1 = 86.4
```

---

## Consistency Score (Cons_score)

**20% weight in LIS**

### 1. Coefficient of Variation (CV)
```
CV(X) = σ(X) / μ(X)

Where:
- σ(X) = sample standard deviation
- μ(X) = sample mean

CV ∈ [0, ∞)
- CV < 0.2: Excellent (consistent)
- CV ∈ [0.2, 0.3]: Good
- CV ∈ [0.3, 0.5]: Fair
- CV > 0.5: Poor (volatile)
```

### 2. Quality Consistency
```
CV_quality = σ(recent_quality_samples) / μ(recent_quality_samples)

Q_consistency = max(0, 100 - CV_quality × 200)

Mapping:
- CV = 0.1 → 100 (perfect)
- CV = 0.2 → 60 (very good)
- CV = 0.3 → 40 (good)
- CV = 0.5 → 0 (poor)
```

### 3. Cost Consistency
```
CV_cost = σ(recent_cost_samples) / μ(recent_cost_samples)

C_consistency = max(0, 100 - CV_cost × 200)
```

### 4. Final Consistency Score
```
Cons_score = (Q_consistency + C_consistency) / 2

Range: [0, 100]
```

### 5. Example Calculation
```
Model: opus/code-review
- recent_quality = [0.84, 0.85, 0.86, 0.87, 0.88]
- μ = 0.86, σ = 0.0141, CV = 0.0164
- Q_consistency = max(0, 100 - 0.0164 × 200) = 99.7

- recent_cost = [0.024, 0.025, 0.026, 0.025, 0.024]
- μ = 0.0248, σ = 0.00084, CV = 0.0339
- C_consistency = max(0, 100 - 0.0339 × 200) = 93.2

- Cons_score = (99.7 + 93.2) / 2 = 96.4
```

---

## Quality Trend Analysis

**Statistical significance test**

### 1. Split Data by Time
```
DataOlder = {quality_scores where timestamp < now - 15 days}
DataRecent = {quality_scores where timestamp ≥ now - 15 days}

n₁ = len(DataOlder), μ₁ = mean(DataOlder), σ₁ = stddev(DataOlder)
n₂ = len(DataRecent), μ₂ = mean(DataRecent), σ₂ = stddev(DataRecent)
```

### 2. Calculate Improvement
```
improvement% = ((μ₂ - μ₁) / μ₁) × 100

Example: μ₁ = 0.80, μ₂ = 0.87
→ improvement% = (0.07 / 0.80) × 100 = 8.75%
```

### 3. Welch's t-test (for unequal variances)
```
t = (μ₂ - μ₁) / √(σ₁²/n₁ + σ₂²/n₂)

df = (σ₁²/n₁ + σ₂²/n₂)² / [(σ₁²/n₁)²/(n₁-1) + (σ₂²/n₂)²/(n₂-1)]

p_value = P(T_{df} > |t|)
# Using t-distribution with df degrees of freedom
```

### 4. Trend Classification
```
IF p_value < 0.05:
  IF improvement% > 0:
    trend = "improving"
    confidence = 1 - p_value
  ELSE:
    trend = "declining"
    confidence = 1 - p_value
ELSE:
  trend = "stable"
  confidence = 0
```

### 5. Example
```
DataOlder: [0.78, 0.80, 0.81, 0.80, 0.82] → μ₁ = 0.802, σ₁ = 0.0149, n₁ = 5
DataRecent: [0.84, 0.86, 0.85, 0.87, 0.86] → μ₂ = 0.856, σ₂ = 0.0110, n₂ = 5

improvement% = (0.856 - 0.802) / 0.802 × 100 = 6.73%

t = (0.856 - 0.802) / √(0.0149²/5 + 0.0110²/5) = 0.054 / 0.0105 = 5.14

df ≈ 8.5, p_value ≈ 0.001

Result: trend = "improving", confidence = 0.999
```

---

## Linear Regression Slope

**For trend calculations**

### 1. Formula
```
Given points: {(x₀, y₀), (x₁, y₁), ..., (xₙ, yₙ)}
where x = index (0 to n), y = metric value

slope = (n × Σ(xᵢ × yᵢ) - Σ(xᵢ) × Σ(yᵢ)) / (n × Σ(xᵢ²) - (Σ(xᵢ))²)

intercept = (Σ(yᵢ) - slope × Σ(xᵢ)) / n

R² = 1 - (SS_res / SS_tot)

Where:
- SS_res = Σ(yᵢ - (slope×xᵢ + intercept))²
- SS_tot = Σ(yᵢ - mean(y))²
```

### 2. R-squared Interpretation
```
R² ∈ [0, 1]
- R² > 0.7: Strong trend
- R² ∈ [0.5, 0.7]: Moderate trend
- R² < 0.5: Weak trend
```

### 3. Example
```
Quality scores (last 10 samples): [0.82, 0.84, 0.85, 0.85, 0.86, 0.86, 0.87, 0.87, 0.88, 0.88]
x indices: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

Σ(x) = 45
Σ(y) = 8.58
Σ(x²) = 285
Σ(xy) = 387.94
n = 10

slope = (10 × 387.94 - 45 × 8.58) / (10 × 285 - 45²)
      = (3879.4 - 386.1) / (2850 - 2025)
      = 3493.3 / 825
      = 4.235 × 10⁻² ≈ 0.0042 per sample

R² ≈ 0.94 (very strong improvement trend)
```

---

## Cost Efficiency

**Cost per quality point**

### 1. Basic Metric
```
cost_per_quality = avg_cost_usd / avg_quality_score

Example: $0.025 cost / 0.85 quality = $0.0294 per quality point
```

### 2. Efficiency Percentile
```
efficiency_percentile = percentile_rank(cost_per_quality_model, 
                                        {cost_per_quality_all_models})

Where lower cost per quality = better = higher percentile
```

### 3. Efficiency Score
```
efficiency_score = (1 - efficiency_percentile) × 100

# So better efficiency → higher score
```

### 4. Efficiency Trend
```
efficiency_trend_slope = linear_regression_slope(last_20_cost_per_quality)

# Negative slope = improving (lower cost per quality)
# Positive slope = degrading (higher cost per quality)
```

### 5. Example
```
Model A: cost_per_quality = 0.0294
Model B: cost_per_quality = 0.0250
Model C: cost_per_quality = 0.0310

For Model A:
- percentile_rank(0.0294, [0.0294, 0.0250, 0.0310]) = 1/3 ≈ 0.33
- efficiency_percentile = 0.33 (33rd percentile = not very efficient)
- efficiency_score = (1 - 0.33) × 100 = 67
```

---

## Speed Improvement

**Execution time reduction**

### 1. Time Period Comparison
```
time_old = mean(durations in first 50% of data)
time_recent = mean(durations in last 50% of data)

speed_improvement% = ((time_old - time_recent) / time_old) × 100

Positive value = faster (good)
Negative value = slower (bad)
```

### 2. Percentage Improved Runs
```
percent_improved = count(duration_recent < time_old) / n_recent × 100

Example: If 68% of recent runs are faster than baseline, improving = 68%
```

### 3. Speed Trend Slope
```
speed_trend_slope = linear_regression_slope(last_10_durations_ms)

Negative slope = getting faster
Positive slope = getting slower
```

### 4. Example
```
Old half (first 20 runs): mean = 3200ms
Recent half (last 20 runs): mean = 2800ms

speed_improvement% = (3200 - 2800) / 3200 × 100 = 12.5%

Recent runs < 3200ms: 17/20 = 85%
percent_improved = 85%
```

---

## Coefficient of Variation (CV)

**Measure of consistency**

### 1. Formula
```
CV = σ / μ

Where:
- σ = sample standard deviation = √[Σ(xᵢ - μ)² / (n-1)]
- μ = sample mean = Σ(xᵢ) / n
- CV is unit-less ratio
```

### 2. Interpretation
```
CV < 0.1:  Very consistent (excellent)
CV < 0.2:  Consistent (good)
CV < 0.3:  Moderately consistent (acceptable)
CV < 0.5:  Inconsistent (poor)
CV ≥ 0.5:  Very inconsistent (dangerous)
```

### 3. Example
```
Quality scores: [0.84, 0.85, 0.86, 0.85, 0.86]

μ = (0.84 + 0.85 + 0.86 + 0.85 + 0.86) / 5 = 0.852

σ² = [(0.84-0.852)² + (0.85-0.852)² + ... ] / 4
   = [0.000144 + 0.000004 + 0.001936 + 0.000004 + 0.001936] / 4
   = 0.00403 / 4 = 0.00101

σ = √0.00101 = 0.0318

CV = 0.0318 / 0.852 = 0.0373

Interpretation: Very consistent (CV < 0.1), excellent performance
```

---

## Percentile Rank

**For comparing models**

### 1. Formula
```
percentile_rank(x, sorted_list) = count(e ∈ list where e < x) / len(list)

Returns: value ∈ [0, 1]
- 0 = lowest value
- 1 = highest value
- 0.5 = median
```

### 2. Example
```
All models' quality scores: [0.75, 0.80, 0.82, 0.85, 0.87, 0.90]
Our model quality: 0.85

percentile_rank(0.85, [...]) = 3 / 6 = 0.5

Our model is at 50th percentile (median quality)
```

---

## Percentile Filtering for Outlier Removal (IQR Method)

**Optional: To clean anomalous data**

### 1. Calculate Quartiles
```
Sorted data: [x₀, x₁, ..., xₙ]

Q1 = x[⌊n/4⌋]          (25th percentile)
Q3 = x[⌊3n/4⌋]         (75th percentile)
IQR = Q3 - Q1
```

### 2. Define Bounds
```
Lower bound = Q1 - 1.5 × IQR
Upper bound = Q3 + 1.5 × IQR
```

### 3. Filter
```
Cleaned data = {x ∈ data where lower_bound ≤ x ≤ upper_bound}
```

### 4. Example
```
Quality scores: [0.70, 0.78, 0.82, 0.85, 0.87, 0.88, 0.90, 0.05]
# (0.05 is an outlier)

Q1 = 0.78, Q3 = 0.89, IQR = 0.11
Lower = 0.78 - 1.5×0.11 = 0.615
Upper = 0.89 + 1.5×0.11 = 1.055

Cleaned: [0.70, 0.78, 0.82, 0.85, 0.87, 0.88, 0.90]
# 0.05 removed as outlier
```

---

## Summary of All Calculations

```
Input: execution_log records for model M and task T

Step 1: Aggregate Statistics
├─ avg_quality = AVG(quality_score)
├─ avg_cost = AVG(cost_usd)
├─ avg_duration = AVG(duration_ms)
├─ stddev_quality = STDDEV(quality_score)
├─ stddev_cost = STDDEV(cost_usd)
└─ stddev_duration = STDDEV(duration_ms)

Step 2: Calculate Component Scores
├─ Quality Score: percentile(avg_quality) + trend_bonus
├─ Cost Score: (1 - percentile(avg_cost)) + reduction_bonus
├─ Speed Score: (1 - percentile(avg_duration)) + speedup_bonus
└─ Consistency Score: (100 - CV_quality×200 + 100 - CV_cost×200) / 2

Step 3: Calculate LIS
├─ LIS = 0.35×Q + 0.25×C + 0.20×S + 0.20×Cons
└─ Cap to [0, 100]

Step 4: Calculate Trends
├─ Quality Trend: t-test on older vs recent samples
├─ Cost Efficiency: cost_per_quality percentile + slope
└─ Speed Improvement: (old_mean - recent_mean) / old_mean

Output: Comprehensive metrics dashboard
```

---

## Formula Validation Examples

### Example 1: High-Quality, Consistent Model
```
Inputs:
- Quality: 0.90 (95th percentile) → Q_base = 95
- Quality slope: +0.02 → Q_bonus = 2.0
- Cost: $0.020 (10th percentile/cheapest) → C_base = 90
- Cost slope: -$0.0001 → C_bonus = 1.5
- Duration: 2000ms (95th percentile/fast) → S_base = 95
- Duration slope: -50ms → S_bonus = 5.0
- CV_quality: 0.08 → Cons_quality = 84
- CV_cost: 0.05 → Cons_cost = 90

Calculations:
- Q_score = min(100, 97) / 1.1 = 88.2
- C_score = min(100, 91.5) / 1.15 = 79.6
- S_score = min(100, 100) / 1.1 = 90.9
- Cons_score = (84 + 90) / 2 = 87

LIS = 0.35×88.2 + 0.25×79.6 + 0.20×90.9 + 0.20×87
    = 30.87 + 19.90 + 18.18 + 17.40
    = 86.35

Result: LIS = 86/100 (Excellent)
```

### Example 2: Declining Model
```
Inputs:
- Quality trend: older=0.85, recent=0.78
- improvement% = (0.78 - 0.85) / 0.85 × 100 = -8.24%
- t-test: t = -3.2, p_value = 0.008

Result:
- trend = "declining"
- confidence = 1 - 0.008 = 0.992 (99.2% confident)
- Alert: Quality regression detected
```

---

## Notes

- All calculations use sample statistics (n-1 denominator for variance)
- Percentile ranks use percent of values strictly less than target
- Bonuses capped to prevent overflow in LIS calculation
- Confidence intervals use α = 0.05 significance level
- Outliers can be removed using IQR method before analysis
